import pandas as pd
import time

from massive import RESTClient
from utils.DataBaseManager import DataBaseManager
from utils.OtherUtils import _handle_error, _save_to_db

# Декоратор для обчислення індикаторів та WCE
from utils.IndicatorDecorator import IndicatorDecorator

class MassiveModule:

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, db_manager: DataBaseManager, api_key: str, free_tier: bool = True, free_requests: int = 5, free_wait_minutes: int = 3):
        self.db_manager = db_manager
        self.client = RESTClient(api_key)
        self.free_tier = free_tier
        self.free_requests = free_requests
        self.free_wait_minutes = free_wait_minutes
        self.request_timestamps = []

    #------------------------------
    # Внутрішній метод перевірки лімітів (динамічно з налаштувань)
    #------------------------------
    def _check_rate_limit(self):
        if not self.free_tier:
            return
            
        current_time = time.time()
        window_seconds = self.free_wait_minutes * 60.0
        self.request_timestamps = [t for t in self.request_timestamps if current_time - t < window_seconds]
        
        if len(self.request_timestamps) >= self.free_requests:
            oldest = self.request_timestamps[0]
            wait_time = window_seconds - (current_time - oldest)
            if wait_time > 0:
                print(f"⏳ Massive API ліміт ({self.free_requests} зап/{self.free_wait_minutes}хв). Очікування {wait_time:.1f} сек...")
                time.sleep(wait_time)
            
            # Оновлюємо після очікування
            current_time = time.time()
            self.request_timestamps = [t for t in self.request_timestamps if current_time - t < window_seconds]
            
        self.request_timestamps.append(time.time())

    #------------------------------
    # Отримання даних про агрегації (OHLCV)
    #------------------------------

    @_save_to_db
    @IndicatorDecorator
    @_handle_error
    def _fetch_ohlcv(self, symbol, multiplier, timeframe, start_date=None, end_date=None, limit=50000, adjusted=True, sort="asc", internal_symbol=None):
        "Параметри: symbol - торговий символ (наприклад, 'C:EURUSD'), multiplier - множник, timeframe - таймфрейм (наприклад, 'minute'), start_date - початкова дата (формат 'YYYY-MM-DD'), end_date - кінцева дата (формат 'YYYY-MM-DD'), limit - максимальна кількість записів, adjusted - чи враховувати корекції, sort - порядок сортування ('asc' або 'desc')"
        
        self._check_rate_limit()
        
        aggs = list(self.client.list_aggs(
            symbol,
            multiplier,
            timeframe,
            start_date,
            end_date,
            adjusted=str(adjusted).lower(),
            sort=sort,
            limit=limit
        ))

        data = [vars(a) for a in aggs]
        df = pd.DataFrame(data)
        
        if internal_symbol:
            symbol_clean = internal_symbol
        else:
            from utils.SymbolManager import SymbolManager
            # Якщо internal_symbol не передано, спробуємо знайти найбільш прийнятний
            symbol_clean = symbol.replace(":", "")[1:]
            
        # Формуємо правильне ім'я таблиці (наприклад, 15m замість minute)
        suffix_map = {"minute": "m", "hour": "h", "day": "d"}
        suffix = f"{multiplier}{suffix_map.get(timeframe, timeframe)}"
        table_name = f"{symbol_clean}_{suffix}"

        return df, table_name
    
    #------------------------------
    # Автоматичне завантаження даних про агрегації (OHLCV) з API та збереження їх у базі даних. Розбиває завдання на частини, щоб уникнути проблем з обсягом даних.
    #------------------------------ 
    
    @_handle_error
    def fetch_ohlcv_auto_download(self, symbol, multiplier, timeframe, start_date=None, end_date=None, limit=None, adjusted=True, sort="asc", batch_size="30D", time_sleep=int(15), internal_symbol=None):
        """Автоматично завантажує дані про агрегації (OHLCV) з API та зберігає їх у базі даних.Розбиває завдання на частини, щоб уникнути проблем з обсягом даних. Параметри: symbol - торговий символ (наприклад, 'C:EURUSD'), multiplier - множник, timeframe - таймфрейм (наприклад, 'minute'), start_date - початкова дата (формат 'YYYY-MM-DD'), end_date - кінцева дата (формат 'YYYY-MM-DD'), adjusted - чи враховувати корекції, sort - порядок сортування ('asc' або 'desc'), batch_size - розмір кожного завантаження (наприклад, '50D' для 50 днів, рекомендовано використовувати тільки дні, щоб уникнути проблем з різною кількістю записів для різних таймфреймів), time_sleep - час у секундах для паузи між завантаженнями (щоб уникнути перевищення лімітів API)"""

        # Розбиваємо завдання на частини
        current_start = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        while current_start < end_date:
            current_end = current_start + pd.Timedelta(batch_size)
            if current_end > end_date:
                current_end = end_date + pd.Timedelta(days=1)

            self._fetch_ohlcv(
                symbol,
                multiplier,
                timeframe,
                start_date=current_start.strftime('%Y-%m-%d'),
                end_date=current_end.strftime('%Y-%m-%d'),
                limit=limit,
                adjusted=adjusted,
                sort=sort,
                internal_symbol=internal_symbol
            )

            current_start = current_end

            time.sleep(time_sleep)

    #------------------------------
    # Метод автоматичного заповнення пропусків в даних про агрегації (OHLCV) з API та збереження їх у базі даних.
    #------------------------------

    @_handle_error
    def fill_ohlcv_gaps(self, symbol, multiplier, timeframe, batch_size="30D", time_sleep=int(15), limit=None, adjusted=True, sort="asc"):
        """Автоматично заповнює пропуски в даних про агрегації (OHLCV) з API та зберігає їх у базі даних. Параметри: symbol - торговий символ (наприклад, 'C:EURUSD'), multiplier - множник, timeframe - таймфрейм (наприклад, 'minute'), batch_size - розмір кожного завантаження для заповнення пропусків (наприклад, '50D' для 50 днів, рекомендовано використовувати тільки дні, щоб уникнути проблем з різною кількістю записів для різних таймфреймів), time_sleep - час у секундах для паузи між завантаженнями (щоб уникнути перевищення лімітів API), limit - максимальна кількість записів для кожного завантаження, adjusted - чи враховувати корекції, sort - порядок сортування ('asc' або 'desc')"""

        symbol_clean = symbol.replace(":", "")[1:]
        
        # Формуємо правильне ім'я таблиці (наприклад, 15m замість minute)
        suffix_map = {"minute": "m", "hour": "h", "day": "d"}
        suffix = f"{multiplier}{suffix_map.get(timeframe, timeframe)}"
        table_name = f"{symbol_clean}_{suffix}"
        gaps = self.db_manager.get_time_gaps(table_name, timeframe_ms=self._timeframe_to_ms(timeframe) * multiplier)
        for gap in gaps:
            gap_start = pd.to_datetime(gap['gap_start'], unit='ms')
            gap_end = pd.to_datetime(gap['gap_end'], unit='ms')

            self.fetch_ohlcv_auto_download(
                symbol,
                multiplier,
                timeframe,
                start_date=gap_start.strftime('%Y-%m-%d'),
                end_date=gap_end.strftime('%Y-%m-%d'),
                batch_size=batch_size,
                time_sleep=time_sleep,
                limit=limit,
                adjusted=adjusted,
                sort=sort
            )

    #------------------------------
    # Внутрішній метод для конвертації таймфрейму в мілісекунди
    #------------------------------

    def _timeframe_to_ms(self, timeframe):
        """Конвертує таймфрейм у мілісекунди. Параметри: timeframe - таймфрейм (наприклад, 'minute', 'hour', 'day')"""
        if timeframe == "minute":
            return 60000
        elif timeframe == "hour":
            return 3600000
        elif timeframe == "day":
            return 86400000
        else:
            raise ValueError(f"Невідомий таймфрейм: {timeframe}. Підтримувані таймфрейми: 'minute', 'hour', 'day'.")