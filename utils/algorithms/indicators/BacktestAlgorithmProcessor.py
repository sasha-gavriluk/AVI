import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE
from utils.algorithms.indicators.AlgorithmProcessor import AlgorithmProcessor

class BacktestAlgorithmProcessor(AlgorithmProcessor):
    """
    Спеціалізований клас для обробки алгоритмічних фіч під час бектестування.
    Векторизована версія, яка обробляє весь DataFrame (історичні дані) без заглядання в майбутнє.
    """
    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame, algorithm_params=None, fractal_window=2):
        super().__init__(data, processed_data, algorithm_params)
        self.fractal_window = fractal_window 

    def find_fractal_levels(self):
        w = self.fractal_window
        highs = self.processed_data['high']
        lows = self.processed_data['low']
        rolling_max = highs.rolling(window=w+1, min_periods=1).max()
        rolling_min = lows.rolling(window=w+1, min_periods=1).min()
        self.processed_data['Fractal_High'] = (highs == rolling_max) & highs.notna()
        self.processed_data['Fractal_Low'] = (lows == rolling_min) & lows.notna()

    def find_peaks_levels(self, prominence=1, distance=5):
        highs = self.processed_data['high']
        lows = self.processed_data['low']
        rolling_max = highs.rolling(window=distance+1, min_periods=1).max()
        rolling_min = lows.rolling(window=distance+1, min_periods=1).min()
        self.processed_data['Peak_High'] = (highs == rolling_max) & highs.notna()
        self.processed_data['Peak_Low'] = (lows == rolling_min) & lows.notna()
        return self.processed_data['high'][self.processed_data['Peak_High']], self.processed_data['low'][self.processed_data['Peak_Low']]



    def detect_market_structure(self):
        n = len(self.processed_data)
        w = self.fractal_window
        
        highs = self.processed_data['high'].values
        lows = self.processed_data['low'].values
        closes = self.processed_data['close'].values
        
        # Векторизований пошук справжніх фракталів (історичний факт)
        high_series = self.processed_data['high']
        low_series = self.processed_data['low']
        rolling_max = high_series.rolling(window=2*w+1, center=True, min_periods=1).max()
        rolling_min = low_series.rolling(window=2*w+1, center=True, min_periods=1).min()
        
        fh_array = (high_series == rolling_max).values
        fl_array = (low_series == rolling_min).values
        
        # Масиви для результатів
        ms_point = [None] * n
        ms_type = [None] * n
        hl_flags = [0] * n
        bos = [False] * n
        choch = [False] * n
        sweep_high = [False] * n
        sweep_low = [False] * n
        
        # Стан
        active_swing_high = np.nan
        active_swing_low = np.nan
        prev_peak = np.nan
        prev_valley = np.nan
        trend_dir = None
        
        for i in range(w, n):
            # 1. Відкриваємо (підтверджуємо) фрактал, який відбувся w свічок тому
            if fh_array[i-w]:
                peak_price = highs[i-w]
                ms_point[i-w] = 'swing_high'
                
                # Уникаємо дублювання однакових піків підряд
                if np.isnan(prev_peak) or peak_price != prev_peak:
                    if np.isnan(prev_peak) or peak_price > prev_peak:
                        ms_type[i-w] = 'HH'
                        hl_flags[i-w] = 1
                    else:
                        ms_type[i-w] = 'LH'
                        hl_flags[i-w] = -1
                    prev_peak = peak_price
                
                active_swing_high = peak_price
                
            if fl_array[i-w]:
                valley_price = lows[i-w]
                ms_point[i-w] = 'swing_low'
                
                if np.isnan(prev_valley) or valley_price != prev_valley:
                    if np.isnan(prev_valley) or valley_price < prev_valley:
                        ms_type[i-w] = 'LL'
                        hl_flags[i-w] = -1
                    else:
                        ms_type[i-w] = 'HL'
                        hl_flags[i-w] = 1
                    prev_valley = valley_price
                    
                active_swing_low = valley_price
                
            # 2. Перевірка на Liquidity Sweep (Turtle Soup)
            curr_high = highs[i]
            curr_low = lows[i]
            curr_close = closes[i]
            
            if not np.isnan(active_swing_high):
                if curr_high > active_swing_high and curr_close <= active_swing_high:
                    sweep_high[i] = True
                    
            if not np.isnan(active_swing_low):
                if curr_low < active_swing_low and curr_close >= active_swing_low:
                    sweep_low[i] = True
                    
            # 3. Перевірка на BOS / CHoCH
            if not np.isnan(active_swing_high) and curr_close > active_swing_high:
                if trend_dir == 'downtrend':
                    choch[i] = True
                    trend_dir = 'uptrend'
                else:
                    bos[i] = True
                    trend_dir = 'uptrend'
                active_swing_high = np.nan # Злам відбувся, рівень пробито
                
            if not np.isnan(active_swing_low) and curr_close < active_swing_low:
                if trend_dir == 'uptrend':
                    choch[i] = True
                    trend_dir = 'downtrend'
                else:
                    bos[i] = True
                    trend_dir = 'downtrend'
                active_swing_low = np.nan
                
        # Записуємо в DataFrame
        self.processed_data['Market_Structure_Point'] = ms_point
        self.processed_data['Market_Structure_Type'] = ms_type
        self.processed_data['Highs_Lows'] = hl_flags
        self.processed_data['BOS'] = bos
        self.processed_data['CHoCH'] = choch
        self.processed_data['Sweep_High'] = sweep_high
        self.processed_data['Sweep_Low'] = sweep_low

    def detect_bos_choch(self):
        # Вже розраховано в detect_market_structure для гарантії синхронізації
        pass

    def detect_liquidity_sweep(self, swing_window=3, tolerance=0.0005):
        # Вже розраховано в detect_market_structure
        pass

    def calculate_levels(self):
        self.find_fractal_levels()
        self.find_peaks_levels()
        
        resistance_levels_list = []
        support_levels_list = []

        res_peaks = self.processed_data['high'][self.processed_data['Peak_High']]
        sup_peaks = self.processed_data['low'][self.processed_data['Peak_Low']]
        if not res_peaks.empty: resistance_levels_list.append(res_peaks)
        if not sup_peaks.empty: support_levels_list.append(sup_peaks)

        res_fractals = self.processed_data['high'][self.processed_data['Fractal_High']]
        sup_fractals = self.processed_data['low'][self.processed_data['Fractal_Low']]
        if not res_fractals.empty: resistance_levels_list.append(res_fractals)
        if not sup_fractals.empty: support_levels_list.append(sup_fractals)

        res_pivots, sup_pivots = super().calculate_pivot_points()
        if not res_pivots.empty: resistance_levels_list.append(res_pivots)
        if not sup_pivots.empty: support_levels_list.append(sup_pivots)

        res_fibo, sup_fibo = super().calculate_fibonacci_levels()
        if not res_fibo.empty: resistance_levels_list.append(res_fibo)
        if not sup_fibo.empty: support_levels_list.append(sup_fibo)

        if resistance_levels_list or support_levels_list:
            all_resistances = pd.concat(resistance_levels_list).dropna() if resistance_levels_list else pd.Series()
            all_supports = pd.concat(support_levels_list).dropna() if support_levels_list else pd.Series()

            res_clusters = self.cluster_levels(all_resistances, tolerance=0.0005) 
            sup_clusters = self.cluster_levels(all_supports, tolerance=0.0005) 

            self.significant_resistances, self.significant_supports = self.find_significant_levels(res_clusters, sup_clusters, methods_count=2)

            self.processed_data['Near_Resistance'] = self.processed_data['close'].apply(
                lambda price: self.is_near_level(price, self.significant_resistances)
            )
            self.processed_data['Near_Support'] = self.processed_data['close'].apply(
                lambda price: self.is_near_level(price, self.significant_supports)
            )

            def get_nearest_resistance(price):
                res = [r for r in self.significant_resistances if r > price]
                return min(res) if res else np.nan

            def get_nearest_support(price):
                sup = [s for s in self.significant_supports if s < price]
                return max(sup) if sup else np.nan

            self.processed_data['Nearest_Resistance_Price'] = self.processed_data['close'].apply(get_nearest_resistance)
            self.processed_data['Nearest_Support_Price'] = self.processed_data['close'].apply(get_nearest_support)
        else:
            self.processed_data['Near_Resistance'] = False
            self.processed_data['Near_Support'] = False
            self.processed_data['Nearest_Resistance_Price'] = np.nan
            self.processed_data['Nearest_Support_Price'] = np.nan

    def process_data(self):
        algo_methods = {
            'Levels': self.calculate_levels,
            'Market_Structure': self.detect_market_structure,
            'BOS_CHoCH': self.detect_bos_choch,
            'Liquidity_Sweep': self.detect_liquidity_sweep,
            'Order_Blocks': self.detect_order_blocks,
            'Fair_Value_Gaps': self.detect_fair_value_gaps,
            'WCE_Anomaly': self.add_wce_anomaly,
            'WCE_Trend_Exhaustion': self.add_wce_trend_exhaustion,
        }

        if self.algorithm_params:
            for name in self.algorithm_params:
                key = name if isinstance(name, str) else name.get("name")
                if key in algo_methods:
                    algo_methods[key]()
                else:
                    print(f"Алгоритмічна функція '{key}' не підтримується.")
        else:
            for method in algo_methods.values():
                method()

        return self.processed_data

