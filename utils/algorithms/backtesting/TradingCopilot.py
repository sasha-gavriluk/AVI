import ast
import re
import pandas as pd
import os
from utils.DataBaseManager import DataBaseManager
import random
from multiprocessing import Pool
import os

# ==================================================================
# ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): модульні функції для
# multiprocessing-виконання коду класичних стратегій (через rules_engine,
# вже заморожений) та їх сканування на ринках. Ніде не викликаються.
# Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
# ==================================================================

_DISABLED_TRADING_COPILOT_WORKER_FUNCTIONS_SOURCE = r'''
_GLOBAL_DF_FOR_WORKERS = None
_GLOBAL_TABLE_NAME_FOR_WORKERS = None

def _init_worker(dfs_dict, table_name):
    global _GLOBAL_DF_FOR_WORKERS, _GLOBAL_TABLE_NAME_FOR_WORKERS
    _GLOBAL_DF_FOR_WORKERS = dfs_dict
    _GLOBAL_TABLE_NAME_FOR_WORKERS = table_name

def _scan_single_market(args: tuple) -> dict:
    strategy_code, df, table_name, strat_name = args
    try:
        from utils.algorithms.backtesting.MarketRunner import MarketRunner
        from utils.rules_engine.core import Indicator, Pattern, Algorithm, Expression, Constant
        from utils.rules_engine.strategy import Strategy
        import numpy as np
        
        safe_globals = {
            '__builtins__': {
                'True': True, 'False': False, 'None': None,
                'min': min, 'max': max, 'abs': abs,
                'float': float, 'int': int, 'str': str,
                'bool': bool, 'list': list, 'dict': dict,
                'tuple': tuple, 'set': set,
                'len': len, 'sum': sum
            },
            'Strategy': Strategy,
            'Indicator': Indicator,
            'Pattern': Pattern,
            'Algorithm': Algorithm,
            'Expression': Expression,
            'Constant': Constant
        }
        
        clean_code = "\n".join([line for line in strategy_code.split("\n") if not line.strip().startswith("import") and not line.strip().startswith("from")])
        
        local_scope = {}
        exec(clean_code, safe_globals, local_scope)
        strategy_obj = local_scope.get("strategy")
        
        if df is None or df.empty or len(df) < 50:
            return {"success": False, "error": "Недостатньо даних", "table": table_name, "strategy": strat_name}
            
        from utils.rules_engine import IndicatorRegistry
        registry = IndicatorRegistry(df)
        entry_series = strategy_obj.entry_rule.evaluate(registry)
        
        try:
            val_prev = entry_series.iloc[-2] if len(entry_series) > 1 else False
            signal_ready = bool(val_prev) if pd.notna(val_prev) else False
        except Exception:
            signal_ready = False
            
        try:
            val_last = entry_series.iloc[-1] if len(entry_series) > 0 else False
            signal_warning = bool(val_last) if pd.notna(val_last) else False
        except Exception:
            signal_warning = False
        
        direction = "BUY"
        import re
        match = re.search(r'Напрямок:\s*(BUY|SELL)', strategy_code)
        if match:
            direction = match.group(1)
            
        return {
            "success": True, 
            "table": table_name,
            "strategy": strat_name,
            "direction": direction,
            "signal_ready": signal_ready,
            "signal_warning": signal_warning and not signal_ready
        }
    except Exception as e:
        return {"success": False, "error": str(e), "table": table_name, "strategy": strat_name}

def _run_single_strategy(strategy_code: str) -> dict:
    """Ізольована функція для одного процесу (має бути на рівні модуля)."""
    global _GLOBAL_DF_FOR_WORKERS, _GLOBAL_TABLE_NAME_FOR_WORKERS
    
    # Тепер _GLOBAL_DF_FOR_WORKERS це словник {table_name: dataframe}
    dfs_dict = _GLOBAL_DF_FOR_WORKERS
    if isinstance(dfs_dict, pd.DataFrame): # Для зворотної сумісності (якщо не оновилось)
        dfs_dict = {_GLOBAL_TABLE_NAME_FOR_WORKERS: dfs_dict}
        
    try:
        from utils.algorithms.backtesting.MarketRunner import MarketRunner
        from utils.rules_engine.core import Indicator, Pattern, Algorithm, Expression, Constant
        from utils.rules_engine.strategy import Strategy
        import ast

        # Sandbox AST перевірка
        tree = ast.parse(strategy_code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise ValueError("Imports are not allowed in strategy code.")
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in ['open', 'exec', 'eval', '__import__', 'globals', 'locals']:
                raise ValueError(f"Function {getattr(node.func, 'id', 'unknown')} is not allowed.")

        # Компілюємо стратегію з коду в безпечному середовищі
        safe_globals = {
            '__builtins__': {
                'True': True, 'False': False, 'None': None,
                'min': min, 'max': max, 'abs': abs,
                'float': float, 'int': int, 'str': str,
                'bool': bool, 'list': list, 'dict': dict,
                'tuple': tuple, 'set': set,
                'len': len, 'sum': sum
            },
            'Strategy': Strategy,
            'Indicator': Indicator,
            'Pattern': Pattern,
            'Algorithm': Algorithm,
            'Expression': Expression,
            'Constant': Constant
        }
        
        local_scope = {}
        exec(strategy_code, safe_globals, local_scope)
        strategy_obj = local_scope.get("strategy")
        
        total_trades = 0
        total_gross_profit = 0.0
        total_gross_loss = 0.0
        total_winning_trades = 0
        
        import time, random
        
        asset_results = []
        
        for t_name, df in dfs_dict.items():
            runner = MarketRunner(
                strategy=strategy_obj,
                db_path=None,
                db_table_path=t_name
            )
            
            result_table = f"backtest_{int(time.time()*1000)}_{random.randint(1000, 9999)}"
            df_trades = runner.run(result_table_name=result_table, df=df)
            
            asset_trades = 0
            asset_winning_trades = 0
            asset_gross_profit = 0.0
            asset_gross_loss = 0.0
            
            if df_trades is not None and not df_trades.empty:
                closed_trades = df_trades[df_trades['Status'] == 'closed']
                num_closed = len(closed_trades)
                if num_closed > 0:
                    asset_trades = num_closed
                    asset_winning_trades = len(closed_trades[closed_trades['Profit'] > 0])
                    asset_gross_profit = closed_trades[closed_trades['Profit'] > 0]['Profit'].sum()
                    asset_gross_loss = abs(closed_trades[closed_trades['Profit'] < 0]['Profit'].sum())
                    
                    total_trades += asset_trades
                    total_winning_trades += asset_winning_trades
                    total_gross_profit += asset_gross_profit
                    total_gross_loss += asset_gross_loss
            
            asset_perf = {
                'win_rate': (asset_winning_trades / asset_trades * 100.0) if asset_trades > 0 else 0.0,
                'profit_factor': (asset_gross_profit / asset_gross_loss) if asset_gross_loss > 0 else (asset_gross_profit if asset_gross_profit > 0 else 0),
                'total_trades': asset_trades
            }
            
            parts = t_name.split('_') if t_name else []
            asset_name = "_".join(parts[:-1]) if len(parts) >= 2 else "UNKNOWN"
            timeframe = parts[-1] if len(parts) >= 2 else "UNKNOWN"
            
            asset_context = {
                "asset": asset_name,
                "timeframe": timeframe,
                "period_start": str(df.index[0]) if not df.empty else "",
                "period_end": str(df.index[-1]) if not df.empty else ""
            }
            
            asset_results.append({
                "context": asset_context,
                "performance": asset_perf
            })
        
        # Аналіз індикаторів з AST
        indicators = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in ['Indicator', 'Pattern', 'Algorithm']:
                if node.args and isinstance(node.args[0], ast.Constant):
                    indicators.append(node.args[0].value)

        # Аналіз показників торгівлі (Агреговані по всім активам)
        overall_performance = {
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'total_trades': total_trades
        }
        
        if total_trades > 0:
            overall_performance['win_rate'] = (total_winning_trades / total_trades) * 100.0
            overall_performance['profit_factor'] = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else (total_gross_profit if total_gross_profit > 0 else 0)
        
        # Відправляємо контекст і результати
        return {
            "success": True, 
            "result": {
                "asset_results": asset_results,
                "performance": overall_performance,
                "indicators": indicators
            }, 
            "code": strategy_code
        }
    except Exception as e:
        return {"success": False, "error": str(e), "code": strategy_code}

'''


class TradingCopilot:
    """
    Єдина система (Copilot + StrategyAnalyzer + ExperienceAnalyzer),
    яка аналізує код стратегій (AST), оцінює шанси на успіх
    та зберігає досвід бектестів безпосередньо в базу даних.
    """

    def __init__(self, db_path: str = None, half_life_days: int = 90):
        self.db_path = db_path
        self.half_life_days = half_life_days
        self.min_score_for_best = 0.6
        self.update_threshold_weight = 15.0
        # Набори індикаторів за категоріями для евристичного аналізу
        self.trend_indicators = ["ema", "sma", "wma", "hma", "macd", "ema_cross", "market_state"]
        self.oscillators = ["rsi", "stochastic", "mfi", "cci", "willr"]
        self.patterns = ["hammer", "engulfing", "shooting_star", "doji"]

    # =========================================================================
    # ПАМ'ЯТЬ ТА ПРОГНОЗУВАННЯ (Колишні TradingCopilot та ExperienceAnalyzer)
    # =========================================================================
    
    def _time_decay_weight(self, timestamp_str: str, half_life_days: int = None) -> float:
        """
        Чим старіший запис — тим менша його вага.
        """
        if half_life_days is None:
            half_life_days = self.half_life_days
            
        import numpy as np
        import pandas as pd
        
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
            kwargs = {'db_path': self.db_path} if self.db_path else {'use_default': True}
            with DataBaseManager(**kwargs) as db:
                db.insert_data_from_pandas_auto("rules_changelog", df)
        except Exception as e:
            print(f"Помилка при збереженні результатів: {e}")

    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    # ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): генерація й тест випадкових
    # стратегій. Викликає StrategyGenerator.generate() (заморожений) і
    # _run_single_strategy (заморожений вище) — сама лишається недосяжною,
    # бо всі виклики цього методу закоментовано в copilot_service.py.
    # Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    def run_random_training(self, generator, n_strategies: int = 1000, direction: str = "BUY", n_workers: int = None, table_name: str = None):
        """Паралельний запуск N рандомних стратегій."""
        if n_workers is None:
            n_workers = max(1, (os.cpu_count() or 4) - 1)
            
        import pandas as pd
        from utils.DataBaseManager import DataBaseManager
        import random
        
        dfs_dict = {}
        with DataBaseManager(self.db_path) as db:
            if table_name:
                df = db.get_data_as_dataframe(table_name)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    dfs_dict[table_name] = df
            else:
                tables = [t for t in db.get_all_tables() if not t.startswith('sqlite') and not t.startswith('copilot_') and not t.startswith('rules_') and not t.startswith('backtest_') and not t.startswith('temp_sim_')]
                
                # Спробуємо отримати цільові активи з налаштувань
                import json
                from utils.PathManager import PathManager
                try:
                    settings_path = PathManager.get_settings_path()
                    if os.path.exists(settings_path):
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            settings_data = json.load(f)
                            target_assets = settings_data.get("copilot", {}).get("target_assets", [])
                            # Беремо 15m таймфрейм як дефолтний
                            if target_assets:
                                target_tables = [f"{a}_15m" for a in target_assets]
                                valid_target_tables = [t for t in target_tables if t in tables]
                                if valid_target_tables:
                                    tables = valid_target_tables
                except Exception:
                    pass
                
                # Обмежуємо до 3-5 активів випадково (Multi-Asset)
                if len(tables) > 3:
                    tables_to_test = random.sample(tables, 3)
                else:
                    tables_to_test = tables
                    
                for t in tables_to_test:
                    df = db.get_data_by_number_range(t, 10000)
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        dfs_dict[t] = df
            
        if not dfs_dict:
            print(f"Помилка: Не знайдено жодної таблиці з даними для тестування.")
            return

        print(f"Генерація {n_strategies} стратегій...")
        strategy_codes = [generator.generate(direction) for _ in range(n_strategies)]
        
        args_list = [code for code in strategy_codes if code is not None]
        
        global _GLOBAL_DF_FOR_WORKERS, _GLOBAL_TABLE_NAME_FOR_WORKERS
        _GLOBAL_DF_FOR_WORKERS = dfs_dict
        _GLOBAL_TABLE_NAME_FOR_WORKERS = f"MULTI_ASSET_{len(dfs_dict)}"
        
        print(f"Запуск {len(args_list)} стратегій на {n_workers} ядрах...")
        results = []
        import multiprocessing
        ctx = multiprocessing.get_context('spawn')
        pool = ctx.Pool(processes=n_workers, initializer=_init_worker, initargs=(dfs_dict, _GLOBAL_TABLE_NAME_FOR_WORKERS), maxtasksperchild=10)
        try:
            for i, result in enumerate(pool.imap_unordered(_run_single_strategy, args_list, chunksize=10)):
                results.append(result)
                if (i+1) % 50 == 0:
                    print(f"  {i+1}/{len(args_list)} завершено...")
        finally:
            pool.close()
            pool.join()
                    
        successful = [r for r in results if r['success']]
        print(f"Успішно: {len(successful)}/{len(results)}")
        
        import time
        import json
        from utils.PathManager import PathManager
        
        top_count = 10
        min_trades_th = 10
        min_score = self.min_score_for_best
        try:
            settings_path = PathManager.get_settings_path()
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                    top_count = settings_data.get("copilot", {}).get("top_strategies_count", 5)
                    min_trades_th = settings_data.get("copilot", {}).get("min_trades", 10)
        except Exception:
            pass

        scored_results = []
        for r in successful:
            perf = r['result']['performance']
            wr = perf.get('win_rate', 0)
            pf = perf.get('profit_factor', 0)
            tt = perf.get('total_trades', 0)
            if tt >= min_trades_th:
                score = (wr / 100) * 0.4 + min(pf, 3.0) / 3.0 * 0.6
                r['score'] = score
                scored_results.append(r)
                
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        copilot_dir = os.path.join(PathManager.get_strategies_dir(), 'Copilot')
        os.makedirs(copilot_dir, exist_ok=True)
        
        for r in scored_results:
            if r['score'] < min_score: continue
            
            # Записуємо в пам'ять тільки хороші стратегії! Це зменшить мусор в базі даних.
            if 'asset_results' in r['result']:
                for a_res in r['result']['asset_results']:
                    if a_res['performance']['total_trades'] > 0:
                        self.record_backtest_result(
                            context=a_res['context'],
                            indicators=r['result']['indicators'],
                            performance=a_res['performance'],
                            note=f"auto_training_score_{r['score']:.2f}"
                        )
            else:
                self.record_backtest_result(
                    context=r['result'].get('context', {}),
                    indicators=r['result']['indicators'],
                    performance=r['result']['performance'],
                    note=f"auto_training_score_{r['score']:.2f}"
                )
            
            code = r['code']
            existing_files = []
            for f in os.listdir(copilot_dir):
                if f.endswith('.py'):
                    try:
                        score_str = f.split('_')[1]
                        existing_files.append((f, float(score_str)))
                    except: pass
            
            existing_files.sort(key=lambda x: x[1])
            
            if len(existing_files) < top_count:
                filename = f"strat_{r['score']:.4f}_{int(time.time()*1000)}.py"
                with open(os.path.join(copilot_dir, filename), 'w', encoding='utf-8') as f:
                    f.write(code)
            else:
                worst_file, worst_score = existing_files[0]
                if r['score'] > worst_score:
                    try: os.remove(os.path.join(copilot_dir, worst_file))
                    except: pass
                    filename = f"strat_{r['score']:.4f}_{int(time.time()*1000)}.py"
                    with open(os.path.join(copilot_dir, filename), 'w', encoding='utf-8') as f:
                        f.write(code)
            
        return results

    def get_memory_df(self) -> pd.DataFrame:
        try:
            kwargs = {'db_path': self.db_path} if self.db_path else {'use_default': True}
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
            import pandas as pd
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
            import json
            new_row["logic_snapshot"] = json.dumps(logic_snapshot)
        else:
            new_row["logic_snapshot"] = "{}"
        df = pd.DataFrame([new_row])
        try:
            kwargs = {'db_path': self.db_path} if self.db_path else {'use_default': True}
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

        general_match = memory[mem_inds == current_set]

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
            
            import math
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
                import numpy as np
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

    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    # ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): самонавчальне редагування
    # rules.json (правил двигуна) на основі успішних бектестів. Раніше
    # викликався лише зі StrategyGenerator.generate() (заморожений) —
    # тепер недосяжний. Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    def update_rules_from_experience(self, rules_path: str):
        """
        Аналізує успішні бектести з copilot_memory та оновлює data/config/rules.json.
        (Алгоритм, що сам себе розширює).
        """
        import json
        import os
        from collections import defaultdict
        
        df = self.get_memory_df()
        if df.empty or 'logic_snapshot' not in df.columns:
            return
            
        # Беремо лише дуже успішні стратегії
        successful = df[(df['win_rate'] > 50.0) & (df['profit_factor'] > 1.2)].copy()
        
        if 'timestamp' in successful.columns:
            successful['time_weight'] = successful['timestamp'].apply(self._time_decay_weight)
        else:
            successful['time_weight'] = 1.0
        
        if successful['time_weight'].sum() < self.update_threshold_weight:
            return
            
        # Збираємо всі значення по індикаторам
        # values_map[indicator][op] = [(val1, w1), (val2, w2), ...]
        values_map = defaultdict(lambda: defaultdict(list))
        
        for _, row in successful.iterrows():
            try:
                snap = json.loads(row['logic_snapshot'])
                # Обходимо entry та exit
                for c in snap.get("entry", []) + snap.get("exit", []):
                    # c = {"var": "rsi", "class": "Indicator", "arg": "RSI_14", "op_symbol": "<", "val": 35}
                    ind = c.get("arg")
                    op = c.get("op_symbol")
                    val = c.get("val")
                    
                    if ind and op and isinstance(val, (int, float)):
                        values_map[ind][op].append((val, row['time_weight']))
            except Exception:
                continue
                
        if not values_map:
            return
            
        # Оновлюємо rules.json
        if not os.path.exists(rules_path):
            return
            
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
                
            updated = False
            for ind, ops_data in values_map.items():
                if ind not in rules:
                    continue
                    
                for op, vals in ops_data.items():
                    total_w = sum(w for v, w in vals)
                    if len(vals) < 10 or total_w < 5.0: # Потрібно хоча б 10 успішних прикладів
                        continue
                        
                    avg_val = sum(v * w for v, w in vals) / total_w
                    # Округлюємо для краси
                    avg_val = int(avg_val) if isinstance(vals[0][0], int) else round(avg_val, 2)
                    
                    # Шукаємо це правило в buy_conditions та sell_conditions
                    for cond_list in [rules[ind].get("buy_conditions", []), rules[ind].get("sell_conditions", [])]:
                        for c in cond_list:
                            # Якщо оператор співпадає і це число (а не "close" чи True)
                            if c["op"] == op and isinstance(c["value"], (int, float)):
                                old_val = c["value"]
                                if old_val != avg_val:
                                    c["value"] = avg_val
                                    updated = True
                                    self._log_rule_change(ind, "value", old_val, avg_val, "Автоматичне навчання", len(successful))
                                
            if updated:
                with open(rules_path, 'w', encoding='utf-8') as f:
                    json.dump(rules, f, indent=2)
                    
        except Exception as e:
            print(f"Помилка оновлення правил: {e}")

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



    # =========================================================================
    # СТАТИЧНИЙ АНАЛІЗАТОР СТРАТЕГІЙ (Колишній StrategyAnalyzer)
    # =========================================================================
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    # ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): статичний аналіз коду
    # rules_engine-стратегій (analyze() + всі приватні _check_*/_parse_*
    # helper-методи нижче до кінця секції). Єдиний викликач був
    # gui/logic/BacktestLogic.py — вкладка "Тестер стратегій" вже
    # відключена (REFACTOR_LOG.md, Кластер 2), тож секція недосяжна.
    # Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!

    def analyze(self, code_text: str) -> dict:
        """
        Аналізує текст стратегії та повертает детальний звіт.
        """
        report = {
            "success": False,
            "error": None,
            "variables": {},      # Змінні індикаторів: {var_name: {"type": "Indicator", "arg": "RSI_14"}}
            "warnings": [],       # Список попереджень (dict)
            "suggestions": [],    # Список корисних порад (str)
            "experience_summary": "", # Аналіз історичного досвіду
            "logic_snapshot": {}  # Збереження розпаршених умов входу та виходу
        }

        try:
            tree = ast.parse(code_text)
            report["success"] = True
        except Exception as e:
            report["error"] = f"Помилка парсингу коду: {e}"
            return report

        self._extract_variables(tree, report)

        has_entry = False
        has_exit = False
        has_strategy_object = False
        
        entry_node = None
        exit_node = None

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "entry":
                            has_entry = True
                            entry_node = node.value
                        elif target.id == "exit":
                            has_exit = True
                            exit_node = node.value
                        elif target.id == "strategy":
                            has_strategy_object = True

        if not has_entry:
            report["warnings"].append({
                "type": "STRUCTURE",
                "severity": "DANGER",
                "message": "Відсутнє правило входу 'entry'!",
                "explanation": "Стратегія повинна визначати правило входу, наприклад: entry = (rsi < 30)"
            })
        if not has_exit:
            report["warnings"].append({
                "type": "STRUCTURE",
                "severity": "WARNING",
                "message": "Відсутнє правило виходу 'exit'.",
                "explanation": "Якщо правило 'exit' не визначено, позиція закриватиметься лише в кінці бектесту або за іншими умовами."
            })
        if not has_strategy_object:
            report["warnings"].append({
                "type": "STRUCTURE",
                "severity": "DANGER",
                "message": "Об'єкт 'strategy' не створено!",
                "explanation": "Наприкінці стратегії обов'язково має бути створено об'єкт: strategy = Strategy(entry_rule=entry, exit_rule=exit)"
            })

        if not has_entry or entry_node is None:
            return report

        entry_conditions = self._parse_expression(entry_node, report["variables"])
        exit_conditions = self._parse_expression(exit_node, report["variables"]) if exit_node else []

        report["logic_snapshot"] = {
            "entry": entry_conditions,
            "exit": exit_conditions
        }

        self._check_redundancy(report)
        self._check_impossible_conditions(entry_conditions, report)
        self._check_trend_oscillator_clash(entry_conditions, report)
        self._check_entry_exit_overlap(entry_conditions, exit_conditions, report)
        self._check_pattern_context(entry_conditions, report)

        self._generate_suggestions(report)

        # Інтегруємо досвід ШІ
        indicators = []
        for var_name, info in report["variables"].items():
            if info.get("class") in ["Indicator", "Pattern", "Algorithm"] and info.get("arg"):
                indicators.append(info["arg"])
                
        if indicators:
            report["experience_summary"] = self.generate_experience_summary(indicators)

        return report

    def _extract_variables(self, tree, report):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    func_name = self._get_name_id(node.value.func)
                    if func_name in ["Indicator", "Pattern", "Algorithm"]:
                        arg_value = None
                        if node.value.args and isinstance(node.value.args[0], ast.Constant):
                            arg_value = node.value.args[0].value
                        
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                report["variables"][target.id] = {
                                    "class": func_name,
                                    "arg": arg_value
                                }

    def _parse_expression(self, node, variables) -> list:
        conditions = []
        if node is None:
            return conditions

        if isinstance(node, ast.BinOp):
            left_conds = self._parse_expression(node.left, variables)
            right_conds = self._parse_expression(node.right, variables)
            
            op_type = "AND" if isinstance(node.op, ast.BitAnd) else "OR"
            
            for c in left_conds:
                c["op"] = op_type
            for c in right_conds:
                c["op"] = op_type
                
            conditions.extend(left_conds)
            conditions.extend(right_conds)

        elif isinstance(node, ast.Compare):
            left_var = self._get_name_id(node.left)
            
            if left_var in variables:
                op_symbol = self._get_op_symbol(node.ops[0])
                right_val = None
                
                if node.comparators and isinstance(node.comparators[0], ast.Constant):
                    right_val = node.comparators[0].value
                elif node.comparators and isinstance(node.comparators[0], ast.Name):
                    right_val = node.comparators[0].id
                
                conditions.append({
                    "var": left_var,
                    "class": variables[left_var]["class"],
                    "arg": variables[left_var]["arg"],
                    "op_symbol": op_symbol,
                    "val": right_val,
                    "op": "AND"
                })
        
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                caller = self._get_name_id(node.func.value)
                method = node.func.attr
                
                if caller in variables and method in ["crosses_over", "crosses_under"]:
                    arg_var = None
                    if node.args:
                        arg_var = self._get_name_id(node.args[0])
                        
                    conditions.append({
                        "var": caller,
                        "class": variables[caller]["class"],
                        "arg": variables[caller]["arg"],
                        "op_symbol": method,
                        "val": arg_var,
                        "op": "AND"
                    })

        return conditions

    def _check_redundancy(self, report):
        vars_info = report["variables"]
        ma_periods = []
        for var_name, info in vars_info.items():
            if info["class"] == "Indicator" and info["arg"]:
                name_upper = info["arg"].upper()
                match = re.search(r'(SMA|EMA)_(\d+)', name_upper)
                if match:
                    ma_type = match.group(1)
                    period = int(match.group(2))
                    ma_periods.append((var_name, ma_type, period))
        
        for i in range(len(ma_periods)):
            for j in range(i + 1, len(ma_periods)):
                var1, type1, p1 = ma_periods[i]
                var2, type2, p2 = ma_periods[j]
                
                if abs(p1 - p2) <= 3 and p1 != p2:
                    report["warnings"].append({
                        "type": "REDUNDANCY",
                        "severity": "INFO",
                        "message": f"Потенційно дублюючі індикатори: {var1} ({type1}_{p1}) та {var2} ({type2}_{p2}).",
                        "explanation": f"Ці ковзні середні мають занадто близькі періоди ({p1} та {p2}). Вони сильно корелюють і не додають нової інформації, лише створюючи зайвий шум та навантаження."
                    })

    def _check_impossible_conditions(self, conditions, report):
        var_groups = {}
        for c in conditions:
            if c["op"] == "AND":
                var_groups.setdefault(c["var"], []).append(c)

        for var, conds in var_groups.items():
            if len(conds) < 2:
                continue
            
            for i in range(len(conds)):
                for j in range(i + 1, len(conds)):
                    c1, c2 = conds[i], conds[j]
                    
                    if c1["val"] is None or c2["val"] is None:
                        continue
                        
                    try:
                        v1, v2 = float(c1["val"]), float(c2["val"])
                        if (c1["op_symbol"] == "<" and c2["op_symbol"] == ">" and v1 <= v2) or \
                           (c1["op_symbol"] == ">" and c2["op_symbol"] == "<" and v2 <= v1):
                            
                            report["warnings"].append({
                                "type": "IMPOSSIBLE_LOGIC",
                                "severity": "DANGER",
                                "message": f"Логічна суперечність для {var}: '{var} {c1['op_symbol']} {c1['val']}' та '{var} {c2['op_symbol']} {c2['val']}' в одному 'AND' блоці.",
                                "explanation": "Ця умова ніколи не буде виконана! Змінна не може бути одночасно меншою за менше значення і більшою за більше."
                            })
                    except (ValueError, TypeError):
                        pass

    def _check_trend_oscillator_clash(self, conditions, report):
        has_bullish_trend = False
        has_oversold = False
        has_overbought = False
        
        trend_var = None
        osc_var = None

        for c in conditions:
            arg_lower = c["arg"].lower() if c["arg"] else ""
            
            if any(t in arg_lower for t in ["ema_cross", "market_state", "linear"]):
                if c["op_symbol"] == "==" and c["val"] == 1:
                    has_bullish_trend = True
                    trend_var = c["var"]
            
            if any(o in arg_lower for o in self.oscillators):
                if c["op_symbol"] in ["<", "<="]:
                    try:
                        val = float(c["val"])
                        if val <= 40:
                            has_oversold = True
                            osc_var = c["var"]
                    except (ValueError, TypeError):
                        pass
                elif c["op_symbol"] in [">", ">="]:
                    try:
                        val = float(c["val"])
                        if val >= 60:
                            has_overbought = True
                            osc_var = c["var"]
                    except (ValueError, TypeError):
                        pass

        if has_bullish_trend and has_overbought and any(c["op"] == "AND" for c in conditions):
            report["warnings"].append({
                "type": "PHASE_CLASH",
                "severity": "WARNING",
                "message": f"Конфлікт фаз тренду та імпульсу: трендовий фільтр '{trend_var}' вказує на висхідний рух, але осцилятор '{osc_var}' сигналізує про перекупленість.",
                "explanation": "Купівля активу, коли тренд вже перегрітий (перекуплений), часто призводить до входу на локальному максимумі безпосередньо перед корекцією."
            })

    def _check_entry_exit_overlap(self, entry_conds, exit_conds, report):
        if not entry_conds or not exit_conds:
            return

        for enc in entry_conds:
            for exc in exit_conds:
                if enc["var"] == exc["var"] and enc["val"] is not None and exc["val"] is not None:
                    try:
                        en_val = float(enc["val"])
                        ex_val = float(exc["val"])
                        
                        if enc["op_symbol"] == "<" and exc["op_symbol"] == "<" and en_val < ex_val:
                            report["warnings"].append({
                                "type": "EXIT_OVERLAP",
                                "severity": "WARNING",
                                "message": f"Небезпечне перекриття правил: вхід при '{enc['var']} < {enc['val']}' та вихід при '{exc['var']} < {exc['val']}'.",
                                "explanation": f"Оскільки {en_val} менше ніж {ex_val}, будь-який успішний вхід автоматично задовольнить умову виходу на наступній свічці, що призведе до миттєвого закриття угод!"
                            })
                    except (ValueError, TypeError):
                        pass

    def _check_pattern_context(self, conditions, report):
        has_pattern = False
        has_trend_filter = False
        pattern_var = None

        for c in conditions:
            arg_lower = c["arg"].lower() if c["arg"] else ""
            if any(p in arg_lower for p in self.patterns):
                has_pattern = True
                pattern_var = c["var"]
            if any(t in arg_lower for t in ["market_state", "linear"]):
                has_trend_filter = True

        if has_pattern and not has_trend_filter:
            report["warnings"].append({
                "type": "NO_CONTEXT",
                "severity": "INFO",
                "message": f"Свічковий патерн '{pattern_var}' використовується без ринкового контексту.",
                "explanation": "Свічкові моделі (наприклад, Молот чи Поглинання) є локальними і працюють виключно при наявності сильного тренду або на рівнях підтримки/опору. Без фільтрації ринкового стану (трендовий алгоритм) вони генеруватимуть багато хибних сигналів."
            })

    def _generate_suggestions(self, report):
        vars_info = report["variables"]
        has_osc = any(info["class"] == "Indicator" and any(o in info["arg"].lower() for o in self.oscillators) for info in vars_info.values() if info["arg"])
        if not has_osc:
            report["suggestions"].append("Спробуйте додати осцилятор (наприклад, RSI або Stochastic) для точнішого визначення зон перекупленості/перепроданості.")
            
        has_trend = any(info["class"] == "Indicator" and any(t in info["arg"].lower() for t in self.trend_indicators) for info in vars_info.values() if info["arg"])
        if not has_trend:
            report["suggestions"].append("Рекомендується додати трендовий індикатор (наприклад, EMA_CROSS або MARKET_STATE_LINEAR), щоб торгувати тільки в напрямку глобального тренду.")

        if len(vars_info) > 5:
            report["suggestions"].append("Ви використовуєте більше 5 індикаторів. Зменшення кількості змінних може зробити стратегію стабільнішою та зменшити ризик 'підгонки під історію' (overfitting).")

    def _get_name_id(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _get_op_symbol(self, op):
        op_map = {
            ast.Eq: "==", ast.NotEq: "!=",
            ast.Lt: "<", ast.LtE: "<=",
            ast.Gt: ">", ast.GtE: ">="
        }
        return op_map.get(type(op), "?")

    # =========================================================================
    # СИГНАЛЬНИЙ СКАНЕР (АВТОМАТИЗАЦІЯ)
    # =========================================================================
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    # ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): сканування ринків збереженими
    # .py-стратегіями (через _scan_single_market, заморожений вище). Всі
    # виклики цього методу закоментовано в gui/logic/copilot_service.py
    # (CopilotSchedulerThread) і gui/logic/CopilotLogic.py
    # (_on_trigger_signal_scan) — метод недосяжний.
    # Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!

    def scan_markets_for_signals(self, active_strategies_paths: list, notifier=None, target_assets=None, target_timeframes=None):
        import os
        from utils.DataBaseManager import DataBaseManager
        
        from utils.PathManager import PathManager
        
        strategies = {}
        for path in active_strategies_paths:
            clean_path = path[5:] if path.startswith("Code/") else path
            full_path = os.path.join(PathManager.get_user_data_dir(), clean_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                        
                        import re
                        assets_match = re.search(r'TARGET_ASSETS\s*=\s*\[(.*?)\]', code)
                        tf_match = re.search(r'TARGET_TIMEFRAMES\s*=\s*\[(.*?)\]', code)
                        
                        strat_target_assets = [x.strip().strip('"\'') for x in assets_match.group(1).split(',') if x.strip()] if assets_match else (target_assets or [])
                        strat_target_timeframes = [x.strip().strip('"\'') for x in tf_match.group(1).split(',') if x.strip()] if tf_match else (target_timeframes or [])
                        
                        strategies[os.path.basename(clean_path)] = {
                            "code": code,
                            "target_assets": strat_target_assets,
                            "target_timeframes": strat_target_timeframes
                        }
                except Exception as e:
                    print(f"Помилка читання стратегії {path}: {e}")
                    
        if not strategies:
            print("Немає активних стратегій для сканування.")
            return

        kwargs = {'db_path': self.db_path} if self.db_path else {'use_default': True}
        try:
            with DataBaseManager(**kwargs) as db:
                tables = [t for t in db.get_all_tables() if not t.startswith('sqlite') and not t.startswith('copilot_') and not t.startswith('rules_') and not t.startswith('backtest_') and not t.startswith('temp_sim_')]
        except Exception as e:
            print(f"Помилка зчитування таблиць: {e}")
            return
            
        print(f"Сканування {len(tables)} ринків за допомогою {len(strategies)} стратегій...")
        
        args_list = []
        import pandas as pd
        from utils.DataBaseManager import DataBaseManager
        with DataBaseManager(self.db_path) as db:
            for table in tables:
                parts = table.split('_')
                if len(parts) >= 2:
                    table_tf = parts[-1]
                    table_asset = "_".join(parts[:-1])
                else:
                    continue

                df = None
                for strat_name, strat_data in strategies.items():
                    s_assets = strat_data["target_assets"]
                    s_tfs = strat_data["target_timeframes"]
                    
                    if s_assets and table_asset not in s_assets:
                        continue
                    if s_tfs and table_tf not in s_tfs:
                        continue
                        
                    if df is None:
                        df = db.get_data_by_number_range(table, 1000)
                        
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        args_list.append((strat_data["code"], df, table, strat_name))
                
        n_workers = max(1, (os.cpu_count() or 4) - 1)
        results = []
        import multiprocessing
        ctx = multiprocessing.get_context('spawn')
        pool = ctx.Pool(processes=n_workers, maxtasksperchild=10)
        try:
            for i, result in enumerate(pool.imap_unordered(_scan_single_market, args_list)):
                results.append(result)
        finally:
            pool.close()
            pool.join()
                
        import pandas as pd
        
        signals_found_list = []
        warnings_found_list = []
        signals_data = []
        
        for r in results:
            if not r.get("success"): 
                print(f"Помилка сканування {r.get('table')} -> {r.get('strategy')}: {r.get('error')}")
                continue
            
            table = r["table"]
            strat = r["strategy"]
            direction = r.get("direction", "BUY")
            dir_text = "🟢 BUY (Лонг)" if direction == "BUY" else "🔴 SELL (Шорт)"
            
            if r["signal_ready"]:
                signals_found_list.append((table, direction, strat, dir_text))
                signals_data.append({
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "asset": table,
                    "direction": direction,
                    "strategy": strat,
                    "status": "READY"
                })
                print(f"Сигнал: {table} -> {dir_text} -> {strat}")
                    
            elif r["signal_warning"]:
                warnings_found_list.append((table, direction, strat, dir_text))
                signals_data.append({
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "asset": table,
                    "direction": direction,
                    "strategy": strat,
                    "status": "WARNING_75%"
                })
                print(f"Попередження: {table} -> {dir_text} -> {strat}")

        if signals_data:
            try:
                df_signals = pd.DataFrame(signals_data)
                kwargs_db = {'db_path': self.db_path} if self.db_path else {'use_default': True}
                with DataBaseManager(**kwargs_db) as db:
                    db.insert_data_from_pandas_auto("copilot_signals", df_signals)
            except Exception as e:
                print(f"Помилка збереження сигналів в БД: {e}")

        if notifier:
            bo_fixed_time_enabled = False
            bo_fixed_time_minutes = 60
            try:
                import os, json
                from utils.PathManager import PathManager
                config_path = PathManager.get_settings_path()
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        bo_fixed_time_enabled = data.get("trading_mode", {}).get("bo_fixed_time_enabled", False)
                        bo_fixed_time_minutes = data.get("trading_mode", {}).get("bo_fixed_time_minutes", 60)
            except: pass

            if signals_found_list or warnings_found_list:
                msg = f"🚨 <b>Звіт Copilot: Знайдено Сигнали</b> 🚨\n\n"
                for table, direction, strat, dir_text in signals_found_list:
                    msg += f"✅ <b>{table}</b> -> {dir_text}\n   ⚙️ <code>{strat}</code>\n"
                    if bo_fixed_time_enabled:
                        msg += f"   ⏱ <b>Експірація: {bo_fixed_time_minutes} хв.</b> (Фіксовано)\n\n"
                    else:
                        msg += "\n"
                for table, direction, strat, dir_text in warnings_found_list:
                    msg += f"⏳ <i>Увага: {table}</i> -> {dir_text}\n   ⚙️ <code>{strat}</code>\n"
                    if bo_fixed_time_enabled:
                        msg += f"   ⏱ <b>Експірація: {bo_fixed_time_minutes} хв.</b> (Фіксовано)\n\n"
                    else:
                        msg += "\n"
                
                if len(msg) > 4000:
                    msg = msg[:3950] + "\n... (список скорочено)"
                notifier.send_message(msg.strip())

            summary = (
                f"ℹ️ <b>Звіт сканування ринків</b>\n"
                f"📊 Перевірено ринків: {len(tables)}\n"
                f"🧠 Використано стратегій: {len(strategies)}\n"
                f"✅ Готових сигналів: {len(signals_found_list)}\n"
                f"⏳ Формується (75%): {len(warnings_found_list)}"
            )
            notifier.send_message(summary, silent=True)

