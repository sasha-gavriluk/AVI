import pandas as pd
import numpy as np

from utils.other_utils import _handle_error

class WCE: # Wrap Candle Engine
    def __init__(self, df: pd.DataFrame, period: int):
        self.data = df
        self.period = period
        self.equalsloatings_size_percent = 0.1

    #------------------------------
    # Внутрішній метод для обчислення MAD (Median Absolute Deviation)
    #------------------------------

    def _get_numpy_mad(self, x):
        "Обчислення MAD для масиву x"
        mean_val = np.mean(x)
        return np.mean(np.abs(x - mean_val))

    #------------------------------
    # Буквенний-численний символ. Перший
    #------------------------------

    #------------------------------
    # Метод перетворення даних в B (Buy), S (Sell), D (Dodji) (Варіант 2)
    #------------------------------

    @_handle_error
    def _transform_to_bsd_v2(self, custom_period=None): 
        "Параметри: custom_period - необов'язковий параметр для вказівки власного періоду замість стандартного"

        last_body_size = (self.data['close'] - self.data['open']).abs()
        last_total_size = self.data['high'] - self.data['low']

        is_dodj = last_body_size <= (self.equalsloatings_size_percent * last_total_size)
        is_bullish = self.data['close'] > self.data['open']
        is_bearish = self.data['close'] < self.data['open']

        conditions = [is_dodj, is_bullish, is_bearish]
        choices = ['D', 'B', 'S']

        bsd_sequence = np.select(conditions, choices, default='N')
        return bsd_sequence.tolist()
    
    #------------------------------
    # Буквенний-численний символ. Другий
    #------------------------------

    #------------------------------
    # Метод перетворення середнього відхилення тіла січки від вікна (Варіант 2)
    #------------------------------

    @_handle_error
    def _transform_body_deviation_v2(self, custom_period=None):
        "Параметри: custom_period - необов'язковий параметр для вказівки власного періоду замість стандартного"
        period = custom_period if custom_period is not None else self.period

        body_size = (self.data['close'] - self.data['open']).abs()

        last_body_size = body_size
        mean_body_size = body_size.rolling(window=period).mean()
        mad_body_size = body_size.rolling(window=period).apply(self._get_numpy_mad, raw=True)

        raw_score = 5 + np.where(
            mad_body_size != 0, 
            (last_body_size - mean_body_size) / mad_body_size, 
            0
        )
        deviation = pd.Series(raw_score).fillna(0).round().clip(1, 9).astype(int)
        return deviation.tolist()
    
    #------------------------------
    # Буквенний-численний символ. Третій 
    #------------------------------

    #------------------------------
    # Метод перетворення середнього відхилення тіні свічки від вікна (Варіант 2)
    #------------------------------

    @_handle_error
    def _transform_shadow_deviation_v2(self, custom_period=None):
        "Параметри: custom_period - необов'язковий параметр для вказівки власного періоду замість стандартного"
        period = custom_period if custom_period is not None else self.period

        body_size = (self.data['close'] - self.data['open']).abs()
        total_size = self.data['high'] - self.data['low']
        shadow_size = total_size - body_size

        last_shadow_size = shadow_size
        mean_shadow_size = shadow_size.rolling(window=period).mean()
        mad_shadow_size = shadow_size.rolling(window=period).apply(self._get_numpy_mad, raw=True)

        raw_score = 5 + np.where(
            mad_shadow_size != 0, 
            (last_shadow_size - mean_shadow_size) / mad_shadow_size, 
            0
        )
        deviation = pd.Series(raw_score)
        return deviation.tolist()
    
    #------------------------------
    # Буквенний-численний символ. Четвертий
    #------------------------------

    #------------------------------
    # Метод перетворення різниці маштабу ціни свічки від вікна (Варіант 2)
    #------------------------------ 

    @_handle_error
    def _transform_price_scale_deviation_v2(self, custom_period=None):
        "Параметри: custom_period - необов'язковий параметр для вказівки власного періоду замість стандартного"
        period = custom_period if custom_period is not None else self.period

        price_scale = self.data['high'] - self.data['low']

        last_price_scale = price_scale
        mean_price_scale = price_scale.rolling(window=period).mean()
        mad_price_scale = price_scale.rolling(window=period).apply(self._get_numpy_mad, raw=True)

        raw_score = 5 + np.where(
            mad_price_scale != 0, 
            (last_price_scale - mean_price_scale) / mad_price_scale, 
            0
        )
        deviation = pd.Series(raw_score)
        return deviation.tolist()
    
    #------------------------------
    # Метод поєднання всіх символів в один рядок
    #------------------------------

    @_handle_error
    def get_combined_sequence_v2(self):
        "Параметри: немає. Використовує стандартний період, але можна викликати внутрішні методи з власним періодом для отримання окремих послідовностей"
        bsd_sequence = self._transform_to_bsd_v2()
        body_deviation_sequence = self._transform_body_deviation_v2()
        shadow_deviation_sequence = self._transform_shadow_deviation_v2()
        price_scale_deviation_sequence = self._transform_price_scale_deviation_v2()

        combined_sequence = []
        for i in range(len(bsd_sequence)):
            # Перевіряємо, чи є NaN хоча б в одному розрахунку відхилення
            if pd.isna(body_deviation_sequence[i]) or pd.isna(shadow_deviation_sequence[i]) or pd.isna(price_scale_deviation_sequence[i]):
                combined_sequence.append("N000") # Явний маркер відсутності даних
            else:
                # Якщо дані є, збираємо токен (перетворюючи цифри на int)
                combined_symbol = f"{bsd_sequence[i]}{int(body_deviation_sequence[i])}{int(shadow_deviation_sequence[i])}{int(price_scale_deviation_sequence[i])}"
                combined_sequence.append(combined_symbol)

        return combined_sequence