import pandas as pd
import re
from utils.algorithms.DataProcessing import IndicatorProcessor, PatternDetector, AlgorithmProcessor

class IndicatorRegistry:
    """
    Реєстр, який з'єднує наші ООП-правила з реальними даними (Pandas DataFrame).
    Підтримує 'Ліниві обчислення' (Lazy Evaluation): якщо індикатора немає, 
    він створюється автоматично через IndicatorProcessor, PatternDetector або AlgorithmProcessor.
    """
    _static_cache = {}
    _cached_df_hash = None
    
    def __init__(self, data: pd.DataFrame, is_backtest: bool = False):
        # Надійний хеш: кількість рядків + timestamp першого і останнього + сума цін закриття
        try:
            t1 = data['timestamp'].iloc[0] if 'timestamp' in data.columns else 0
            t2 = data['timestamp'].iloc[-1] if 'timestamp' in data.columns else 0
            c_sum = data['close'].sum() if 'close' in data.columns else 0
            df_hash = hash((data.shape[0], data.shape[1], t1, t2, c_sum, is_backtest))
        except Exception:
            df_hash = hash((data.shape[0], data.shape[1], is_backtest))
            
        if df_hash != IndicatorRegistry._cached_df_hash:
            IndicatorRegistry._static_cache = {}
            IndicatorRegistry._cached_df_hash = df_hash
        self._cache = IndicatorRegistry._static_cache
        
        # Робимо копію, щоб не змінювати оригінальний об'єкт (Best Practice)
        self.data = data.copy()
        
        # ЄДИНИЙ спільний DataFrame для результатів
        self.processed_data = self.data
        
        # Ініціалізуємо процесори, передаючи їм СПІЛЬНИЙ об'єкт
        self.processor = IndicatorProcessor(data=self.data, processed_data=self.processed_data)
        self.pattern_detector = PatternDetector(data=self.data, processed_data=self.processed_data)
        
        if is_backtest:
            from utils.algorithms.indicators.BacktestAlgorithmProcessor import BacktestAlgorithmProcessor
            self.algorithm_processor = BacktestAlgorithmProcessor(data=self.data, processed_data=self.processed_data)
        else:
            self.algorithm_processor = AlgorithmProcessor(data=self.data, processed_data=self.processed_data)

    def get_indicator(self, name: str):
        """Отримує колонку з датафрейму за її назвою (з кешу). Якщо немає - генерує."""
        if name in self._cache:
            return self._cache[name]
            
        series = self._calculate_indicator(name)
        self._cache[name] = series
        return series

    def _calculate_indicator(self, name: str):
        """Внутрішній метод генерації індикатора"""
        if name in self.data.columns:
            return self.data[name]
        
        # ЛІНИВІ ОБЧИСЛЕННЯ
        print(f"[Registry] Індикатор '{name}' не знайдено. Генерую 'на льоту'...")
        
        # Розбиваємо назву на текстові та числові частини (напр. 'MACD_Signal_12_26_9')
        parts = name.split('_')
        text_parts = []
        num_parts = []
        for p in parts:
            try:
                f_val = float(p)
                if f_val.is_integer():
                    num_parts.append(int(f_val))
                else:
                    num_parts.append(f_val)
            except ValueError:
                text_parts.append(p)
                
        base_name = "_".join(text_parts).upper()
        
        # 1. Прості індикатори з 1 параметром (період)
        if base_name in ['SMA', 'EMA', 'RSI', 'ATR', 'CCI', 'ADX', 'WILLIAMSR', 'VOLUME_AVG']:
            if num_parts:
                period = num_parts[0]
                if base_name == 'SMA': self.processor.add_sma(period)
                elif base_name == 'EMA': self.processor.add_ema(period)
                elif base_name == 'RSI': self.processor.add_rsi(period)
                elif base_name == 'ATR': self.processor.add_atr(period)
                elif base_name == 'CCI': self.processor.add_cci(period)
                elif base_name == 'ADX': self.processor.add_adx(period)
                elif base_name == 'WILLIAMSR': self.processor.add_williamsr(period)
                elif base_name == 'VOLUME_AVG': self.processor.add_volume_avg(period)

        # 2. Індикатори перетину (Cross) з 2 параметрами
        elif base_name in ['SMA_CROSS', 'EMA_CROSS']:
            if len(num_parts) >= 2:
                if base_name == 'SMA_CROSS': self.processor.add_sma_cross(num_parts[0], num_parts[1])
                elif base_name == 'EMA_CROSS': self.processor.add_ema_cross(num_parts[0], num_parts[1])

        # 3. Стохастик (потребує k_period та d_period)
        elif base_name in ['STOCHASTIC', 'STOCHASTIC_K', 'STOCHASTIC_D']:
            k = num_parts[0] if len(num_parts) >= 1 else 14
            d = num_parts[1] if len(num_parts) >= 2 else 3
            self.processor.add_stochastic(k_period=k, d_period=d)
            # Повертаємо K-лінію (основна)
            matching = [c for c in self.data.columns if f'stochastic_k_{k}'.lower() in c.lower()]
            if matching:
                return self.data[matching[0]]

        # 4. MACD (потребує fast, slow, signal)
        elif base_name in ['MACD', 'MACD_SIGNAL', 'MACD_HIST']:
            if len(num_parts) >= 3:
                self.processor.add_macd(num_parts[0], num_parts[1], num_parts[2])
            else:
                self.processor.add_macd() # дефолтні 12, 26, 9

        # 5. Bollinger Bands
        elif base_name in ['BOLLINGER_UPPER', 'BOLLINGER_LOWER', 'BOLLINGER_MIDDLE']:
            if len(num_parts) >= 2:
                self.processor.add_bollinger_bands(period=num_parts[0], std_multiplier=num_parts[1])
            elif len(num_parts) == 1:
                self.processor.add_bollinger_bands(period=num_parts[0])

        # 6. Keltner Channel
        elif base_name in ['KELTNER_UPPER', 'KELTNER_LOWER', 'KELTNER_MIDDLE']:
            if num_parts:
                self.processor.add_keltner_channel(period=num_parts[0])

        # 7. Кластеризація (наш новий метод)
        elif base_name in ['MARKET_STATE_LINEAR', 'MARKET_SLOPE', 'MARKET_VOLRATIO']:
            period = num_parts[0] if num_parts else 20
            self.processor.add_market_state_linear(period=period)
            # Повертаємо відповідну колонку залежно від запиту
            target_prefix = {
                'MARKET_STATE_LINEAR': f'Market_State_Linear_{period}',
                'MARKET_SLOPE': f'Market_Slope_{period}',
                'MARKET_VOLRATIO': f'Market_VolRatio_{period}',
            }.get(base_name, f'Market_State_Linear_{period}')
            matching = [c for c in self.data.columns if target_prefix.lower() in c.lower()]
            if matching:
                return self.data[matching[0]]

        # 8. Свічкові патерни (без чисел у назві)
        elif base_name in ['HAMMER', 'INVERTED_HAMMER', 'SHOOTING_STAR', 'ENGULFING', 
                           'MORNING_STAR', 'EVENING_STAR', 'PIERCING_PATTERN', 
                           'DARK_CLOUD_COVER', 'THREE_WHITE_SOLDIERS', 'THREE_BLACK_CROWS', 'HANGING_MAN']:
            pattern_methods = {
                'HAMMER': self.pattern_detector.detect_hammer,
                'INVERTED_HAMMER': self.pattern_detector.detect_inverted_hammer,
                'SHOOTING_STAR': self.pattern_detector.detect_shooting_star,
                'ENGULFING': self.pattern_detector.detect_engulfing,
                'MORNING_STAR': self.pattern_detector.detect_morning_star,
                'EVENING_STAR': self.pattern_detector.detect_evening_star,
                'PIERCING_PATTERN': self.pattern_detector.detect_piercing_pattern,
                'DARK_CLOUD_COVER': self.pattern_detector.detect_dark_cloud_cover,
                'THREE_WHITE_SOLDIERS': self.pattern_detector.detect_three_white_soldiers,
                'THREE_BLACK_CROWS': self.pattern_detector.detect_three_black_crows,
                'HANGING_MAN': self.pattern_detector.detect_hanging_man,
            }
            pattern_methods[base_name]()
            
            for col in self.data.columns:
                if col.upper() == base_name:
                    return self.data[col].astype(bool)

        # 9. Алгоритмічні фічі (AlgorithmProcessor)
        elif base_name in ['BOS', 'CHOCH', 'LIQUIDITY_SWEEP', 'ORDER_BLOCK', 'ORDER_BLOCKS', 'FVG', 'MARKET_STRUCTURE']:
            if base_name in ['BOS', 'CHOCH']:
                if 'Market_Structure_Type' not in self.processed_data.columns:
                    self.algorithm_processor.detect_market_structure()
                self.algorithm_processor.detect_bos_choch()
            elif base_name == 'LIQUIDITY_SWEEP':
                self.algorithm_processor.detect_liquidity_sweep()
                if 'LIQUIDITY_SWEEP' not in self.processed_data.columns:
                    self.processed_data['LIQUIDITY_SWEEP'] = self.processed_data['Sweep_High'] | self.processed_data['Sweep_Low']
            elif base_name in ['ORDER_BLOCK', 'ORDER_BLOCKS']:
                self.algorithm_processor.detect_order_blocks()
                # ORDER_BLOCKS повертає агрегований сигнал: 1 (бичачий), -1 (ведмежий), 0
                if 'Bullish_OB' in self.data.columns and 'Bearish_OB' in self.data.columns:
                    bull = self.data['Bullish_OB'].astype(int)
                    bear = self.data['Bearish_OB'].astype(int)
                    self.data['ORDER_BLOCKS'] = bull - bear
                    return self.data['ORDER_BLOCKS']
            elif base_name == 'FVG':
                self.algorithm_processor.detect_fair_value_gaps()
            elif base_name == 'MARKET_STRUCTURE':
                self.algorithm_processor.detect_market_structure()

        # 10. WCE (Wrap Candle Engine)
        elif base_name == 'WCE':
            period = num_parts[0] if num_parts else 10
            self.processor.add_wce(period=period)
            matching = [c for c in self.data.columns if f'wce_{period}'.lower() in c.lower()]
            if matching:
                return self.data[matching[0]]

        # 11. NGram Прогнози
        elif base_name == 'NGRAM_ROAD':
            road = num_parts[0] if num_parts else 1
            self.algorithm_processor.add_ngram_predictions(prediction_road=road)
            col = f'NGRAM_ROAD_{road}'
            if col in self.data.columns:
                return self.data[col]

        # 12. WCE Anomaly
        elif base_name == 'WCE_ANOMALY':
            peak = num_parts[0] if len(num_parts) > 0 else 6
            norm = num_parts[1] if len(num_parts) > 1 else 3
            self.algorithm_processor.add_wce_anomaly(peak_threshold=peak, norm_threshold=norm)
            col = f'WCE_ANOMALY_{peak}_{norm}'
            if col in self.data.columns:
                return self.data[col]

        # Перевірка результату після генерації індикаторів (не патернів)
        if name in self.data.columns:
            return self.data[name]
        
        # Fuzzy-пошук: шукаємо колонку, назва якої є ПОЧАТКОМ нашого запиту
        # Це дозволяє RSI_14 знаходитись при запиті RSI_14_70_30
        name_lower = name.lower().replace('.', '_')
        matching_cols = [
            c for c in self.data.columns
            if name_lower.startswith(c.lower().replace('.', '_')) or c.lower().replace('.', '_').startswith(name_lower)
        ]
        if matching_cols:
            # Обираємо найдовший збіг (точніший)
            matching_cols.sort(key=lambda c: len(c), reverse=True)
            return self.data[matching_cols[0]]

        raise ValueError(f"Індикатор '{name}' не знайдено, і авто-генератор не зміг його створити.")
        
    def execute_rule(self, rule_expression):
        """
        Виконує правило і повертає булеву маску (Pandas Series з True/False).
        """
        return rule_expression.evaluate(self)
