import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE

class IndicatorProcessor:
    def __init__(self, data: pd.DataFrame, processed_data: pd.DataFrame, indicators_params=None):
        self.data = data
        self.processed_data = processed_data
        self.indicators_params = indicators_params if indicators_params is not None else []

    def _get_unique_column_name(self, base_name: str) -> str:
        """Return a unique column name based on base_name.

        If a column with base_name already exists in processed_data, a numeric
        suffix is appended. This allows the same indicator to be added multiple
        times even with identical parameters.
        """
        if base_name not in self.processed_data.columns:
            return base_name
        counter = 1
        new_name = f"{base_name}_{counter}"
        while new_name in self.processed_data.columns:
            counter += 1
            new_name = f"{base_name}_{counter}"
        return new_name

    # Окремі методи для кожного індикатора
    def add_sma(self, period=20):
        column = self._get_unique_column_name(f'SMA_{period}')
        self.processed_data[column] = self.data['close'].rolling(window=period).mean()

    def add_ema(self, period=20):
        column = self._get_unique_column_name(f'EMA_{period}')
        self.processed_data[column] = self.data['close'].ewm(span=period, adjust=False).mean()

    # ----------------------------------
    # Перетини ковзних середніх
    # ----------------------------------

    def add_sma_cross(self, period_short=10, period_long=50, column='close'):
        """Метод для визначення перетину двох SMA (швидкої та повільної)"""
        sma_short = self.data[column].rolling(window=period_short).mean()
        sma_long = self.data[column].rolling(window=period_long).mean()
        cross = (sma_short > sma_long).astype(int) - (sma_short < sma_long).astype(int)
        cross_column = self._get_unique_column_name(f"SMA_Cross_{period_short}_{period_long}")
        self.processed_data[cross_column] = cross

    def add_ema_cross(self, period_short=10, period_long=50, column='close'):
        """Метод для визначення перетину двох EMA (швидкої та повільної)"""
        ema_short = self.data[column].ewm(span=period_short, adjust=False).mean()
        ema_long = self.data[column].ewm(span=period_long, adjust=False).mean()
        cross = (ema_short > ema_long).astype(int) - (ema_short < ema_long).astype(int)
        cross_column = self._get_unique_column_name(f"EMA_Cross_{period_short}_{period_long}")
        self.processed_data[cross_column] = cross

    # ----------------------------------
    # Осцилятори
    # ----------------------------------

    def add_rsi(self, period=14, column='close'):
        """
        Метод для додавання індикатора RSI (Relative Strength Index).
        
        Параметри:
        - period: період (за замовчуванням 14)
        - column: колонка для розрахунку (зазвичай 'close')
        """
        delta = self.data[column].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        column = self._get_unique_column_name(f'RSI_{period}')
        self.processed_data[column] = rsi

    # ----------------------------------
    # Індикатор MACD
    # ----------------------------------

    def add_macd(self, fast_period=12, slow_period=26, signal_period=9, column='close'):
        """
        Метод для додавання індикатора MACD (Moving Average Convergence Divergence).
        
        Параметри:
        - fast_period: швидкий період (за замовчуванням 12)
        - slow_period: повільний період (за замовчуванням 26)
        - signal_period: сигнальний період (за замовчуванням 9)
        """
        short_ema = self.data[column].ewm(span=fast_period, adjust=False).mean()
        long_ema = self.data[column].ewm(span=slow_period, adjust=False).mean()
        macd = short_ema - long_ema
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        macd_hist = macd - signal

        # Save the MACD components with parameter-specific column names
        macd_column = self._get_unique_column_name(f'MACD_{fast_period}_{slow_period}_{signal_period}')
        signal_column = self._get_unique_column_name(f'MACD_Signal_{fast_period}_{slow_period}_{signal_period}')
        hist_column = self._get_unique_column_name(f'MACD_Hist_{fast_period}_{slow_period}_{signal_period}')

        self.processed_data[macd_column] = macd
        self.processed_data[signal_column] = signal
        self.processed_data[hist_column] = macd_hist

    # ----------------------------------
    # Смуги Боллінджера
    # ----------------------------------

    def add_bollinger_bands(self, period=20, std_multiplier=2, column='close'):
        """Метод для розрахунку та додавання смуг Боллінджера (Bollinger Bands)"""
        sma = self.data[column].rolling(window=period).mean()
        std = self.data[column].rolling(window=period).std()
        upper_band = sma + (std_multiplier * std)
        lower_band = sma - (std_multiplier * std)

        # Замінюємо крапку на підкреслення в std_multiplier
        std_multiplier_str = str(std_multiplier).replace('.', '_')

        upper_band_column = self._get_unique_column_name(f'Bollinger_Upper_{period}_{std_multiplier_str}')
        lower_band_column = self._get_unique_column_name(f'Bollinger_Lower_{period}_{std_multiplier_str}')
        middle_band_column = self._get_unique_column_name(f'Bollinger_Middle_{period}')

        self.processed_data[upper_band_column] = upper_band
        self.processed_data[lower_band_column] = lower_band
        self.processed_data[middle_band_column] = sma

    # ----------------------------------
    # Стохастик
    # ----------------------------------

    def add_stochastic(self, k_period=14, d_period=3, column='close'):
        """
        Метод для додавання індикатора Stochastic Oscillator до даних.

        Параметри:
        - k_period: int, період для %K лінії
        - d_period: int, період для %D лінії (сигнальна лінія)
        - column: str, колонка для розрахунку (зазвичай 'close')
        """
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

    # ----------------------------------
    # ADX (Average Directional Index)
    # ----------------------------------

    def add_adx(self, period=14):
        """Метод для розрахунку індикатора сили тренду ADX"""
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        plus_dm = high.diff()
        minus_dm = low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / atr)

        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.ewm(alpha=1/period).mean()

        column = self._get_unique_column_name(f'ADX_{period}')
        self.processed_data[column] = adx
        # print(f"ADX_{period} - Min: {adx.min()}, Mean: {adx.mean()}, Max: {adx.max()}")

    # ----------------------------------
    # ATR (Average True Range)
    # ----------------------------------

    def add_atr(self, period=14):
        """Метод для розрахунку істинного діапазону волатильності ATR"""
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = true_range.rolling(window=period).mean()
        column = self._get_unique_column_name(f'ATR_{period}')
        self.processed_data[column] = atr  

    # ----------------------------------
    # Williams %R
    # ----------------------------------

    def add_williamsr(self, period=14):
        """Метод для розрахунку індикатора Williams %R"""
        high = self.data['high']
        low = self.data['low']
        close = self.data['close']

        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()

        williams_r = -100 * (highest_high - close) / (highest_high - lowest_low)
        column = self._get_unique_column_name(f'WilliamsR_{period}')
        self.processed_data[column] = williams_r

    # ----------------------------------
    # CCI (Commodity Channel Index)
    # ----------------------------------

    def add_cci(self, period=20):
        """Метод для розрахунку індикатора CCI"""
        tp = (self.data['high'] + self.data['low'] + self.data['close']) / 3
        sma_tp = tp.rolling(window=period).mean()
        mean_dev = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
        cci = (tp - sma_tp) / (0.015 * mean_dev)
        column = self._get_unique_column_name(f'CCI_{period}')
        self.processed_data[column] = cci

    # ----------------------------------
    # Keltner Channel
    # ----------------------------------

    def add_keltner_channel(self, period=20, multiplier=2):
        """
        Метод для розрахунку каналів Кельтнера.
        Обчислює Keltner Channel без використання ATR (на базі середнього діапазону).
        """
        typical_price = (self.processed_data['high'] + self.processed_data['low'] + self.processed_data['close']) / 3
        middle_band = typical_price.ewm(span=period, adjust=False).mean()

        # Обчислення середнього діапазону між High і Low
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

    # ----------------------------------
    # Об'ємні індикатори
    # ----------------------------------

    def add_volume_avg(self, period=20):
        """Метод для розрахунку ковзної середньої об'єму"""
        column = self._get_unique_column_name(f'Volume_Avg_{period}')
        self.processed_data[column] = self.data['volume'].rolling(window=period).mean()

    # ----------------------------------
    # Wrap Candle Engine (WCE)
    # ----------------------------------

    def add_wce(self, period=10):
        """Метод для перетворення свічок у токени WCE (напр. B555, S234)"""
        wce = WCE(self.data, period=period)
        column = self._get_unique_column_name(f'WCE_{period}')
        self.processed_data[column] = wce.get_combined_sequence_v2()

    # ----------------------------------
    # Кластеризація ринку (Market States)
    # ----------------------------------

    def add_market_state_linear(self, period=20, slope_threshold=0.05, vol_threshold=1.5):
        """
        Метод лінійної кластеризації станів ринку.
        Визначає стан ринку на основі нормалізованого нахилу лінійної регресії та волатильності.
        Стани:
         1: 'uptrend' (Висхідний тренд)
        -1: 'downtrend' (Низхідний тренд)
         0: 'flat' (Боковик)
         3: 'volatility' (Висока волатильність/хаос)
        """
        close_prices = self.data['close']

        # 1. Розрахунок нахилу лінійної регресії (Slope)
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

        # Нормалізуємо нахил (відсоток зміни за одиницю часу)
        normalized_slope = (slope / close_prices) * 100

        # 2. Розрахунок волатильності
        sma = close_prices.rolling(window=period).mean()
        std_dev = close_prices.rolling(window=period).std()
        normalized_volatility = (std_dev / sma) * 100

        # Визначаємо відносну волатильність до середньої за довгий період
        long_period = period * 4
        avg_volatility = normalized_volatility.rolling(window=long_period).mean()
        volatility_ratio = normalized_volatility / avg_volatility

        # 3. Кластеризація (Маркування станів)
        states = pd.Series(0, index=self.data.index)

        # Логіка станів
        vol_condition = volatility_ratio > vol_threshold
        uptrend_condition = (normalized_slope > slope_threshold) & (~vol_condition)
        downtrend_condition = (normalized_slope < -slope_threshold) & (~vol_condition)

        states.loc[uptrend_condition] = 1
        states.loc[downtrend_condition] = -1
        states.loc[vol_condition] = 3

        # Зберігаємо результати
        column_slope = self._get_unique_column_name(f'Market_Slope_{period}')
        column_vol = self._get_unique_column_name(f'Market_VolRatio_{period}')
        column_state = self._get_unique_column_name(f'Market_State_Linear_{period}')

        self.processed_data[column_slope] = normalized_slope
        self.processed_data[column_vol] = volatility_ratio
        self.processed_data[column_state] = states

    # ----------------------------------
    # Головна функція
    # ----------------------------------

    def process_data(self):
        """Метод-оркестратор для обробки та виклику всіх вказаних індикаторів"""

        # Мапимо імена функцій на методи
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
            # Якщо параметри передані
            for indicator in self.indicators_params:
                name = indicator.get('name')
                params = indicator.get('parameters', {})

                if name in indicator_methods:
                    indicator_methods[name](**params)
                else:
                    print(f"Індикатор '{name}' не підтримується.")
        else:
            # Якщо параметри не передані — запускаємо всі індикатори зі стандартними значеннями
            for method in indicator_methods.values():
                method()

        return self.processed_data

# ==================================
# Клас для виявлення свічкових патернів
# ==================================
