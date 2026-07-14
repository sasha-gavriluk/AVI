import pandas as pd
from models.FB.FB import FB
from models.RS.RS import RS
from models.MR.MR import MR

class BOForexLogic:

    #------------------------------
    # Initialization
    #------------------------------

    def __init__(self, df: pd.DataFrame):
        "Завантажуємо моделі в пам'ять один раз при старті"
        self.mr = MR()
        self.fb = FB()
        self.rs = RS()
        
        # Поріг впевненості для генерації сигналу
        self.fb_threshold = 0.75 # Знижено для більшої кількості сигналів після жорсткої фільтрації зонами

        self.df_processed = df.copy()

    #==============================
    # Methods for analysis. Input data
    #==============================

    #------------------------------
    # Generation of data. Market state
    #------------------------------

    def _add_market_regime(self) -> pd.DataFrame:
        "Додає інформацію про стан ринку (MR)"
        return self.mr.process(self.df_processed)

    #------------------------------
    # Generation of data. Support and resistance levels
    #------------------------------

    def _add_support_resistance(self) -> pd.DataFrame:
        "Додає інформацію про рівні підтримки та опору (RS)"
        return self.rs.process(self.df_processed)

    #------------------------------
    # Generation of data. False breakouts
    #------------------------------

    def _add_false_breakouts(self) -> pd.DataFrame:
        "Додає інформацію про хибні пробої (FB)"
        return self.fb.process(self.df_processed)

    #------------------------------
    # Combining data (INPUT DATA)
    #------------------------------

    def _enrich_data(self) -> pd.DataFrame:
        "Єдиний метод, який запускає всі інші для збагачення даних"
        
        # Послідовно пропускаємо через усі мережі
        self.df_processed = self._add_market_regime()
        self.df_processed = self._add_support_resistance()
        self.df_processed = self._add_false_breakouts()
        
        return self.df_processed

    #==============================
    # Methods of Logic
    #==============================

    #------------------------------
    # Triggering FB logic
    #------------------------------

    def _logic_fb_trigger(self) -> pd.DataFrame:
        "Метод логіки: оцінює хибні пробої та рівні, додаючи колонки тригерів до датафрейму"
        df_logic = self.df_processed.copy()
        
        def evaluate_row(row):
            # Аналіз стану ринку (MR)
            states = {'TREND': row.get('MR_Trend', 0.0), 'FLAT': row.get('MR_Flat', 0.0), 'EXPLOSION': row.get('MR_Explosion', 0.0)}
            market_state = max(states, key=states.get)
            
            fb_bull = row.get('FB_Bullish', 0.0)
            fb_bear = row.get('FB_Bearish', 0.0)
            
            sup_prox = row.get('RS_sup_proximity', 0.0)
            sup_str = row.get('RS_sup_strength', 0.0)
            res_prox = row.get('RS_res_proximity', 0.0)
            res_str = row.get('RS_res_strength', 0.0)
            
            if market_state != 'FLAT':
                return pd.Series(['NEUTRAL', 0.0, f"Тригер FB не активний для режиму {market_state}", market_state])
                
            min_strength = 0.20
            
            if fb_bull >= self.fb_threshold and fb_bull > fb_bear:
                if sup_prox > 0.5:
                    if sup_str >= min_strength:
                        return pd.Series(['BUY', fb_bull, None, market_state])
                    else:
                        return pd.Series(['NEUTRAL', 0.0, f"Сигнал BUY ігноровано: зона Підтримки занадто слабка", market_state])
                else:
                    return pd.Series(['NEUTRAL', 0.0, "Сигнал BUY ігноровано: ціна не в зоні Підтримки", market_state])
            
            elif fb_bear >= self.fb_threshold and fb_bear > fb_bull:
                if res_prox > 0.5:
                    if res_str >= min_strength:
                        return pd.Series(['SELL', fb_bear, None, market_state])
                    else:
                        return pd.Series(['NEUTRAL', 0.0, f"Сигнал SELL ігноровано: зона Опору занадто слабка", market_state])
                else:
                    return pd.Series(['NEUTRAL', 0.0, "Сигнал SELL ігноровано: ціна не в зоні Опору", market_state])
                    
            return pd.Series(['NEUTRAL', 0.0, "Немає сильного сигналу від НН", market_state])

        # Застосовуємо логіку та створюємо нові колонки тригеру
        df_logic[['Logic_Signal', 'Logic_Confidence', 'Logic_BlockReason', 'Logic_MarketState']] = df_logic.apply(evaluate_row, axis=1)
        
        return df_logic

    #------------------------------
    # Applying logic triggers
    #------------------------------

    def _apply_logic_triggers(self) -> pd.DataFrame:
        "Єдиний метод, який запускає всі логічні тригери"

        self.df_processed = self._logic_fb_trigger()

        return self.df_processed

    #------------------------------
    # Trigger Calculation
    #------------------------------

    def _calculate_final_signal(self) -> dict:
        "Метод підрахунку тригерів та формування фінального сигналу"
        
        last_row = self.df_processed.iloc[-1]
        
        # 1. Аналіз стану ринку (MR)
        states = {
            'TREND': last_row.get('MR_Trend', 0.0), 
            'FLAT': last_row.get('MR_Flat', 0.0), 
            'EXPLOSION': last_row.get('MR_Explosion', 0.0)
        }
        market_state = max(states, key=states.get)
        
        # Умова щодо EXPLOSION: угоди не беруться до уваги
        if market_state == 'EXPLOSION':
            return {
                "signal": "NEUTRAL",
                "confidence": 0.0,
                "block_reason": "Ринок у стані EXPLOSION. Торги заборонено.",
                "market_state": market_state,
                "active_triggers": 0
            }
            
        buy_triggers = 0
        sell_triggers = 0
        total_confidence = 0.0
        active_triggers = 0
        block_reasons = []

        # 2. При стані MR_Flat активий тригер _logic_fb_trigger
        if market_state == 'FLAT':
            fb_signal = last_row.get('Logic_Signal', 'NEUTRAL')
            fb_conf = last_row.get('Logic_Confidence', 0.0)
            fb_reason = last_row.get('Logic_BlockReason', None)
            
            if fb_signal == 'BUY':
                buy_triggers += 1
                total_confidence += fb_conf
                active_triggers += 1
            elif fb_signal == 'SELL':
                sell_triggers += 1
                total_confidence += fb_conf
                active_triggers += 1
            elif fb_reason:
                block_reasons.append(f"FB: {fb_reason}")

        # Заглушка для стану TREND
        elif market_state == 'TREND':
            block_reasons.append("Для режиму TREND тригери поки не налаштовані.")

        # 3. Метод підрахунку тригерів
        final_signal = 'NEUTRAL'
        final_confidence = 0.0
        final_reason = "Недостатньо тригерів для входу"

        if buy_triggers > sell_triggers:
            final_signal = 'BUY'
            final_confidence = total_confidence / buy_triggers
            final_reason = None
        elif sell_triggers > buy_triggers:
            final_signal = 'SELL'
            final_confidence = total_confidence / sell_triggers
            final_reason = None
        elif active_triggers == 0 and block_reasons:
            final_reason = " | ".join(block_reasons)

        return {
            "signal": final_signal,
            "confidence": round(final_confidence, 3) if final_confidence > 0 else 0.0,
            "block_reason": final_reason,
            "market_state": market_state,
            "active_triggers": active_triggers
        }

    #==============================
    # Main method
    #==============================

    def process(self) -> dict:
        "Єдиний метод, який запускає всі інші для отримання реального сигналу"

        self.df_processed = self._enrich_data()
        self.df_processed = self._apply_logic_triggers()
        
        return self._calculate_final_signal()
        