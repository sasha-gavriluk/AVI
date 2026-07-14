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



    def detect_liquidity_sweep(self, swing_window=3, tolerance=0.0005):
        highs = self.processed_data['high']
        lows = self.processed_data['low']
        past_highs = highs.shift(1).rolling(window=swing_window, min_periods=1).max()
        past_lows = lows.shift(1).rolling(window=swing_window, min_periods=1).min()
        
        self.processed_data['Sweep_High'] = highs > past_highs * (1 + tolerance)
        self.processed_data['Sweep_Low'] = lows < past_lows * (1 - tolerance)
        self.processed_data['Sweep_High'] = self.processed_data['Sweep_High'].fillna(False)
        self.processed_data['Sweep_Low'] = self.processed_data['Sweep_Low'].fillna(False)

    def detect_market_structure(self):
        self.find_fractal_levels()
        
        n = len(self.processed_data)
        points = [None] * n
        types = [None] * n
        hl_flags = [0] * n
        
        last_high_val = -np.inf
        last_low_val = np.inf
        
        highs = self.processed_data['high'].values
        lows = self.processed_data['low'].values
        fh = self.processed_data['Fractal_High'].values
        fl = self.processed_data['Fractal_Low'].values
        
        for i in range(n):
            if fh[i]:
                points[i] = 'swing_high'
                if highs[i] > last_high_val:
                    types[i] = 'HH'
                    hl_flags[i] = 1
                else:
                    types[i] = 'LH'
                    hl_flags[i] = -1
                last_high_val = highs[i]
                last_low_val = np.inf 
            elif fl[i]:
                points[i] = 'swing_low'
                if lows[i] < last_low_val:
                    types[i] = 'LL'
                    hl_flags[i] = -1
                else:
                    types[i] = 'HL'
                    hl_flags[i] = 1
                last_low_val = lows[i]
                last_high_val = -np.inf 
            else:
                if i > 0:
                    types[i] = types[i-1]
                    hl_flags[i] = hl_flags[i-1]
                    
        self.processed_data['Market_Structure_Point'] = points
        self.processed_data['Market_Structure_Type'] = types
        self.processed_data['Highs_Lows'] = hl_flags

    def detect_bos_choch(self):
        if 'Market_Structure_Type' not in self.processed_data.columns:
            self.detect_market_structure()
            
        n = len(self.processed_data)
        bos = [False] * n
        choch = [False] * n
        
        trend_dir = None
        last_hh = None
        last_hl = None
        last_ll = None
        last_lh = None
        
        types = self.processed_data['Market_Structure_Type'].values
        closes = self.processed_data['close'].values
        
        for i in range(n):
            point = types[i]
            price = closes[i]
            prev_point = types[i-1] if i > 0 else None
            
            if point is not None and point != prev_point:
                if point == 'HH':
                    if last_hh is None or price > last_hh: last_hh = price
                    if trend_dir == 'downtrend' and last_lh is not None and price > last_lh:
                        choch[i] = True
                        trend_dir = 'uptrend'
                    elif trend_dir == 'uptrend' and last_hh is not None and price > last_hh:
                        bos[i] = True
                    elif trend_dir is None:
                        trend_dir = 'uptrend'
                elif point == 'HL':
                    if last_hl is None or price > last_hl: last_hl = price
                elif point == 'LL':
                    if last_ll is None or price < last_ll: last_ll = price
                    if trend_dir == 'uptrend' and last_hl is not None and price < last_hl:
                        choch[i] = True
                        trend_dir = 'downtrend'
                    elif trend_dir == 'downtrend' and last_ll is not None and price < last_ll:
                        bos[i] = True
                    elif trend_dir is None:
                        trend_dir = 'downtrend'
                elif point == 'LH':
                    if last_lh is None or price < last_lh: last_lh = price
                    
        self.processed_data['BOS'] = bos
        self.processed_data['CHoCH'] = choch

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

