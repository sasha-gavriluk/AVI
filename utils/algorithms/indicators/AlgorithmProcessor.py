import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from utils.algorithms.WrapCandleEngine import WCE

class AlgorithmProcessor:
    """Клас для алгоритмічної обробки та розрахунку рівнів"""
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame, algorithm_params=None):
        """Ініціалізація"""
        self.data = data
        self.processed_data = processed_data
        self.algorithm_params = algorithm_params if algorithm_params is not None else []

    # ----------------------------------
    # NGram Прогнози (AI)
    # ----------------------------------

    def add_ngram_predictions(self, wce_column='WCE_10', ngram_length=3, prediction_road=1):
        """
        Метод для генерування сигналів на основі NGramAnalyzer.
        Приймає на вхід колонку WCE та проганяє її через аналізатор.
        """
        from utils.algorithms.NGramAnalyzer import NGramAnalyzer
        from utils.algorithms.WrapCandleEngine import WCE
        
        # Перевіряємо чи є колонка WCE
        if wce_column not in self.processed_data.columns and wce_column not in self.data.columns:
            # Якщо немає, генеруємо її з дефолтним періодом (наприклад 10)
            period_str = wce_column.split('_')[-1]
            period = int(period_str) if period_str.isdigit() else 10
            wce = WCE(self.data, period=period)
            self.processed_data[wce_column] = wce.get_combined_sequence_v2()
            
        wce_series = self.processed_data[wce_column] if wce_column in self.processed_data.columns else self.data[wce_column]
        
        try:
            # Ініціалізуємо аналізатор (без доступу до БД, вимагає вже згенерованого json-файлу або передаємо data_df для генерації)
            analyzer = NGramAnalyzer(db_manager=None, table_name=None, ngram_length=ngram_length, prediction_road=prediction_road, data_df=self.processed_data, wce_column_name=wce_column)
        except Exception as e:
            print(f"Помилка ініціалізації NGramAnalyzer: {e}. Переконайтесь, що файл прогнозів існує.")
            return

        signals = []
        for token in wce_series:
            # Якщо токен N000 або подібний
            if not isinstance(token, str):
                signals.append(0)
                continue
                
            analyzer.history.append(token)
            
            # Якщо історія ще не заповнена
            if len(analyzer.history) < analyzer.ngram_length:
                signals.append(0)
                continue
                
            # Симулюємо логіку з analyze
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
            
            # Інтерпретуємо сигнал
            if found_prediction and len(found_prediction) > 0:
                pred_token = found_prediction[0][0]
                if isinstance(pred_token, (list, tuple)) and len(pred_token) > 0:
                    pred_token = pred_token[0] # беремо найімовірніший напрямок
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

    # ----------------------------------
    # WCE Anomaly Detector
    # ----------------------------------
    
    def add_wce_anomaly(self, wce_column='WCE_10', peak_threshold=6, norm_threshold=3):
        """
        Відстежує аномалії WCE токенів (ефект розтягнутої гумки).
        """
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

    # ----------------------------------
    # Розрахунок levels
    # ----------------------------------

    def calculate_levels(self):
        """Розрахунок levels"""
        resistance_levels_list = []
        support_levels_list = []

        # Метод 1: Піки та западини
        res_peaks, sup_peaks = self.find_peaks_levels(prominence=0.5, distance=1)
        if not res_peaks.empty:
            resistance_levels_list.append(res_peaks)
        if not sup_peaks.empty:
            support_levels_list.append(sup_peaks)

        # Метод 2: Фрактали
        res_fractals, sup_fractals = self.find_fractal_levels()
        if not res_fractals.empty:
            resistance_levels_list.append(res_fractals)
        if not sup_fractals.empty:
            support_levels_list.append(sup_fractals)

        # Метод 3: Pivot Points
        res_pivots, sup_pivots = self.calculate_pivot_points()
        if not res_pivots.empty:
            resistance_levels_list.append(res_pivots)
        if not sup_pivots.empty:
            support_levels_list.append(sup_pivots)

        # Метод 4: Фібоначчі
        res_fibo, sup_fibo = self.calculate_fibonacci_levels()
        if not res_fibo.empty:
            resistance_levels_list.append(res_fibo)
        if not sup_fibo.empty:
            support_levels_list.append(sup_fibo)

        # Перевірка, чи є рівні для комбінування
        if resistance_levels_list and support_levels_list:
            # Комбінування рівнів
            res_clusters, sup_clusters = self.combine_levels(resistance_levels_list, support_levels_list, clustering_tolerance=0.005)

            # Знаходимо значущі рівні (підтверджені як мінімум одним методом)
            self.significant_resistances, self.significant_supports = self.find_significant_levels(res_clusters, sup_clusters, methods_count=1)

            # Додаємо логічні колонки, які показують, чи ціна близька до рівнів
            self.processed_data['Near_Resistance'] = self.processed_data['close'].apply(
                lambda price: self.is_near_level(price, self.significant_resistances)
            )

            self.processed_data['Near_Support'] = self.processed_data['close'].apply(
                lambda price: self.is_near_level(price, self.significant_supports)
            )
        else:
            print("No levels found to combine.")
            self.processed_data['Near_Resistance'] = False
            self.processed_data['Near_Support'] = False

    # ----------------------------------
    # Перевірка near level
    # ----------------------------------

    def is_near_level(self, price, levels, tolerance=0.005):
        """Перевірка near level"""
        return any(abs((price - level) / level) <= tolerance for level in levels)

    # ----------------------------------
    # Пошук peaks levels
    # ----------------------------------

    def find_peaks_levels(self, prominence=1, distance=5):
        """Пошук peaks levels"""
        # Опір (максимуми)
        peaks, _ = find_peaks(self.data['high'], prominence=prominence, distance=distance)
        resistance_levels = self.data['high'].iloc[peaks]

        # Підтримка (мінімуми)
        troughs, _ = find_peaks(-self.data['low'], prominence=prominence, distance=distance)
        support_levels = self.data['low'].iloc[troughs]

        return resistance_levels, support_levels

    # ----------------------------------
    # Пошук fractal levels
    # ----------------------------------

    def find_fractal_levels(self):
        """Пошук fractal levels"""
        highs = self.data['high']
        lows = self.data['low']

        # Верхні фрактали
        upper_fractals = (highs.shift(2) < highs.shift(1)) & (highs.shift(1) < highs) & \
                         (highs > highs.shift(-1)) & (highs.shift(-1) > highs.shift(-2))
        resistance_levels = highs[upper_fractals]

        # Нижні фрактали
        lower_fractals = (lows.shift(2) > lows.shift(1)) & (lows.shift(1) > lows) & \
                         (lows < lows.shift(-1)) & (lows.shift(-1) < lows.shift(-2))
        support_levels = lows[lower_fractals]

        return resistance_levels, support_levels

    # ----------------------------------
    # Розрахунок pivot points
    # ----------------------------------

    def calculate_pivot_points(self):
        """Розрахунок pivot points"""
        high = self.data['high'].shift(1)
        low = self.data['low'].shift(1)
        close = self.data['close'].shift(1)

        pivot = (high + low + close) / 3
        resistance1 = (2 * pivot) - low
        support1 = (2 * pivot) - high
        resistance2 = pivot + (high - low)
        support2 = pivot - (high - low)

        # Об'єднуємо всі рівні опору та підтримки
        resistance_levels = pd.concat([resistance1, resistance2]).dropna()
        support_levels = pd.concat([support1, support2]).dropna()

        return resistance_levels, support_levels

    # ----------------------------------
    # Розрахунок fibonacci levels
    # ----------------------------------

    def calculate_fibonacci_levels(self):
        """Розрахунок fibonacci levels"""
        # Знайдемо останній максимум і мінімум за певний період
        lookback = min(100, len(self.data))  # кількість свічок для аналізу
        recent_high = self.data['high'].rolling(window=lookback).max().iloc[-1]
        recent_low = self.data['low'].rolling(window=lookback).min().iloc[-1]

        levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        diff = recent_high - recent_low

        resistance_levels = [recent_high - diff * level for level in levels]
        support_levels = [recent_low + diff * level for level in levels]

        resistance_levels = pd.Series(resistance_levels)
        support_levels = pd.Series(support_levels)

        return resistance_levels, support_levels

    # ----------------------------------
    # Об'єднання levels
    # ----------------------------------

    def combine_levels(self, resistance_levels_list, support_levels_list, clustering_tolerance=0.005):
        """Об'єднання levels"""
        all_resistances = pd.concat(resistance_levels_list)
        all_supports = pd.concat(support_levels_list)

        # Кластеризація рівнів
        resistance_clusters = self.cluster_levels(all_resistances, clustering_tolerance)
        support_clusters = self.cluster_levels(all_supports, clustering_tolerance)

        return resistance_clusters, support_clusters

    # ----------------------------------
    # Кластеризація levels
    # ----------------------------------

    def cluster_levels(self, levels, tolerance):
        """Кластеризація levels"""
        levels = levels.dropna().sort_values().reset_index(drop=True)
        clustered_levels = []

        while not levels.empty:
            level = levels.iloc[0]
            if level == 0:
                # Уникаємо ділення на нуль
                close_levels = levels[np.abs(levels - level) <= tolerance]
            else:
                close_levels = levels[np.abs((levels - level) / level) <= tolerance]
            clustered_level = close_levels.mean()
            clustered_levels.append(clustered_level)
            levels = levels.drop(close_levels.index).reset_index(drop=True)

        return pd.Series(clustered_levels)

    # ----------------------------------
    # Пошук significant levels
    # ----------------------------------

    def find_significant_levels(self, resistance_clusters, support_clusters, methods_count):
        """Пошук significant levels"""
        # Визначаємо кількість підтверджень для кожного рівня
        resistance_levels = resistance_clusters.value_counts()
        support_levels = support_clusters.value_counts()

        # Фільтруємо рівні, які мають підтвердження від достатньої кількості методів
        significant_resistances = resistance_levels[resistance_levels >= methods_count].index
        significant_supports = support_levels[support_levels >= methods_count].index

        return significant_resistances, significant_supports
    
    # ----------------------------------
    # Виявлення market structure
    # ----------------------------------

    def detect_market_structure(self, swing_window=3):
        """
        Визначення локальних максимумів/мінімумів і побудова структури ринку (HH, HL, LH, LL).

        :param swing_window: кількість свічок для виявлення локальних swing-high/swing-low.
        """

        highs = self.data['high']
        lows = self.data['low']

        structure = []

        for i in range(len(self.data)):
            if i < swing_window or i > len(self.data) - swing_window - 1:
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

        # Тепер визначаємо тип структури (HH, HL, LH, LL)
        last_swing_price = None
        last_swing_type = None
        structure_type = []

        for i in range(len(self.processed_data)):
            current_point = self.processed_data['Market_Structure_Point'].iloc[i]
            current_price = self.data['close'].iloc[i]

            if not pd.isna(current_point):
                if last_swing_price is None:
                    structure_type.append(None)
                else:
                    if current_point == 'swing_high':
                        if current_price > last_swing_price:
                            structure_type.append('HH')  # Higher High
                        else:
                            structure_type.append('LH')  # Lower High
                    elif current_point == 'swing_low':
                        if current_price > last_swing_price:
                            structure_type.append('HL')  # Higher Low
                        else:
                            structure_type.append('LL')  # Lower Low
                last_swing_price = current_price
                last_swing_type = current_point
            else:
                structure_type.append(None)

        self.processed_data['Market_Structure_Type'] = structure_type

    # ----------------------------------
    # Виявлення bos choch
    # ----------------------------------

    def detect_bos_choch(self):
        """
        Визначає Break of Structure (BOS) та Change of Character (CHoCH) на основі структури ринку.
        """

        structure = self.processed_data['Market_Structure_Type']
        close = self.data['close']

        last_hh = None
        last_hl = None
        last_ll = None
        last_lh = None
        trend_direction = None  # 'uptrend' або 'downtrend'

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

    # ----------------------------------
    # Виявлення liquidity sweep
    # ----------------------------------

    def detect_liquidity_sweep(self, swing_window=3, tolerance=0.0005):
        """Виявлення liquidity sweep"""
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


    # ----------------------------------
    # Виявлення order blocks
    # ----------------------------------

    def detect_order_blocks(self, body_threshold=0.5, min_body_size=0.0001):
        """Виявлення order blocks"""
        open_ = self.data['open']
        close = self.data['close']
        high = self.data['high']
        low = self.data['low']

        body = (close - open_).abs()
        range_ = high - low

        bullish_ob = []
        bearish_ob = []

        n = len(self.data)
        for i in range(n):
            r = float(range_.iloc[i])
            b = float(body.iloc[i])

            if r == 0:
                bullish_ob.append(False)
                bearish_ob.append(False)
                continue

            body_ratio = b / r

            if body_ratio > body_threshold and b > min_body_size:
                if close.iloc[i] > open_.iloc[i]:
                    bullish_ob.append(True)
                    bearish_ob.append(False)
                else:
                    bullish_ob.append(False)
                    bearish_ob.append(True)
            else:
                bullish_ob.append(False)
                bearish_ob.append(False)

        self.processed_data['Bullish_OB'] = bullish_ob
        self.processed_data['Bearish_OB'] = bearish_ob


    # ----------------------------------
    # Виявлення fair value gaps
    # ----------------------------------

    def detect_fair_value_gaps(self, min_gap_ratio=0.0003):
        """
        Виявляє Fair Value Gaps (імбаланси) між трьома свічками.

        :param min_gap_ratio: мінімальний розмір FVG як частка ціни (0.0003 = 0.03%)
        """

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

            # Додатково перевіряємо мінімальний розмір FVG
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

        # Додаємо NaN для перших двох свічок (немає повного контексту)
        fvg_up = [False, False] + fvg_up
        fvg_down = [False, False] + fvg_down

        self.processed_data['FVG_Up'] = fvg_up
        self.processed_data['FVG_Down'] = fvg_down

    # ----------------------------------
    # Головний метод обробки даних
    # ----------------------------------

    def process_data(self):
        """Головний метод обробки даних"""
        algo_methods = {
            'Levels': self.calculate_levels,
            'Market_Structure': self.detect_market_structure,
            'BOS_CHoCH': self.detect_bos_choch,
            'Liquidity_Sweep': self.detect_liquidity_sweep,
            'Order_Blocks': self.detect_order_blocks,
            'Fair_Value_Gaps': self.detect_fair_value_gaps,
            'WCE_Anomaly': self.add_wce_anomaly,
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
    
# ==================================
# Клас алгоритмічної обробки, адаптований для бектесту
# ==================================
