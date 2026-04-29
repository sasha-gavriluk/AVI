import pandas as pd
import time

from massive import RESTClient
from utils.DataBaseManager import DataBaseManager
from utils.other_utils import _handle_error, _save_to_db

# Декоратор для обчислення індикаторів та WCE
from utils.IndicatorDecorator import IndicatorDecorator

class MassiveModule:

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, db_manager: DataBaseManager, api_key: str):
        self.db_manager = db_manager
        self.client = RESTClient(api_key)

    #------------------------------
    # Отримання даних про агрегації (OHLCV)
    #------------------------------

    @_save_to_db
    @IndicatorDecorator
    @_handle_error
    def _fetch_ohlcv(self, symbol, multiplier, timeframe, start_date=None, end_date=None, limit=None, adjusted=True, sort="asc"):
        "Параметри: symbol - торговий символ (наприклад, 'C:EURUSD'), multiplier - множник, timeframe - таймфрейм (наприклад, 'minute'), start_date - початкова дата (формат 'YYYY-MM-DD'), end_date - кінцева дата (формат 'YYYY-MM-DD'), limit - максимальна кількість записів, adjusted - чи враховувати корекції, sort - порядок сортування ('asc' або 'desc')"
        
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
        symbol_clean = symbol.replace(":", "")[1:]
        table_name = f"{symbol_clean}_{timeframe}"

        return df, table_name
    
    #------------------------------
    # Автоматичне завантаження даних про агрегації (OHLCV) з API та збереження їх у базі даних. Розбиває завдання на частини, щоб уникнути проблем з обсягом даних.
    #------------------------------ 
    
    @_handle_error
    def fetch_ohlcv_auto_download(self, symbol, multiplier, timeframe, start_date=None, end_date=None, limit=None, adjusted=True, sort="asc", batch_size="30D", time_sleep=int(15)):
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
                sort=sort
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
        table_name = f"{symbol_clean}_{timeframe}"
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