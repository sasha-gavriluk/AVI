import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from utils.algorithms.WrapCandleEngine import WCE
from utils.OtherUtils import _handle_error

class AlgorithmProcessor:
    "Клас для алгоритмічної обробки та розрахунку рівнів і структур"

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame, algorithm_params=None):
        self.data = data
        self.processed_data = processed_data
        self.algorithm_params = algorithm_params if algorithm_params is not None else []

    #------------------------------
    # NGram Прогнози (AI)
    #------------------------------

    @_handle_error
    def add_ngram_predictions(self, wce_column='WCE_10', ngram_length=3, prediction_road=1):
        "Метод для генерування сигналів на основі NGramAnalyzer"
        from utils.algorithms.NGramAnalyzer import NGramAnalyzer
        from utils.algorithms.WrapCandleEngine import WCE
        
        if wce_column not in self.processed_data.columns and wce_column not in self.data.columns:
            period_str = wce_column.split('_')[-1]
            period = int(period_str) if period_str.isdigit() else 10
            wce = WCE(self.data, period=period)
            self.processed_data[wce_column] = wce.get_combined_sequence_v2()
            
        wce_series = self.processed_data[wce_column] if wce_column in self.processed_data.columns else self.data[wce_column]
        
        try:
            analyzer = NGramAnalyzer(db_manager=None, table_name=None, ngram_length=ngram_length, prediction_road=prediction_road, data_df=self.processed_data, wce_column_name=wce_column)
        except Exception as e:
            print(f"Помилка ініціалізації NGramAnalyzer: {e}. Переконайтесь, що файл прогнозів існує.")
            return

        signals = []
        for token in wce_series:
            if not isinstance(token, str):
                signals.append(0)
                continue
                
            analyzer.history.append(token)
            
            if len(analyzer.history) < analyzer.ngram_length:
                signals.append(0)
                continue
                
            if len(analyzer.history) > analyzer.ngram_length:
                analyzer.history.pop(0)
                
            parsed_hist = tuple(analyzer._parse_token(t) for t in analyzer.history)
            dir_signature = tuple(pt[0] if isinstance(pt, tuple) else pt for pt in parsed_hist)
            
            found_prediction = None
            if dir_signature in analyzer.valid_prefixes:
                for base_parsed in analyzer.signature_index.get(dir_signature, []):
                    is_similar = True
                    for pt1, pt2 in zip(parsed_hist, base_parsed):
                        if type(pt1) != type(pt2):
                            is_similar = False
                            break
                        if isinstance(pt1, tuple):
                            if abs(pt1[1] - pt2[1]) > analyzer.tolerance or \
                               abs(pt1[2] - pt2[2]) > analyzer.tolerance or \
                               abs(pt1[3] - pt2[3]) > analyzer.tolerance:
                                is_similar = False
                                break
                        elif pt1 != pt2:
                            is_similar = False
                            break
                    if is_similar:
                        found_prediction = analyzer.parsed_predictions[base_parsed]
                        break
            
            if found_prediction and len(found_prediction) > 0:
                pred_token = found_prediction[0][0]
                if isinstance(pred_token, (list, tuple)) and len(pred_token) > 0:
                    pred_token = pred_token[0] 
                elif isinstance(pred_token, (list, tuple)):
                    pred_token = 'D'
                    
                if isinstance(pred_token, str):
                    if pred_token.startswith('B'):
                        signals.append(1)
                    elif pred_token.startswith('S'):
                        signals.append(-1)
                    else:
                        signals.append(0)
                else:
                    signals.append(0)
            else:
                signals.append(0)
            
        self.processed_data[f'NGRAM_ROAD_{prediction_road}'] = signals

    #------------------------------
    # WCE Anomaly Detector
    #------------------------------
    
    @_handle_error
    def add_wce_anomaly(self, wce_column='WCE_10', peak_threshold=6, norm_threshold=3):
        "Відстежує аномалії WCE токенів (ефект розтягнутої гумки)"
        from utils.algorithms.WrapCandleEngine import WCE
        from utils.algorithms.WCEAnomalyDetector import WCEAnomalyDetector
        
        if wce_column not in self.processed_data.columns and wce_column not in self.data.columns:
            period_str = wce_column.split('_')[-1]
            period = int(period_str) if period_str.isdigit() else 10
            wce = WCE(self.data, period=period)
            self.processed_data[wce_column] = wce.get_combined_sequence_v2()
            
        data_to_use = self.processed_data if wce_column in self.processed_data.columns else self.data
        
        detector = WCEAnomalyDetector(data_to_use, wce_column, peak_threshold, norm_threshold)
        signals = detector.calculate()
        
        col_name = f'WCE_ANOMALY_{peak_threshold}_{norm_threshold}'
        self.processed_data[col_name] = signals
        
    @_handle_error
    def add_wce_trend_exhaustion(self, wce_column='WCE_10', peak_threshold=15, norm_threshold=3):
        "Відстежує кумулятивні аномалії WCE токенів (параболічне виснаження)"
        from utils.algorithms.WrapCandleEngine import WCE
        from utils.algorithms.WCEAnomalyDetector import WCETrendExhaustionDetector
        
        if wce_column not in self.processed_data.columns and wce_column not in self.data.columns:
            period_str = wce_column.split('_')[-1]
            period = int(period_str) if period_str.isdigit() else 10
            wce = WCE(self.data, period=period)
            self.processed_data[wce_column] = wce.get_combined_sequence_v2()
            
        data_to_use = self.processed_data if wce_column in self.processed_data.columns else self.data
        
        detector = WCETrendExhaustionDetector(data_to_use, wce_column, peak_threshold, norm_threshold)
        signals = detector.calculate()
        
        col_name = f'WCE_TREND_EXHAUSTION_{peak_threshold}_{norm_threshold}'
        self.processed_data[col_name] = signals

    #------------------------------
    # Розрахунок levels
    #------------------------------

    @_handle_error
    def calculate_levels(self):
        "Розрахунок ключових рівнів (підтримка/опір) з різних джерел"
        resistance_levels_list = []
        support_levels_list = []

        res_peaks, sup_peaks = self._find_peaks_levels(prominence=0.5, distance=1)
        if not res_peaks.empty:
            resistance_levels_list.append(res_peaks)
        if not sup_peaks.empty:
            support_levels_list.append(sup_peaks)

        res_fractals, sup_fractals = self._find_fractal_levels()
        if not res_fractals.empty:
            resistance_levels_list.append(res_fractals)
        if not sup_fractals.empty:
            support_levels_list.append(sup_fractals)

        res_pivots, sup_pivots = self.calculate_pivot_points()
        if not res_pivots.empty:
            resistance_levels_list.append(res_pivots)
        if not sup_pivots.empty:
            support_levels_list.append(sup_pivots)

        res_fibo, sup_fibo = self.calculate_fibonacci_levels()
        if not res_fibo.empty:
            resistance_levels_list.append(res_fibo)
        if not sup_fibo.empty:
            support_levels_list.append(sup_fibo)

        if resistance_levels_list and support_levels_list:
            res_clusters, sup_clusters, res_counts, sup_counts = self._combine_levels(
                resistance_levels_list, support_levels_list, clustering_tolerance=0.0005)
            self.significant_resistances, self.significant_supports = self._find_significant_levels(res_clusters, sup_clusters, methods_count=2,
                                                                                          resistance_counts=res_counts, support_counts=sup_counts)

            self.processed_data['Near_Resistance'] = self.processed_data['close'].apply(
                lambda price: self._is_near_level(price, self.significant_resistances)
            )

            self.processed_data['Near_Support'] = self.processed_data['close'].apply(
                lambda price: self._is_near_level(price, self.significant_supports)
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

    #------------------------------
    # Внутрішні методи обробки рівнів
    #------------------------------

    def _is_near_level(self, price, levels, tolerance=0.0005):
        "Перевірка чи ціна знаходиться близько до рівня"
        return any(abs((price - level) / level) <= tolerance for level in levels)

    def _find_peaks_levels(self, prominence=1, distance=5):
        "Пошук рівнів на основі локальних піків та западин"
        peaks, _ = find_peaks(self.data['high'], prominence=prominence, distance=distance)
        resistance_levels = self.data['high'].iloc[peaks]

        troughs, _ = find_peaks(-self.data['low'], prominence=prominence, distance=distance)
        support_levels = self.data['low'].iloc[troughs]

        return resistance_levels, support_levels

    def _find_fractal_levels(self):
        "Пошук рівнів на основі фракталів"
        highs = self.data['high']
        lows = self.data['low']

        upper_fractals = (highs.shift(2) < highs.shift(1)) & (highs.shift(1) < highs) & \
                         (highs > highs.shift(-1)) & (highs.shift(-1) > highs.shift(-2))
        resistance_levels = highs[upper_fractals]

        lower_fractals = (lows.shift(2) > lows.shift(1)) & (lows.shift(1) > lows) & \
                         (lows < lows.shift(-1)) & (lows.shift(-1) < lows.shift(-2))
        support_levels = lows[lower_fractals]

        return resistance_levels, support_levels

    # Залишаємо публічними, оскільки вони можуть викликатись з BacktestAlgorithmProcessor
    def calculate_pivot_points(self):
        "Розрахунок Pivot Points"
        high = self.data['high'].shift(1)
        low = self.data['low'].shift(1)
        close = self.data['close'].shift(1)

        pivot = (high + low + close) / 3
        resistance1 = (2 * pivot) - low
        support1 = (2 * pivot) - high
        resistance2 = pivot + (high - low)
        support2 = pivot - (high - low)

        resistance_levels = pd.concat([resistance1, resistance2]).dropna()
        support_levels = pd.concat([support1, support2]).dropna()

        return resistance_levels, support_levels

    def calculate_fibonacci_levels(self):
        "Розрахунок рівнів Фібоначчі"
        lookback = min(100, len(self.data))
        recent_high = self.data['high'].rolling(window=lookback).max().iloc[-1]
        recent_low = self.data['low'].rolling(window=lookback).min().iloc[-1]

        levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        diff = recent_high - recent_low

        resistance_levels = [recent_high - diff * level for level in levels]
        support_levels = [recent_low + diff * level for level in levels]

        resistance_levels = pd.Series(resistance_levels)
        support_levels = pd.Series(support_levels)

        return resistance_levels, support_levels

    def _combine_levels(self, resistance_levels_list, support_levels_list, clustering_tolerance=0.005):
        """
        Об'єднання та кластеризація рівнів.

        :return: (кластери опору, кластери підтримки, розміри опору, розміри підтримки)
                 Розміри потрібні для _find_significant_levels — без них відібрати
                 значущі рівні неможливо.
        """
        all_resistances = pd.concat(resistance_levels_list)
        all_supports = pd.concat(support_levels_list)

        resistance_clusters, resistance_counts = self._cluster_levels(
            all_resistances, clustering_tolerance, return_counts=True)
        support_clusters, support_counts = self._cluster_levels(
            all_supports, clustering_tolerance, return_counts=True)

        return resistance_clusters, support_clusters, resistance_counts, support_counts

    def _cluster_levels(self, levels, tolerance, return_counts=False):
        """
        Кластеризація близьких рівнів.

        :param return_counts: True — повернути ще й РОЗМІР кожного кластера, тобто
                              скільки сирих рівнів у нього злилось. Саме цей розмір
                              і означає «рівень підтверджений кількома методами»;
                              без нього відібрати значущі рівні неможливо.
        """
        levels = levels.dropna().sort_values().reset_index(drop=True)
        clustered_levels = []
        counts = []

        while not levels.empty:
            level = levels.iloc[0]
            if level == 0:
                close_levels = levels[np.abs(levels - level) <= tolerance]
            else:
                close_levels = levels[np.abs((levels - level) / level) <= tolerance]
            clustered_level = close_levels.mean()
            clustered_levels.append(clustered_level)
            counts.append(len(close_levels))
            levels = levels.drop(close_levels.index).reset_index(drop=True)

        if return_counts:
            return pd.Series(clustered_levels), pd.Series(counts)
        return pd.Series(clustered_levels)

    def _find_significant_levels(self, resistance_clusters, support_clusters, methods_count,
                                 resistance_counts=None, support_counts=None):
        """
        Фільтрація найбільш значущих рівнів: лишаємо ті, у які злилось щонайменше
        methods_count сирих рівнів (тобто рівень підтвердили кілька методів).

        :param resistance_counts: розміри кластерів опору з _cluster_levels(return_counts=True)
        :param support_counts: те саме для підтримок
        """
        def відібрати(кластери, розміри):
            кластери = pd.Series(кластери).reset_index(drop=True)
            if кластери.empty:
                return pd.Index([])
            if розміри is None:
                # Запасний шлях, якщо розміри не передали: рахуємо повтори однакових
                # значень. Після усереднення в _cluster_levels кожне значення унікальне,
                # тож цей шлях нічого не відбере — див. журнал змін унизу файлу.
                розміри = кластери.map(кластери.value_counts())
            розміри = pd.Series(розміри).reset_index(drop=True)
            return pd.Index(кластери[розміри.values >= methods_count])

        return (відібрати(resistance_clusters, resistance_counts),
                відібрати(support_clusters, support_counts))
    
    #------------------------------
    # Виявлення Market Structure
    #------------------------------

    @_handle_error
    def detect_market_structure(self, swing_window=3):
        "Визначення локальних максимумів/мінімумів і побудова структури ринку (HH, HL, LH, LL)"
        highs = self.data['high']
        lows = self.data['low']

        structure = []
        n = len(self.data)

        for i in range(n):
            if i < swing_window or i > n - swing_window - 1:
                structure.append(None)
                continue

            current_high = highs.iloc[i]
            current_low = lows.iloc[i]

            left_highs = highs.iloc[i - swing_window:i]
            right_highs = highs.iloc[i + 1:i + swing_window + 1]
            left_lows = lows.iloc[i - swing_window:i]
            right_lows = lows.iloc[i + 1:i + swing_window + 1]

            local_high = (current_high > left_highs.max()) and (current_high > right_highs.max())
            local_low = (current_low < left_lows.min()) and (current_low < right_lows.min())

            if local_high:
                structure.append('swing_high')
            elif local_low:
                structure.append('swing_low')
            else:
                structure.append(None)

        self.processed_data['Market_Structure_Point'] = structure

        last_swing_price = None
        last_swing_type = None
        structure_type = []

        for i in range(len(self.processed_data)):
            current_point = self.processed_data['Market_Structure_Point'].iloc[i]
            current_price = self.data['close'].iloc[i]

            if pd.notna(current_point):
                if last_swing_price is None:
                    structure_type.append(None)
                else:
                    if current_point == 'swing_high':
                        if current_price > last_swing_price:
                            structure_type.append('HH') 
                        else:
                            structure_type.append('LH') 
                    elif current_point == 'swing_low':
                        if current_price > last_swing_price:
                            structure_type.append('HL') 
                        else:
                            structure_type.append('LL') 
                last_swing_price = current_price
                last_swing_type = current_point
            else:
                structure_type.append(None)

        self.processed_data['Market_Structure_Type'] = structure_type

    #------------------------------
    # Виявлення BOS та CHoCH
    #------------------------------

    @_handle_error
    def detect_bos_choch(self):
        "Визначає Break of Structure (BOS) та Change of Character (CHoCH) на основі структури ринку"
        structure = self.processed_data['Market_Structure_Type']
        close = self.data['close']

        last_hh = None
        last_hl = None
        last_ll = None
        last_lh = None
        trend_direction = None

        bos = []
        choch = []

        for i in range(len(structure)):
            point = structure.iloc[i]
            price = close.iloc[i]

            bos_signal = False
            choch_signal = False

            if point == 'HH':
                if last_hh is None or price > last_hh:
                    last_hh = price
                if trend_direction == 'downtrend' and last_lh is not None and price > last_lh:
                    choch_signal = True
                    trend_direction = 'uptrend'
                elif trend_direction == 'uptrend' and last_hh is not None and price > last_hh:
                    bos_signal = True
                elif trend_direction is None:
                    trend_direction = 'uptrend'

            elif point == 'HL':
                if last_hl is None or price > last_hl:
                    last_hl = price

            elif point == 'LL':
                if last_ll is None or price < last_ll:
                    last_ll = price
                if trend_direction == 'uptrend' and last_hl is not None and price < last_hl:
                    choch_signal = True
                    trend_direction = 'downtrend'
                elif trend_direction == 'downtrend' and last_ll is not None and price < last_ll:
                    bos_signal = True
                elif trend_direction is None:
                    trend_direction = 'downtrend'

            elif point == 'LH':
                if last_lh is None or price < last_lh:
                    last_lh = price

            bos.append(bos_signal)
            choch.append(choch_signal)

        self.processed_data['BOS'] = bos
        self.processed_data['CHoCH'] = choch

    #------------------------------
    # Виявлення Liquidity Sweep
    #------------------------------

    @_handle_error
    def detect_liquidity_sweep(self, swing_window=3, tolerance=0.0005):
        "Виявлення liquidity sweep (зняття ліквідності)"
        highs = self.data['high']
        lows = self.data['low']

        sweep_high = []
        sweep_low = []
        n = len(self.data)

        for i in range(n):
            if i < swing_window or i > n - swing_window - 1:
                sweep_high.append(False)
                sweep_low.append(False)
                continue

            local_high = highs.iloc[i - swing_window : i + swing_window + 1].max()
            local_low = lows.iloc[i - swing_window : i + swing_window + 1].min()

            if highs.iloc[i] > local_high * (1 + tolerance):
                sweep_high.append(True)
            else:
                sweep_high.append(False)

            if lows.iloc[i] < local_low * (1 - tolerance):
                sweep_low.append(True)
            else:
                sweep_low.append(False)

        self.processed_data['Sweep_High'] = sweep_high
        self.processed_data['Sweep_Low'] = sweep_low

    #------------------------------
    # Виявлення Order Blocks
    #------------------------------

    @_handle_error
    def detect_order_blocks(self, body_threshold=0.5, min_body_size=0.0001, max_lifetime=20):
        "Виявлення Order Blocks (остання протилежна свічка перед імпульсом)"
        open_ = self.data['open'].values
        close = self.data['close'].values
        high = self.data['high'].values
        low = self.data['low'].values
        
        n = len(self.data)
        ob_up_signals = np.zeros(n, dtype=bool)
        ob_down_signals = np.zeros(n, dtype=bool)
        
        active_bullish_obs = []
        active_bearish_obs = []
        
        last_bearish_idx = -1
        last_bullish_idx = -1
        
        for i in range(2, n):
            curr_open = open_[i]
            curr_close = close[i]
            curr_high = high[i]
            curr_low = low[i]
            
            active_bullish_obs = [ob for ob in active_bullish_obs if i - ob[2] <= max_lifetime]
            active_bearish_obs = [ob for ob in active_bearish_obs if i - ob[2] <= max_lifetime]
            
            if curr_close < curr_open:
                last_bearish_idx = i
            elif curr_close > curr_open:
                last_bullish_idx = i
                
            mitigated_bullish_idx = []
            for idx, ob in enumerate(active_bullish_obs):
                ob_high, ob_low, _ = ob
                if curr_low <= ob_high:
                    ob_up_signals[i] = True
                    mitigated_bullish_idx.append(idx)
                    
            for idx in reversed(mitigated_bullish_idx):
                active_bullish_obs.pop(idx)
                
            mitigated_bearish_idx = []
            for idx, ob in enumerate(active_bearish_obs):
                ob_high, ob_low, _ = ob
                if curr_high >= ob_low:
                    ob_down_signals[i] = True
                    mitigated_bearish_idx.append(idx)
                    
            for idx in reversed(mitigated_bearish_idx):
                active_bearish_obs.pop(idx)
                
            prev_high = high[i-2]
            prev_low = low[i-2]
            
            gap_up = curr_low > prev_high
            gap_down = curr_high < prev_low
            price = curr_close
            
            if gap_up and (curr_low - prev_high) / price > 0.0001:
                if last_bearish_idx != -1 and last_bearish_idx < i:
                    active_bullish_obs.append((high[last_bearish_idx], low[last_bearish_idx], i))
            elif gap_down and (prev_low - curr_high) / price > 0.0001:
                if last_bullish_idx != -1 and last_bullish_idx < i:
                    active_bearish_obs.append((high[last_bullish_idx], low[last_bullish_idx], i))
                    
        self.processed_data['Bullish_OB'] = ob_up_signals
        self.processed_data['Bearish_OB'] = ob_down_signals

    #------------------------------
    # Виявлення Fair Value Gaps
    #------------------------------

    @_handle_error
    def detect_fair_value_gaps(self, min_gap_ratio=0.0001):
        "Виявляє Fair Value Gaps (імбаланси) між трьома свічками"
        high = self.data['high']
        low = self.data['low']

        fvg_up = []
        fvg_down = []

        for i in range(2, len(self.data)):
            prev_high = high.iloc[i-2]
            prev_low = low.iloc[i-2]

            curr_high = high.iloc[i]
            curr_low = low.iloc[i]

            gap_up = curr_low > prev_high
            gap_down = curr_high < prev_low

            price = self.data['close'].iloc[i]
            if gap_up and (curr_low - prev_high) / price > min_gap_ratio:
                fvg_up.append(True)
                fvg_down.append(False)
            elif gap_down and (prev_low - curr_high) / price > min_gap_ratio:
                fvg_up.append(False)
                fvg_down.append(True)
            else:
                fvg_up.append(False)
                fvg_down.append(False)

        fvg_up = [False, False] + fvg_up
        fvg_down = [False, False] + fvg_down

        self.processed_data['FVG_Up'] = fvg_up
        self.processed_data['FVG_Down'] = fvg_down

    #------------------------------
    # Оркестратор
    #------------------------------

    @_handle_error
    def process_data(self):
        "Головний метод обробки даних (виклик алгоритмів)"
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


# ==========================================================================================
# ЖУРНАЛ ЗМІН, ВНЕСЕНИХ АСИСТЕНТОМ (31.08.2026)
# ==========================================================================================
#
# ЗМІНА — відбір значущих рівнів не працював НІКОЛИ, на будь-яких даних.
#
# БУЛО (оригінал):
#     def _cluster_levels(self, levels, tolerance):
#         ...
#         clustered_level = close_levels.mean()
#         clustered_levels.append(clustered_level)
#         ...
#         return pd.Series(clustered_levels)
#
#     def _find_significant_levels(self, resistance_clusters, support_clusters, methods_count):
#         resistance_levels = resistance_clusters.value_counts()
#         significant_resistances = resistance_levels[resistance_levels >= methods_count].index
#
# СТАЛО: _cluster_levels уміє повертати РОЗМІР кожного кластера (return_counts=True),
#        _combine_levels передає ці розміри далі, а _find_significant_levels відбирає
#        рівні за розміром кластера, а не за повторами значень.
#
# ЧОМУ (причина помилки):
# _cluster_levels зводить кожну групу близьких рівнів в ОДНЕ усереднене число. Отже
# кожне значення в результаті унікальне. А _find_significant_levels рахувало повтори
# однакових значень через value_counts() і лишало ті, що трапились >= methods_count разів.
# Унікальне значення не може трапитись двічі, тож умова не виконувалась ніколи.
#
# Заміряно на SOLUSDT (6000 свічок) ДО правки:
#     сирих рівнів опору (піки + фрактали): 3585
#     кластерів після злиття:                426
#     максимальна кількість повторів:          1
#     кластерів із лічильником >= 2:           0   <- фільтр не пропускав нічого
# Наслідок: significant_resistances і significant_supports завжди порожні, звідси
# Near_Resistance = Near_Support = False у 100% рядків, а Nearest_Resistance_Price і
# Nearest_Support_Price заповнені на 0.0% рядків. Це тривало непомітно, бо симптом
# виглядав як «фіча слабка», а не як помилка.
#
# ПІСЛЯ правки на тих самих даних: 669 значущих опорів, 661 підтримка.
#
# УВАГА, ЩО ЛИШИЛОСЬ НЕВИРІШЕНИМ (свідомо не чіпав — це рішення з теханалізу, не з коду):
# Допуск злиття кластерів дорівнює допуску «біля рівня» — обидва 0.0005, тобто 0.05%.
# Через це кожен кластер стає власним околом, рівнів виходять сотні, і ціна майже
# завжди біля якогось. Тобто Near_Resistance тепер істинний у 98.9% рядків — фіча
# з «завжди нуль» стала «завжди одиниця», і користі так само немає.
#
# Заміряно, як це залежить від допуску злиття (мін. методів = 2):
#     допуск 0.05%  ->  387 рівнів  ->  ціна біля рівня у 91.8% свічок  (зараз)
#     допуск 0.20%  ->  153 рівні   ->  45.4%
#     допуск 0.50%  ->   76 рівнів  ->  20.0%
#     допуск 1.00%  ->   42 рівні   ->   9.0%
# Розумним виглядає допуск злиття 0.5% при незмінному допуску «біля рівня» 0.05%,
# але вибір за господарем: це питання про те, що вважати ОДНИМ І ТИМ САМИМ рівнем.
#
# ПЕРЕНАВЧАННЯ ПІСЛЯ ЦІЄЇ ПРАВКИ НЕ ПРОВОДИЛОСЬ. Датасети, зібрані до 31.08.2026,
# містять стару (порожню) версію Near_* і Nearest_*_Price. Щоб зміна дійшла до
# мережі, датасет треба перезібрати.
#
# Оригінали перед правкою: scratchpad/AlgorithmProcessor.py.bak,
# scratchpad/BacktestAlgorithmProcessor.py.bak
# ==========================================================================================
