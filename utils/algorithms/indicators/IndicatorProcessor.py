import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE

from utils.OtherUtils import _handle_error

class IndicatorProcessor:
    "Процесор для пакетного обчислення індикаторів"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame, indicators_params=None):
        self.data = data
        self.processed_data = processed_data
        self.indicators_params = indicators_params if indicators_params is not None else []

    #------------------------------
    # Внутрішній метод для генерації унікального імені колонки
    #------------------------------

    def _get_unique_column_name(self, base_name: str) -> str:
        "Додає суфікс, якщо колонка з таким ім'ям вже існує (дозволяє багаторазовий запуск однакових індикаторів)"
        if base_name not in self.processed_data.columns:
            return base_name
        counter = 1
        new_name = f"{base_name}_{counter}"
        while new_name in self.processed_data.columns:
            counter += 1
            new_name = f"{base_name}_{counter}"
        return new_name

    #------------------------------
    # Прості ковзні середні (SMA, EMA)
    #------------------------------

    @_handle_error
    def add_sma(self, period=20):
        "Метод для розрахунку SMA"
        column = self._get_unique_column_name(f'SMA_{period}')
        self.processed_data[column] = self.data['close'].rolling(window=period).mean()

    @_handle_error
    def add_ema(self, period=20):
        "Метод для розрахунку EMA"
        column = self._get_unique_column_name(f'EMA_{period}')
        self.processed_data[column] = self.data['close'].ewm(span=period, adjust=False).mean()

    #------------------------------
    # Перетини ковзних середніх
    #------------------------------

    @_handle_error
    def add_sma_cross(self, period_short=10, period_long=50, column='close'):
        "Метод для визначення перетину двох SMA (швидкої та повільної)"
        sma_short = self.data[column].rolling(window=period_short).mean()
        sma_long = self.data[column].rolling(window=period_long).mean()
        cross = (sma_short > sma_long).astype(int) - (sma_short < sma_long).astype(int)
        cross_column = self._get_unique_column_name(f"SMA_Cross_{period_short}_{period_long}")
        self.processed_data[cross_column] = cross

    @_handle_error
    def add_ema_cross(self, period_short=10, period_long=50, column='close'):
        "Метод для визначення перетину двох EMA (швидкої та повільної)"
        ema_short = self.data[column].ewm(span=period_short, adjust=False).mean()
        ema_long = self.data[column].ewm(span=period_long, adjust=False).mean()
        cross = (ema_short > ema_long).astype(int) - (ema_short < ema_long).astype(int)
        cross_column = self._get_unique_column_name(f"EMA_Cross_{period_short}_{period_long}")
        self.processed_data[cross_column] = cross

    #------------------------------
    # Осцилятори (RSI)
    #------------------------------

    @_handle_error
    def add_rsi(self, period=14, column='close'):
        "Метод для додавання індикатора RSI (Relative Strength Index)"
        delta = self.data[column].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        col_name = self._get_unique_column_name(f'RSI_{period}')
        self.processed_data[col_name] = rsi

    #------------------------------
    # MACD
    #------------------------------

    @_handle_error
    def add_macd(self, fast_period=12, slow_period=26, signal_period=9, column='close'):
        "Метод для додавання індикатора MACD (Moving Average Convergence Divergence)"
        short_ema = self.data[column].ewm(span=fast_period, adjust=False).mean()
        long_ema = self.data[column].ewm(span=slow_period, adjust=False).mean()
        macd = short_ema - long_ema
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        macd_hist = macd - signal

        macd_column = self._get_unique_column_name(f'MACD_{fast_period}_{slow_period}_{signal_period}')
        signal_column = self._get_unique_column_name(f'MACD_Signal_{fast_period}_{slow_period}_{signal_period}')
        hist_column = self._get_unique_column_name(f'MACD_Hist_{fast_period}_{slow_period}_{signal_period}')

        self.processed_data[macd_column] = macd
        self.processed_data[signal_column] = signal
        self.processed_data[hist_column] = macd_hist

    #------------------------------
    # Смуги Боллінджера
    #------------------------------

    @_handle_error
    def add_bollinger_bands(self, period=20, std_multiplier=2, column='close'):
        "Метод для розрахунку та додавання смуг Боллінджера (Bollinger Bands)"
        sma = self.data[column].rolling(window=period).mean()
        std = self.data[column].rolling(window=period).std()
        upper_band = sma + (std_multiplier * std)
        lower_band = sma - (std_multiplier * std)

        std_multiplier_str = str(std_multiplier).replace('.', '_')
        upper_band_column = self._get_unique_column_name(f'Bollinger_Upper_{period}_{std_multiplier_str}')
        lower_band_column = self._get_unique_column_name(f'Bollinger_Lower_{period}_{std_multiplier_str}')
        middle_band_column = self._get_unique_column_name(f'Bollinger_Middle_{period}')

        self.processed_data[upper_band_column] = upper_band
        self.processed_data[lower_band_column] = lower_band
        self.processed_data[middle_band_column] = sma

    #------------------------------
    # Стохастик (Stochastic)
    #------------------------------

    @_handle_error
    def add_stochastic(self, k_period=14, d_period=3, column='close'):
        "Метод для додавання індикатора Stochastic Oscillator"
        high = self.data['high']
        low = self.data['low']
        close = self.data[column]

        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()

        stochastic_k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        stochastic_d = stochastic_k.rolling(window=d_period).mean()

        k_column = self._get_unique_column_name(f'Stochastic_K_{k_period}')
        d_column = self._get_unique_column_name(f'Stochastic_D_{d_period}')

        self.processed_data[k_column] = stochastic_k
        self.processed_data[d_column] = stochastic_d

    #------------------------------
    # Сила тренду (ADX)
    #------------------------------

    @_handle_error
    def add_adx(self, period=14):
        "Метод для розрахунку індикатора сили тренду ADX"
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        plus_dm = high.diff()
        minus_dm = low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / atr)

        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di)) * 100
        adx = dx.ewm(alpha=1/period).mean()

        col_name = self._get_unique_column_name(f'ADX_{period}')
        self.processed_data[col_name] = adx

    #------------------------------
    # Волатильність (ATR)
    #------------------------------

    @_handle_error
    def add_atr(self, period=14):
        "Метод для розрахунку істинного діапазону волатильності ATR"
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = true_range.rolling(window=period).mean()
        col_name = self._get_unique_column_name(f'ATR_{period}')
        self.processed_data[col_name] = atr  

    #------------------------------
    # Williams %R
    #------------------------------

    @_handle_error
    def add_williamsr(self, period=14):
        "Метод для розрахунку індикатора Williams %R"
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()

        williams_r = -100 * (highest_high - close) / (highest_high - lowest_low)
        col_name = self._get_unique_column_name(f'WilliamsR_{period}')
        self.processed_data[col_name] = williams_r

    #------------------------------
    # CCI (Commodity Channel Index)
    #------------------------------

    @_handle_error
    def add_cci(self, period=20):
        "Метод для розрахунку індикатора CCI"
        tp = (self.data['high'] + self.data['low'] + self.data['close']) / 3
        sma_tp = tp.rolling(window=period).mean()
        mean_dev = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
        cci = (tp - sma_tp) / (0.015 * mean_dev)
        col_name = self._get_unique_column_name(f'CCI_{period}')
        self.processed_data[col_name] = cci

    #------------------------------
    # Канали Кельтнера (Keltner Channel)
    #------------------------------

    @_handle_error
    def add_keltner_channel(self, period=20, multiplier=2):
        "Метод для розрахунку каналів Кельтнера без використання ATR (на базі середнього діапазону)"
        typical_price = (self.processed_data['high'] + self.processed_data['low'] + self.processed_data['close']) / 3
        middle_band = typical_price.ewm(span=period, adjust=False).mean()

        high_low_range = self.processed_data['high'] - self.processed_data['low']
        average_range = high_low_range.rolling(window=period).mean()

        upper_band = middle_band + (multiplier * average_range)
        lower_band = middle_band - (multiplier * average_range)

        middle_column = self._get_unique_column_name(f'Keltner_Middle_{period}')
        upper_column = self._get_unique_column_name(f'Keltner_Upper_{period}')
        lower_column = self._get_unique_column_name(f'Keltner_Lower_{period}')

        self.processed_data[middle_column] = middle_band
        self.processed_data[upper_column] = upper_band
        self.processed_data[lower_column] = lower_band

    #------------------------------
    # Об'єм
    #------------------------------

    @_handle_error
    def add_volume_avg(self, period=20):
        "Метод для розрахунку ковзної середньої об'єму"
        col_name = self._get_unique_column_name(f'Volume_Avg_{period}')
        self.processed_data[col_name] = self.data['volume'].rolling(window=period).mean()

    #------------------------------
    # Wrap Candle Engine (WCE)
    #------------------------------

    @_handle_error
    def add_wce(self, period=10):
        "Метод для перетворення свічок у токени WCE (напр. B555, S234)"
        wce = WCE(self.data, period=period)
        col_name = self._get_unique_column_name(f'WCE_{period}')
        self.processed_data[col_name] = wce.get_combined_sequence_v2()

    #------------------------------
    # Кластеризація ринку (Market States Linear)
    #------------------------------

    @_handle_error
    def add_market_state_linear(self, period=20, atr_period=14, slope_atr_threshold=0.07, vol_threshold=1.5):
        "Метод лінійної кластеризації станів ринку (1: uptrend, -1: downtrend, 0: flat, 3: volatility)"
        close_prices = self.data['close']

        x = np.arange(period)
        x_mean = x.mean()
        x_diff = x - x_mean
        x_diff_sq_sum = (x_diff ** 2).sum()
        
        if x_diff_sq_sum == 0:
            x_diff_sq_sum = 1e-10

        def calc_slope(y):
            y_mean = np.mean(y)
            return np.sum(x_diff * (y - y_mean)) / x_diff_sq_sum

        slope = close_prices.rolling(window=period).apply(calc_slope, raw=True)

        sma = close_prices.rolling(window=period).mean()
        std_dev = close_prices.rolling(window=period).std()
        normalized_volatility = (std_dev / sma) * 100

        long_period = period * 4
        avg_volatility = normalized_volatility.rolling(window=long_period).mean()
        volatility_ratio = normalized_volatility / avg_volatility

        atr_col = f'ATR_{atr_period}'
        if atr_col in self.processed_data.columns:
            atr = self.processed_data[atr_col]
        else:
            tr1 = self.data['high'] - self.data['low']
            tr2 = (self.data['high'] - close_prices.shift()).abs()
            tr3 = (self.data['low'] - close_prices.shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=atr_period).mean()

        states = pd.Series(0, index=self.data.index)

        vol_condition = volatility_ratio > vol_threshold
        uptrend_condition = (slope > atr * slope_atr_threshold) & (~vol_condition)
        downtrend_condition = (slope < -atr * slope_atr_threshold) & (~vol_condition)

        states.loc[uptrend_condition] = 1
        states.loc[downtrend_condition] = -1
        states.loc[vol_condition] = 3

        column_slope = self._get_unique_column_name(f'Market_Slope_{period}')
        column_vol = self._get_unique_column_name(f'Market_VolRatio_{period}')
        column_state = self._get_unique_column_name(f'Market_State_Linear_{period}')

        slope_atr_ratio = slope / atr
        
        self.processed_data[column_slope] = slope_atr_ratio
        self.processed_data[column_vol] = volatility_ratio
        self.processed_data[column_state] = states

    #------------------------------
    # Оркестратор
    #------------------------------

    @_handle_error
    def process_data(self):
        "Метод-оркестратор для виклику всіх вказаних індикаторів з параметрами"
        indicator_methods = {
            'SMA': self.add_sma,
            'EMA': self.add_ema,
            'SMA_Cross': self.add_sma_cross,
            'EMA_Cross': self.add_ema_cross,
            'RSI': self.add_rsi,
            'MACD': self.add_macd,
            'Bollinger_Bands': self.add_bollinger_bands,
            'Stochastic': self.add_stochastic,
            'WilliamsR': self.add_williamsr,
            'CCI': self.add_cci,
            'ADX': self.add_adx,
            'ATR': self.add_atr,
            'Keltner_Channel': self.add_keltner_channel,
            'Volume_Avg': self.add_volume_avg,
            'Market_State_Linear': self.add_market_state_linear,
        }

        if self.indicators_params:
            for indicator in self.indicators_params:
                name = indicator.get('name')
                params = indicator.get('parameters', {})
                if name in indicator_methods:
                    indicator_methods[name](**params)
                else:
                    print(f"Індикатор '{name}' не підтримується.")
        else:
            for method in indicator_methods.values():
                method()

        return self.processed_data
