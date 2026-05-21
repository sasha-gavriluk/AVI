import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from utils.algorithms.WrapCandleEngine import WCE

class PatternDetector:
    """Клас для виявлення свічкових патернів"""
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame , pattern_params=None):
        """Ініціалізація"""
        self.data = data
        self.processed_data = processed_data
        self.pattern_params = pattern_params if pattern_params is not None else []

    # Окремі методи для свічкових патернів
    # ----------------------------------
    # Виявлення hammer
    # ----------------------------------

    def detect_hammer(self):
        """Виявлення hammer"""
        body = np.abs(self.data['close'] - self.data['open'])
        shadow_lower = self.data['low'] - np.minimum(self.data['close'], self.data['open'])
        shadow_upper = self.data['high'] - np.maximum(self.data['close'], self.data['open'])
        condition = (shadow_lower >= 2 * body) & (shadow_upper <= body)
        self.processed_data['Hammer'] = condition.astype(int)

    # ----------------------------------
    # Виявлення inverted hammer
    # ----------------------------------

    def detect_inverted_hammer(self):
        """
        Виявляє патерн Inverted Hammer.
        """
        open_ = self.data['open']
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        body = abs(close - open_)
        upper_shadow = high - np.maximum(close, open_)
        lower_shadow = np.minimum(close, open_) - low

        condition = (
            (upper_shadow > 2 * body) &           # Довга верхня тінь
            (lower_shadow < body * 0.5) &         # Коротка або відсутня нижня тінь
            (close < open_)                       # Ведмежа свічка
        )

        self.processed_data['Inverted_Hammer'] = condition.astype(bool)
        # print(f"Патерн 'Inverted Hammer' виявлено: {condition.sum()} разів")

    # ----------------------------------
    # Виявлення shooting star
    # ----------------------------------

    def detect_shooting_star(self):
        """Виявлення shooting star"""
        body = np.abs(self.data['close'] - self.data['open'])
        shadow_upper = self.data['high'] - np.maximum(self.data['close'], self.data['open'])
        shadow_lower = np.minimum(self.data['close'], self.data['open']) - self.data['low']
        condition = (shadow_upper >= 2 * body) & (shadow_lower <= body)
        self.processed_data['Shooting_Star'] = condition.astype(int)

    # ----------------------------------
    # Виявлення engulfing
    # ----------------------------------

    def detect_engulfing(self):
        """Виявлення engulfing"""
        prev_close = self.data['close'].shift(1)
        prev_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        bullish = ((current_close > current_open) & (prev_close < prev_open) &
                   (current_close >= prev_open) & (current_open <= prev_close))
        bearish = ((current_close < current_open) & (prev_close > prev_open) &
                   (current_close <= prev_open) & (current_open >= prev_close))

        self.processed_data['Engulfing'] = np.where(bullish, 1, np.where(bearish, -1, 0))

    # ----------------------------------
    # Виявлення morning star
    # ----------------------------------

    def detect_morning_star(self):
        """Виявлення morning star"""
        prev2_close = self.data['close'].shift(2)
        prev2_open = self.data['open'].shift(2)
        prev1_close = self.data['close'].shift(1)
        prev1_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        condition = ((prev2_close < prev2_open) &
                     (prev1_close < prev1_open) &
                     (current_close > current_open) &
                     (current_close > prev2_open))

        self.processed_data['Morning_Star'] = condition.astype(int)

    # ----------------------------------
    # Виявлення evening star
    # ----------------------------------

    def detect_evening_star(self):
        """Виявлення evening star"""
        prev2_close = self.data['close'].shift(2)
        prev2_open = self.data['open'].shift(2)
        prev1_close = self.data['close'].shift(1)
        prev1_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        condition = ((prev2_close > prev2_open) &
                     (prev1_close > prev1_open) &
                     (current_close < current_open) &
                     (current_close < prev2_open))

        self.processed_data['Evening_Star'] = condition.astype(int)

    # ----------------------------------
    # Виявлення piercing pattern
    # ----------------------------------

    def detect_piercing_pattern(self):
        """Виявлення piercing pattern"""
        prev_close = self.data['close'].shift(1)
        prev_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        condition = ((prev_close < prev_open) &
                     (current_close > current_open) &
                     (current_close > (prev_close + prev_open)/2) &
                     (current_open < prev_close))

        self.processed_data['Piercing_Pattern'] = condition.astype(int)

    # ----------------------------------
    # Виявлення dark cloud cover
    # ----------------------------------

    def detect_dark_cloud_cover(self):
        """Виявлення dark cloud cover"""
        prev_close = self.data['close'].shift(1)
        prev_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        condition = ((prev_close > prev_open) &
                     (current_close < current_open) &
                     (current_close < (prev_close + prev_open)/2) &
                     (current_open > prev_close))

        self.processed_data['Dark_Cloud_Cover'] = condition.astype(int)

    # ----------------------------------
    # Виявлення three white soldiers
    # ----------------------------------

    def detect_three_white_soldiers(self):
        """Виявлення three white soldiers"""
        close = self.data['close']
        open_ = self.data['open']

        condition = ((close > open_) &
                     (close.shift(1) > open_.shift(1)) &
                     (close.shift(2) > open_.shift(2)) &
                     (close > close.shift(1)) &
                     (close.shift(1) > close.shift(2)))

        self.processed_data['Three_White_Soldiers'] = condition.astype(int)
        # print(f"Патерн 'Three_White_Soldiers' виявлено: {condition.sum()} разів")

    # ----------------------------------
    # Виявлення three black crows
    # ----------------------------------

    def detect_three_black_crows(self):
        """Виявлення three black crows"""
        close = self.data['close']
        open_ = self.data['open']

        condition = ((close < open_) &
                     (close.shift(1) < open_.shift(1)) &
                     (close.shift(2) < open_.shift(2)) &
                     (close < close.shift(1)) &
                     (close.shift(1) < close.shift(2)))

        self.processed_data['Three_Black_Crows'] = condition.astype(int)
        # print(f"Патерн 'Three_Black_Crows' виявлено: {condition.sum()} разів")

    # ----------------------------------
    # Виявлення hanging man
    # ----------------------------------

    def detect_hanging_man(self):
        """Виявлення hanging man"""
        body = np.abs(self.data['close'] - self.data['open'])
        shadow_lower = self.data['low'] - np.minimum(self.data['close'], self.data['open'])
        shadow_upper = self.data['high'] - np.maximum(self.data['close'], self.data['open'])

        condition = (shadow_lower >= 2 * body) & (shadow_upper <= body) & (body / (self.data['high'] - self.data['low']) >= 0.3)

        self.processed_data['Hanging_Man'] = condition.astype(int)

    # ----------------------------------
    # Головний метод обробки даних
    # ----------------------------------

    def process_data(self):
        """Головний метод обробки даних"""
        pattern_methods = {
            'Hammer': self.detect_hammer,
            'Inverted_Hammer': self.detect_inverted_hammer,
            'Shooting_Star': self.detect_shooting_star,
            'Engulfing': self.detect_engulfing,
            'Morning_Star': self.detect_morning_star,
            'Evening_Star': self.detect_evening_star,
            'Piercing_Pattern': self.detect_piercing_pattern,
            'Dark_Cloud_Cover': self.detect_dark_cloud_cover,
            'Three_White_Soldiers': self.detect_three_white_soldiers,
            'Three_Black_Crows': self.detect_three_black_crows,
            'Hanging_Man': self.detect_hanging_man,
        }

        if self.pattern_params:
            for pattern in self.pattern_params:
                name = pattern if isinstance(pattern, str) else pattern.get('name')
                if name in pattern_methods:
                    pattern_methods[name]()
                else:
                    print(f"Патерн '{name}' не підтримується.")
        else:
            for method in pattern_methods.values():
                method()

        return self.processed_data

# ==================================
# Клас для алгоритмічної обробки та розрахунку рівнів
# ==================================
