import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE

class BacktestAlgorithmProcessor(AlgorithmProcessor):
    """
    Спеціалізований клас для обробки алгоритмічних фіч під час бектестування.
    Перевизначає методи для усунення "заглядання в майбутнє".
    Цей клас гарантує, що всі розрахунки базуються лише на історичних даних,
    доступних на момент поточної свічки.
    """
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame, algorithm_params=None, fractal_window=2):
        """Ініціалізація"""
        super().__init__(data, processed_data, algorithm_params)
        self.fractal_window = fractal_window # Window size for lookahead-free fractals
        # Store last confirmed swing points to build market structure incrementally
        self._last_swing_high = {'index': -1, 'value': -np.inf}
        self._last_swing_low = {'index': -1, 'value': np.inf}

    # ----------------------------------
    # Пошук fractal levels
    # ----------------------------------

    def find_fractal_levels(self):
        """
        Lookahead-free fractal detection.
        A fractal high is the highest point in a trailing window.
        A fractal low is the lowest point in a trailing window.
        """
        # Initialize columns if they don't exist
        if 'Fractal_High' not in self.processed_data.columns:
            self.processed_data['Fractal_High'] = False
        if 'Fractal_Low' not in self.processed_data.columns:
            self.processed_data['Fractal_Low'] = False

        if len(self.processed_data) < self.fractal_window + 1:
            return # Not enough data for initial fractal calculation

        # Get the current candle's index (last index in the slice)
        current_idx_in_slice = len(self.processed_data) - 1
        current_candle_df_index = self.processed_data.index[current_idx_in_slice]

        # Check for Fractal High at the current candle
        # The current high must be the maximum in the window ending at the current candle
        if current_idx_in_slice >= self.fractal_window:
            window_highs = self.processed_data['high'].iloc[current_idx_in_slice - self.fractal_window : current_idx_in_slice + 1]
            if self.processed_data['high'].iloc[current_idx_in_slice] == window_highs.max():
                self.processed_data.loc[current_candle_df_index, 'Fractal_High'] = True

            # Check for Fractal Low at the current candle
            window_lows = self.processed_data['low'].iloc[current_idx_in_slice - self.fractal_window : current_idx_in_slice + 1]
            if self.processed_data['low'].iloc[current_idx_in_slice] == window_lows.min():
                self.processed_data.loc[current_candle_df_index, 'Fractal_Low'] = True

    # ----------------------------------
    # Пошук peaks levels
    # ----------------------------------

    def find_peaks_levels(self, prominence=1, distance=5):
        """
        Lookahead-free find_peaks_levels.
        This version processes peaks/troughs only up to the current candle.
        """
        current_idx_in_slice = len(self.processed_data) - 1
        current_candle_df_index = self.processed_data.index[current_idx_in_slice]

        # To avoid lookahead, we can only confirm a peak/trough after `distance` candles have passed.
        # For a truly lookahead-free backtest, often peaks are confirmed retrospectively.
        # For simplicity here, we'll check the current candle relative to its *past* window.
        # This is a simplification, as `find_peaks` is inherently designed for full series.
        # A more robust lookahead-free peak detection would involve iterative confirmation.

        # For now, we'll mark the current candle as a potential peak/trough
        # if it's the highest/lowest in a trailing window.
        
        # Initialize columns if they don't exist
        if 'Peak_High' not in self.processed_data.columns:
            self.processed_data['Peak_High'] = False
        if 'Peak_Low' not in self.processed_data.columns:
            self.processed_data['Peak_Low'] = False

        if current_idx_in_slice >= distance:
            # Check for Peak High: current high is max in trailing window
            window_highs = self.processed_data['high'].iloc[current_idx_in_slice - distance : current_idx_in_slice + 1]
            if self.processed_data['high'].iloc[current_idx_in_slice] == window_highs.max():
                self.processed_data.loc[current_candle_df_index, 'Peak_High'] = True

            # Check for Peak Low: current low is min in trailing window
            window_lows = self.processed_data['low'].iloc[current_idx_in_slice - distance : current_idx_in_slice + 1]
            if self.processed_data['low'].iloc[current_idx_in_slice] == window_lows.min():
                self.processed_data.loc[current_candle_df_index, 'Peak_Low'] = True
        
        # This method will not return series, but update processed_data directly.
        # The `calculate_levels` method will then read from these columns.

    # ----------------------------------
    # Виявлення fair value gaps
    # ----------------------------------

    def detect_fair_value_gaps(self, min_gap_ratio=0.0003):
        """
        Lookahead-free Fair Value Gaps (FVG) detection for the current candle.
        Bullish FVG: Low[current] > High[current-2]
        Bearish FVG: High[current] < Low[current-2]
        """
        # Initialize columns if they don't exist
        if 'FVG_Up' not in self.processed_data.columns:
            self.processed_data['FVG_Up'] = False
        if 'FVG_Down' not in self.processed_data.columns:
            self.processed_data['FVG_Down'] = False
        if 'FVG_Size' not in self.processed_data.columns:
            self.processed_data['FVG_Size'] = np.nan

        current_idx_in_slice = len(self.processed_data) - 1
        current_candle_df_index = self.processed_data.index[current_idx_in_slice]

        if current_idx_in_slice < 2: # Need at least 3 candles (i, i-1, i-2) for FVG
            return

        curr_high = self.processed_data['high'].iloc[current_idx_in_slice]
        curr_low = self.processed_data['low'].iloc[current_idx_in_slice]
        prev2_high = self.processed_data['high'].iloc[current_idx_in_slice - 2]
        prev2_low = self.processed_data['low'].iloc[current_idx_in_slice - 2]
        current_price = self.processed_data['close'].iloc[current_idx_in_slice]

        # Bullish FVG
        if curr_low > prev2_high:
            gap_size = curr_low - prev2_high
            if current_price > 0 and (gap_size / current_price) > min_gap_ratio:
                self.processed_data.loc[current_candle_df_index, 'FVG_Up'] = True
                self.processed_data.loc[current_candle_df_index, 'FVG_Size'] = gap_size

        # Bearish FVG
        if curr_high < prev2_low:
            gap_size = prev2_low - curr_high
            if current_price > 0 and (gap_size / current_price) > min_gap_ratio:
                self.processed_data.loc[current_candle_df_index, 'FVG_Down'] = True
                self.processed_data.loc[current_candle_df_index, 'FVG_Size'] = gap_size

    # ----------------------------------
    # Виявлення market structure
    # ----------------------------------

    def detect_market_structure(self):
        """
        Lookahead-free market structure detection based on confirmed fractals.
        This method updates the market structure for the current candle based on
        the most recent confirmed swing high/low.
        """
        # Initialize columns if they don't exist
        if 'Market_Structure_Point' not in self.processed_data.columns:
            self.processed_data['Market_Structure_Point'] = None
        if 'Market_Structure_Type' not in self.processed_data.columns:
            self.processed_data['Market_Structure_Type'] = None
        if 'Highs_Lows' not in self.processed_data.columns:
            self.processed_data['Highs_Lows'] = 0

        current_idx_in_slice = len(self.processed_data) - 1
        current_candle_df_index = self.processed_data.index[current_idx_in_slice]
        
        current_high = self.processed_data['high'].iloc[current_idx_in_slice]
        current_low = self.processed_data['low'].iloc[current_idx_in_slice]

        # Update last swing high/low if a new fractal is detected at the current candle
        if self.processed_data.loc[current_candle_df_index, 'Fractal_High']:
            self.processed_data.loc[current_candle_df_index, 'Market_Structure_Point'] = 'swing_high'
            if current_high > self._last_swing_high['value']:
                self.processed_data.loc[current_candle_df_index, 'Market_Structure_Type'] = 'HH'
                self.processed_data.loc[current_candle_df_index, 'Highs_Lows'] = 1
            else:
                self.processed_data.loc[current_candle_df_index, 'Market_Structure_Type'] = 'LH'
                self.processed_data.loc[current_candle_df_index, 'Highs_Lows'] = -1
            self._last_swing_high = {'index': current_candle_df_index, 'value': current_high}
            # If a new high, reset last low for HH/HL comparison
            self._last_swing_low = {'index': -1, 'value': np.inf} # Reset to allow new HL detection

        elif self.processed_data.loc[current_candle_df_index, 'Fractal_Low']:
            self.processed_data.loc[current_candle_df_index, 'Market_Structure_Point'] = 'swing_low'
            if current_low < self._last_swing_low['value']:
                self.processed_data.loc[current_candle_df_index, 'Market_Structure_Type'] = 'LL'
                self.processed_data.loc[current_candle_df_index, 'Highs_Lows'] = -1
            else:
                self.processed_data.loc[current_candle_df_index, 'Market_Structure_Type'] = 'HL'
                self.processed_data.loc[current_candle_df_index, 'Highs_Lows'] = 1
            self._last_swing_low = {'index': current_candle_df_index, 'value': current_low}
            # If a new low, reset last high for LL/LH comparison
            self._last_swing_high = {'index': -1, 'value': -np.inf} # Reset to allow new LH detection

        # If no new swing point, carry forward the last known structure type or None
        if current_idx_in_slice > 0 and self.processed_data.loc[current_candle_df_index, 'Market_Structure_Type'] is None:
            self.processed_data.loc[current_candle_df_index, 'Market_Structure_Type'] = \
                self.processed_data['Market_Structure_Type'].iloc[current_idx_in_slice - 1]
            self.processed_data.loc[current_candle_df_index, 'Highs_Lows'] = \
                self.processed_data['Highs_Lows'].iloc[current_idx_in_slice - 1]

    # ----------------------------------
    # Виявлення liquidity sweep (Lookahead-free)
    # ----------------------------------

    def detect_liquidity_sweep(self, swing_window=3, tolerance=0.0005):
        if 'Sweep_High' not in self.processed_data.columns:
            self.processed_data['Sweep_High'] = False
        if 'Sweep_Low' not in self.processed_data.columns:
            self.processed_data['Sweep_Low'] = False

        current_idx = len(self.processed_data) - 1
        current_candle_idx = self.processed_data.index[current_idx]

        if current_idx < swing_window:
            return

        # Тільки минулі свічки
        local_high = self.processed_data['high'].iloc[current_idx - swing_window : current_idx].max()
        local_low = self.processed_data['low'].iloc[current_idx - swing_window : current_idx].min()

        if self.processed_data['high'].iloc[current_idx] > local_high * (1 + tolerance):
            self.processed_data.loc[current_candle_idx, 'Sweep_High'] = True

        if self.processed_data['low'].iloc[current_idx] < local_low * (1 - tolerance):
            self.processed_data.loc[current_candle_idx, 'Sweep_Low'] = True

    # ----------------------------------
    # Виявлення bos choch (Lookahead-free для поточної свічки)
    # ----------------------------------

    def detect_bos_choch(self):
        """
        Lookahead-free BOS / CHoCH для поточної свічки (щоб не перераховувати O(N^2)).
        """
        if 'BOS' not in self.processed_data.columns:
            self.processed_data['BOS'] = False
        if 'CHoCH' not in self.processed_data.columns:
            self.processed_data['CHoCH'] = False
            
        # Якщо ми не маємо стану тренду, ініціалізуємо змінні
        if not hasattr(self, '_trend_direction'):
            self._trend_direction = None
            self._last_confirmed_hh = None
            self._last_confirmed_hl = None
            self._last_confirmed_ll = None
            self._last_confirmed_lh = None

        current_idx_in_slice = len(self.processed_data) - 1
        current_candle_df_index = self.processed_data.index[current_idx_in_slice]
        
        point = self.processed_data['Market_Structure_Type'].iloc[current_idx_in_slice]
        price = self.data['close'].iloc[current_idx_in_slice]
        
        bos_signal = False
        choch_signal = False
        
        # Перевіряємо, чи змінилася структура на поточній свічці
        # Якщо структура та сама, що і на попередній, не робимо повторних обчислень для того ж екстремуму
        prev_point = self.processed_data['Market_Structure_Type'].iloc[current_idx_in_slice - 1] if current_idx_in_slice > 0 else None
        
        if point is not None and point != prev_point:
            if point == 'HH':
                if self._last_confirmed_hh is None or price > self._last_confirmed_hh:
                    self._last_confirmed_hh = price
                if self._trend_direction == 'downtrend' and self._last_confirmed_lh is not None and price > self._last_confirmed_lh:
                    choch_signal = True
                    self._trend_direction = 'uptrend'
                elif self._trend_direction == 'uptrend' and self._last_confirmed_hh is not None and price > self._last_confirmed_hh:
                    bos_signal = True
                elif self._trend_direction is None:
                    self._trend_direction = 'uptrend'

            elif point == 'HL':
                if self._last_confirmed_hl is None or price > self._last_confirmed_hl:
                    self._last_confirmed_hl = price

            elif point == 'LL':
                if self._last_confirmed_ll is None or price < self._last_confirmed_ll:
                    self._last_confirmed_ll = price
                if self._trend_direction == 'uptrend' and self._last_confirmed_hl is not None and price < self._last_confirmed_hl:
                    choch_signal = True
                    self._trend_direction = 'downtrend'
                elif self._trend_direction == 'downtrend' and self._last_confirmed_ll is not None and price < self._last_confirmed_ll:
                    bos_signal = True
                elif self._trend_direction is None:
                    self._trend_direction = 'downtrend'

            elif point == 'LH':
                if self._last_confirmed_lh is None or price < self._last_confirmed_lh:
                    self._last_confirmed_lh = price

        self.processed_data.loc[current_candle_df_index, 'BOS'] = bos_signal
        self.processed_data.loc[current_candle_df_index, 'CHoCH'] = choch_signal

    # ----------------------------------
    # Розрахунок levels
    # ----------------------------------

    def calculate_levels(self):
        """
        Lookahead-free calculate_levels method.
        This method is now part of BacktestAlgorithmProcessor and will use
        the lookahead-free versions of `find_fractal_levels` and `find_peaks_levels`.
        """
        # Ensure fractal and peak levels are calculated first, as they modify processed_data in place
        self.find_fractal_levels() # This updates 'Fractal_High' and 'Fractal_Low'
        self.find_peaks_levels()   # This updates 'Peak_High' and 'Peak_Low'

        resistance_levels_list = []
        support_levels_list = []

        current_idx_in_slice = len(self.processed_data) - 1
        current_candle_df_index = self.processed_data.index[current_idx_in_slice]
        
        # Метод 1: Піки та западини (з lookahead-free Peak_High/Low)
        if 'Peak_High' in self.processed_data.columns and self.processed_data.loc[current_candle_df_index, 'Peak_High']:
            resistance_levels_list.append(pd.Series([self.processed_data['high'].iloc[current_idx_in_slice]]))
        if 'Peak_Low' in self.processed_data.columns and self.processed_data.loc[current_candle_df_index, 'Peak_Low']:
            support_levels_list.append(pd.Series([self.processed_data['low'].iloc[current_idx_in_slice]]))

        # Метод 2: Фрактали (з lookahead-free Fractal_High/Low)
        if 'Fractal_High' in self.processed_data.columns and self.processed_data.loc[current_candle_df_index, 'Fractal_High']:
            resistance_levels_list.append(pd.Series([self.processed_data['high'].iloc[current_idx_in_slice]]))
        if 'Fractal_Low' in self.processed_data.columns and self.processed_data.loc[current_candle_df_index, 'Fractal_Low']:
            support_levels_list.append(pd.Series([self.processed_data['low'].iloc[current_idx_in_slice]]))

        # Метод 3: Pivot Points (використовуємо базовий метод, він вже lookahead-free для поточної свічки)
        res_pivots, sup_pivots = super().calculate_pivot_points()
        if not res_pivots.empty:
            resistance_levels_list.append(res_pivots)
        if not sup_pivots.empty:
            support_levels_list.append(sup_pivots)

        # Метод 4: Фібоначчі (використовуємо базовий метод, він вже lookahead-free для поточної свічки)
        res_fibo, sup_fibo = super().calculate_fibonacci_levels()
        if not res_fibo.empty:
            resistance_levels_list.append(res_fibo)
        if not sup_fibo.empty:
            support_levels_list.append(sup_fibo)

        # Ініціалізуємо колонки, якщо вони ще не існують
        if 'Near_Resistance' not in self.processed_data.columns:
            self.processed_data['Near_Resistance'] = False
        if 'Near_Support' not in self.processed_data.columns:
            self.processed_data['Near_Support'] = False

        # Перевірка, чи є рівні для комбінування
        if resistance_levels_list or support_levels_list:
            all_resistances = pd.concat(resistance_levels_list).dropna() if resistance_levels_list else pd.Series()
            all_supports = pd.concat(support_levels_list).dropna() if support_levels_list else pd.Series()

            # Кластеризація рівнів
            # Викликаємо cluster_levels з правильним ім'ям аргументу 'tolerance'
            res_clusters = self.cluster_levels(all_resistances, tolerance=0.005) 
            sup_clusters = self.cluster_levels(all_supports, tolerance=0.005) 

            # Знаходимо значущі рівні (підтверджені як мінімум одним методом)
            # Примітка: find_significant_levels також є методом батьківського класу.
            # Оскільки він працює з Series, його можна використовувати без змін.
            self.significant_resistances, self.significant_supports = self.find_significant_levels(res_clusters, sup_clusters, methods_count=1)

            # Додаємо логічні колонки, які показують, чи ціна близька до рівнів
            current_price = self.processed_data['close'].iloc[current_idx_in_slice]
            
            self.processed_data.loc[current_candle_df_index, 'Near_Resistance'] = self.is_near_level(current_price, self.significant_resistances)
            self.processed_data.loc[current_candle_df_index, 'Near_Support'] = self.is_near_level(current_price, self.significant_supports)
        else:
            # Якщо рівнів не знайдено, встановлюємо False для поточної свічки
            self.processed_data.loc[current_candle_df_index, 'Near_Resistance'] = False
            self.processed_data.loc[current_candle_df_index, 'Near_Support'] = False
            # print("No levels found to combine for the current candle.")


    # ----------------------------------
    # Головний метод обробки даних
    # ----------------------------------

    def process_data(self):
        """Main function to run algorithmic processing based on provided parameters."""
        algo_methods = {
            'Levels': self.calculate_levels, # Now calls the overridden version
            'Market_Structure': self.detect_market_structure,
            'BOS_CHoCH': self.detect_bos_choch,
            'Liquidity_Sweep': self.detect_liquidity_sweep,
            'Order_Blocks': self.detect_order_blocks,
            'Fair_Value_Gaps': self.detect_fair_value_gaps,
        }

        if self.algorithm_params:
            for name in self.algorithm_params:
                key = name if isinstance(name, str) else name.get("name")
                if key in algo_methods:
                    algo_methods[key]()
                else:
                    print(f"Алгоритмічна функція '{key}' не підтримується.")
        else:
            # If no parameters, run all algorithms with default values
            for method in algo_methods.values():
                method()

        return self.processed_data
    
# ==================================
# Головний менеджер для оркестрації обробки даних
# ==================================
