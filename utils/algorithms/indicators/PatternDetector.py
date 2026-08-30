import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE
from utils.OtherUtils import _handle_error

class PatternDetector:
    "Клас для виявлення класичних свічкових патернів"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame , pattern_params=None):
        self.data = data
        self.processed_data = processed_data
        self.pattern_params = pattern_params if pattern_params is not None else []

    #------------------------------
    # Виявлення Hammer
    #------------------------------

    @_handle_error
    def detect_hammer(self):
        "Виявляє патерн Hammer (Молот)"
        body = np.abs(self.data['close'] - self.data['open'])
        shadow_lower = self.data['low'] - np.minimum(self.data['close'], self.data['open'])
        shadow_upper = self.data['high'] - np.maximum(self.data['close'], self.data['open'])
        condition = (shadow_lower >= 2 * body) & (shadow_upper <= body)
        self.processed_data['Hammer'] = condition.astype(int)

    #------------------------------
    # Виявлення Inverted Hammer
    #------------------------------

    @_handle_error
    def detect_inverted_hammer(self):
        "Виявляє патерн Inverted Hammer (Перевернутий молот)"
        open_ = self.data['open']
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        body = abs(close - open_)
        upper_shadow = high - np.maximum(close, open_)
        lower_shadow = np.minimum(close, open_) - low

        condition = (
            (upper_shadow > 2 * body) &           
            (lower_shadow < body * 0.5) &         
            (close < open_)                       
        )

        self.processed_data['Inverted_Hammer'] = condition.astype(bool)

    #------------------------------
    # Виявлення Shooting Star
    #------------------------------

    @_handle_error
    def detect_shooting_star(self):
        "Виявляє патерн Shooting Star (Зірка, що падає)"
        body = np.abs(self.data['close'] - self.data['open'])
        shadow_upper = self.data['high'] - np.maximum(self.data['close'], self.data['open'])
        shadow_lower = np.minimum(self.data['close'], self.data['open']) - self.data['low']
        condition = (shadow_upper >= 2 * body) & (shadow_lower <= body)
        self.processed_data['Shooting_Star'] = condition.astype(int)

    #------------------------------
    # Виявлення Engulfing
    #------------------------------

    @_handle_error
    def detect_engulfing(self):
        "Виявляє патерн Engulfing (Поглинання)"
        prev_close = self.data['close'].shift(1)
        prev_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        bullish = ((current_close > current_open) & (prev_close < prev_open) &
                   (current_close >= prev_open) & (current_open <= prev_close))
        bearish = ((current_close < current_open) & (prev_close > prev_open) &
                   (current_close <= prev_open) & (current_open >= prev_close))

        self.processed_data['Engulfing'] = np.where(bullish, 1, np.where(bearish, -1, 0))

    #------------------------------
    # Виявлення Morning Star
    #------------------------------

    @_handle_error
    def detect_morning_star(self):
        "Виявляє патерн Morning Star (Ранкова зірка)"
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

    #------------------------------
    # Виявлення Evening Star
    #------------------------------

    @_handle_error
    def detect_evening_star(self):
        "Виявляє патерн Evening Star (Вечірня зірка)"
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

    #------------------------------
    # Виявлення Piercing Pattern
    #------------------------------

    @_handle_error
    def detect_piercing_pattern(self):
        "Виявляє Piercing Pattern (Просвіт у хмарах)"
        prev_close = self.data['close'].shift(1)
        prev_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        condition = ((prev_close < prev_open) &
                     (current_close > current_open) &
                     (current_close > (prev_close + prev_open)/2) &
                     (current_open < prev_close))

        self.processed_data['Piercing_Pattern'] = condition.astype(int)

    #------------------------------
    # Виявлення Dark Cloud Cover
    #------------------------------

    @_handle_error
    def detect_dark_cloud_cover(self):
        "Виявляє Dark Cloud Cover (Завіса з темних хмар)"
        prev_close = self.data['close'].shift(1)
        prev_open = self.data['open'].shift(1)
        current_close = self.data['close']
        current_open = self.data['open']

        condition = ((prev_close > prev_open) &
                     (current_close < current_open) &
                     (current_close < (prev_close + prev_open)/2) &
                     (current_open > prev_close))

        self.processed_data['Dark_Cloud_Cover'] = condition.astype(int)

    #------------------------------
    # Виявлення Three White Soldiers
    #------------------------------

    @_handle_error
    def detect_three_white_soldiers(self):
        "Виявляє Three White Soldiers (Три білі солдати)"
        close = self.data['close']
        open_ = self.data['open']

        condition = ((close > open_) &
                     (close.shift(1) > open_.shift(1)) &
                     (close.shift(2) > open_.shift(2)) &
                     (close > close.shift(1)) &
                     (close.shift(1) > close.shift(2)))

        self.processed_data['Three_White_Soldiers'] = condition.astype(int)

    #------------------------------
    # Виявлення Three Black Crows
    #------------------------------

    @_handle_error
    def detect_three_black_crows(self):
        "Виявляє Three Black Crows (Три чорні ворони)"
        close = self.data['close']
        open_ = self.data['open']

        condition = ((close < open_) &
                     (close.shift(1) < open_.shift(1)) &
                     (close.shift(2) < open_.shift(2)) &
                     (close < close.shift(1)) &
                     (close.shift(1) < close.shift(2)))

        self.processed_data['Three_Black_Crows'] = condition.astype(int)

    #------------------------------
    # Виявлення Hanging Man
    #------------------------------

    @_handle_error
    def detect_hanging_man(self):
        "Виявляє Hanging Man (Шибеник)"
        body = np.abs(self.data['close'] - self.data['open'])
        shadow_lower = self.data['low'] - np.minimum(self.data['close'], self.data['open'])
        shadow_upper = self.data['high'] - np.maximum(self.data['close'], self.data['open'])

        condition = (shadow_lower >= 2 * body) & (shadow_upper <= body) & (body / (self.data['high'] - self.data['low']) >= 0.3)

        self.processed_data['Hanging_Man'] = condition.astype(int)

    #------------------------------
    # Оркестратор
    #------------------------------

    @_handle_error
    def process_data(self):
        "Головний оркестратор для виклику методів патернів"
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
