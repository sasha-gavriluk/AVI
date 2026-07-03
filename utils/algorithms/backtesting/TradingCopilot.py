import json
import math
import numpy as np
import pandas as pd
from utils.DataBaseManager import DataBaseManager

# Генерація/тестування/сканування класичних rules_engine-стратегій
# видалено разом із самим rules_engine (заморожено й прибрано з проєкту).
# Довідка: Code/REFACTOR_LOG.md, старий код — git-коміт 0eeea95.


class TradingCopilot:
    """
    Пам'ять і прогнозування досвіду бектестів: зберігає результати в БД,
    оцінює компоненти (індикатори/патерни) за історичною успішністю та
    прогнозує шанси нових комбінацій на основі накопиченого досвіду.
    """

    def __init__(self, db_path: str = None, half_life_days: int = 90):
        self.db_path = db_path
        self.half_life_days = half_life_days
        self.min_score_for_best = 0.6
        self.update_threshold_weight = 15.0

    def _db_kwargs(self) -> dict:
        """kwargs для DataBaseManager: власний шлях, якщо задано, інакше дефолтна БД."""
        return {'db_path': self.db_path} if self.db_path else {'use_default': True}

    # =========================================================================
    # ПАМ'ЯТЬ ТА ПРОГНОЗУВАННЯ (Колишні TradingCopilot та ExperienceAnalyzer)
    # =========================================================================
    
    def _time_decay_weight(self, timestamp_str: str, half_life_days: int = None) -> float:
        """
        Чим старіший запис — тим менша його вага.
        """
        if half_life_days is None:
            half_life_days = self.half_life_days

        try:
            record_time = pd.Timestamp(timestamp_str)
            if record_time.tzinfo is not None:
                now = pd.Timestamp.now(tz=record_time.tzinfo)
            else:
                now = pd.Timestamp.now()
            
            days_ago = max(0, (now - record_time).days)
            decay = np.exp(-np.log(2) * days_ago / half_life_days)
            return float(decay)
        except Exception:
            return 1.0

    def _jaccard(self, set_a: set, set_b: set) -> float:
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _calculate_score(self, win_rate: float, profit_factor: float, total_trades: int) -> float:
        trade_confidence = min(total_trades / 50.0, 1.0)
        pf_normalized = min((profit_factor - 1.0) / 2.0, 1.0) if profit_factor > 1 else 0
        score = (
            (win_rate / 100.0) * 0.35 +
            pf_normalized * 0.45 +
            trade_confidence * 0.20
        )
        return round(score, 4)

    def _log_rule_change(self, element: str, field: str, old_val, new_val, reason: str, triggered_by: int):
        row = {
            "timestamp": pd.Timestamp.now().isoformat(),
            "element": element,
            "field": field,
            "old_value": str(old_val),
            "new_value": str(new_val),
            "reason": reason,
            "triggered_by_notes": triggered_by
        }
        df = pd.DataFrame([row])
        try:
            kwargs = self._db_kwargs()
            with DataBaseManager(**kwargs) as db:
                db.insert_data_from_pandas_auto("rules_changelog", df)
        except Exception as e:
            print(f"Помилка при збереженні результатів: {e}")

    def get_memory_df(self) -> pd.DataFrame:
        try:
            kwargs = self._db_kwargs()
            with DataBaseManager(**kwargs) as db:
                tables = db.get_all_tables()
                if 'copilot_memory' in tables:
                    df = db.get_data_as_dataframe('copilot_memory')
                    return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"Помилка зчитування пам'яті копілота з бази: {e}")
        return pd.DataFrame()

    def record_backtest_result(self, context: dict, indicators: list, performance: dict, note: str, logic_snapshot: dict = None):

        def safe_float(val):
            if pd.isna(val):
                return 0.0
            try:
                return float(val)
            except Exception:
                return 0.0

        win_rate = safe_float(performance.get("win_rate", 0.0))
        profit_factor = safe_float(performance.get("profit_factor", 0.0))
        total_trades = performance.get("total_trades", 0)
        score = self._calculate_score(win_rate, profit_factor, total_trades)

        new_row = {
            "timestamp": pd.Timestamp.now().isoformat(),
            "asset": context.get("asset", "UNKNOWN"),
            "timeframe": context.get("timeframe", "UNKNOWN"),
            "period_start": context.get("period_start", ""),
            "period_end": context.get("period_end", ""),
            "indicators": ",".join(sorted([str(i).strip().upper() for i in indicators])),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "score": score,
            "note": note
        }
        
        if logic_snapshot:
            new_row["logic_snapshot"] = json.dumps(logic_snapshot)
        else:
            new_row["logic_snapshot"] = "{}"
        df = pd.DataFrame([new_row])
        try:
            kwargs = self._db_kwargs()
            with DataBaseManager(**kwargs) as db:
                db.insert_data_from_pandas_auto("copilot_memory", df)
        except Exception as e:
            print(f"Помилка збереження пам'яті: {e}")

    def predict_success_chance(self, current_asset: str, current_tf: str, current_indicators: list) -> dict:
        memory = self.get_memory_df()
        if memory.empty:
            return {"status": "empty", "message": "База ще порожня. Проведіть кілька бектестів для навчання!"}

        current_set = set([str(i).strip().upper() for i in current_indicators])
        
        def parse_inds(x):
            if pd.isna(x): return set()
            return set([str(i).strip().upper() for i in str(x).split(',') if str(i).strip()])
            
        mem_inds = memory["indicators"].apply(parse_inds)
        
        exact_match = memory[
            (memory["asset"] == current_asset) & 
            (memory["timeframe"] == current_tf) &
            (mem_inds == current_set)
        ]

        if not exact_match.empty:
            if 'timestamp' in exact_match.columns:
                exact_match = exact_match.copy()
                exact_match['time_weight'] = exact_match['timestamp'].apply(self._time_decay_weight)
                tw_sum = exact_match['time_weight'].sum()
                if tw_sum > 0:
                    avg_win = float((exact_match["win_rate"] * exact_match['time_weight']).sum() / tw_sum)
                    avg_pf = float((exact_match["profit_factor"] * exact_match['time_weight']).sum() / tw_sum)
                else:
                    avg_win = float(exact_match["win_rate"].mean())
                    avg_pf = float(exact_match["profit_factor"].mean())
            else:
                avg_win = float(exact_match["win_rate"].mean())
                avg_pf = float(exact_match["profit_factor"].mean())
                
            last_note = exact_match.iloc[-1]["note"]

            if math.isnan(avg_win): avg_win = 0.0
            if math.isnan(avg_pf): avg_pf = 0.0
            
            return {
                "status": "exact_match",
                "win_rate": avg_win,
                "profit_factor": avg_pf,
                "note": last_note if str(last_note) != "nan" else ""
            }
                
        # Схожий пошук через Jaccard (новий уніфікований підхід)
        summary = self.generate_experience_summary(current_indicators)
        return {"status": "similar_match", "summary": summary}

    def generate_experience_summary(self, indicators: list) -> str:
        """Аналіз досвіду у текстовому вигляді для звіту."""
        df = self.get_memory_df()
        if df.empty:
             return "База досвіду порожня або не знайдена."
        
        current_set = set([str(i).strip().upper() for i in indicators])
        if not current_set:
            return "Немає індикаторів для аналізу."
            
        if 'timestamp' in df.columns:
            df['time_weight'] = df['timestamp'].apply(self._time_decay_weight)
        else:
            df['time_weight'] = 1.0
            
        df['ind_set'] = df['indicators'].apply(lambda x: set([str(i).strip().upper() for i in str(x).split(',') if str(i).strip()]))
        
        summary_lines = []
        exact_matches = df[df['ind_set'] == current_set]
        
        if not exact_matches.empty:
            tw_sum = exact_matches['time_weight'].sum()
            if tw_sum > 0:
                wr = (exact_matches['win_rate'] * exact_matches['time_weight']).sum() / tw_sum
                pf = (exact_matches['profit_factor'] * exact_matches['time_weight']).sum() / tw_sum
            else:
                wr = exact_matches['win_rate'].mean()
                pf = exact_matches['profit_factor'].mean()
            count = len(exact_matches)
            
            summary_lines.append(f"🎯 ТОЧНИЙ ЗБІГ: Ця стратегія тестувалася {count} разів.")
            summary_lines.append(f"   📊 Середній Win Rate: {wr:.1f}%, Profit Factor: {pf:.2f}")
            if wr >= 50:
                summary_lines.append("   ✅ Висновок: Історично це робоча стратегія.")
            else:
                summary_lines.append("   ❌ Висновок: Стратегія збиткова. Рекомендується змінити логіку.")
        else:
            summary_lines.append("🆕 Точного збігу не знайдено, але ШІ робить прогноз на основі набутого досвіду...")
            
            df['sim_score'] = df['ind_set'].apply(lambda x: self._jaccard(current_set, x))
            similar_df = df[df['sim_score'] > 0.5].copy()
            
            if not similar_df.empty:
                if 'total_trades' in similar_df.columns:
                    similar_df['weight'] = similar_df['sim_score'] * np.log1p(similar_df['total_trades'].fillna(50)) * similar_df['time_weight']
                else:
                    similar_df['weight'] = similar_df['sim_score'] * np.log1p(50) * similar_df['time_weight']
                    
                total_weight = similar_df['weight'].sum()
                if total_weight > 0:
                    predicted_wr = (similar_df['win_rate'] * similar_df['weight']).sum() / total_weight
                    predicted_pf = (similar_df['profit_factor'] * similar_df['weight']).sum() / total_weight
                else:
                    predicted_wr = similar_df['win_rate'].mean()
                    predicted_pf = similar_df['profit_factor'].mean()
                
                summary_lines.append(f"🔮 ПРОГНОЗ ШІ: Аналізуючи {len(similar_df)} частково схожих стратегій, очікувані результати:")
                summary_lines.append(f"   📊 Прогнозований Win Rate: {predicted_wr:.1f}%, Profit Factor: {predicted_pf:.2f}")
                
                if predicted_pf > 1.2 and predicted_wr >= 50:
                    summary_lines.append("   ✅ Висновок ШІ: Стратегія виглядає перспективно, комбінація історично вдала.")
                elif predicted_pf < 0.9 or predicted_wr < 40:
                    summary_lines.append("   ❌ Висновок ШІ: Досвід підказує, що ця комбінація скоріш за все буде збитковою.")
                else:
                    summary_lines.append("   ⚠️ Висновок ШІ: Результати посередні. Стратегія потребує тонкого налаштування.")
            else:
                summary_lines.append("🤷 Досвід відсутній (жоден індикатор раніше не використовувався). Прогноз неможливий.")

        bad_indicators = []
        good_indicators = []
        MIN_RECORDS = 10
        MIN_TRADES = 30
        
        for ind in current_set:
            if 'total_trades' in df.columns:
                ind_df = df[df['ind_set'].apply(lambda x: ind in x) & (df['total_trades'] >= MIN_TRADES)]
            else:
                ind_df = df[df['ind_set'].apply(lambda x: ind in x)]
                
            if len(ind_df) >= MIN_RECORDS:
                ind_wr = ind_df['win_rate'].mean()
                if ind_wr < 40:
                    bad_indicators.append(ind)
                elif ind_wr > 60:
                    good_indicators.append(ind)
                    
        if bad_indicators:
            summary_lines.append(f"⚠️ ОБЕРЕЖНО: Індикатори {', '.join(bad_indicators)} історично дуже слабкі у вашій базі (Win Rate < 40%).")
        if good_indicators:
            summary_lines.append(f"🔥 ВІДМІННО: Ви використовуєте сильні індикатори {', '.join(good_indicators)} (історичний Win Rate > 60%).")

        return "\n".join(summary_lines)

    def get_best_components(self, direction="BUY") -> dict:
        """
        Аналізує copilot_memory -> які елементи найчастіше
        зустрічаються в успішних стратегіях (score > 0.6).
        Повертає рейтинг: {"BOS": 0.78, "RSI_14": 0.71, ...}
        """
        df = self.get_memory_df()
        if df.empty:
            return {}
            
        if 'score' in df.columns:
            successful = df[df['score'] > self.min_score_for_best].copy()
        else:
            successful = df[(df['win_rate'] > 50.0) & (df['profit_factor'] > 1.2)].copy()
            
        if successful.empty:
            return {}
            
        if 'timestamp' in successful.columns:
            successful['time_weight'] = successful['timestamp'].apply(self._time_decay_weight)
        else:
            successful['time_weight'] = 1.0
            
        component_counts = {}
        total_weight = successful['time_weight'].sum()
        if total_weight == 0:
            return {}
        
        for _, row in successful.iterrows():
            inds = [i.strip() for i in str(row['indicators']).split(',') if i.strip()]
            for ind in inds:
                component_counts[ind] = component_counts.get(ind, 0) + row['time_weight']
                
        rating = {}
        for comp, count in component_counts.items():
            rating[comp] = round(count / total_weight, 2)
            
        return dict(sorted(rating.items(), key=lambda item: item[1], reverse=True))
