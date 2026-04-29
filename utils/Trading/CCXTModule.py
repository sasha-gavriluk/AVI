import ccxt
import pandas as pd

from utils.DataBaseManager import DataBaseManager
from utils.other_utils import _handle_error, _save_to_db

# Декоратор для обчислення індикаторів та WCE
from utils.IndicatorDecorator import IndicatorDecorator

class CCXTModule:

    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, exchange_name, db_manager: DataBaseManager):
        self.exchange = getattr(ccxt, exchange_name)()
        self.db_manager = db_manager
    
    # ----------------------------------
    # Підключення
    # ----------------------------------

    @_handle_error
    def connect(self, api_key, secret_key):
        "Параметри: api_key - ключ API, secret_key - секретний ключ"
        self.exchange.apiKey = api_key
        self.exchange.secret = secret_key
        self.exchange.enableRateLimit = True

    # ----------------------------------
    # Отримання балансу
    # ----------------------------------

    @_handle_error
    def fetch_balance(self):
        "Отримання балансу"
        balance = self.exchange.fetch_balance()
        balance_info = {
            "total": balance['total'],
            "free": balance['free'],
            "used": balance['used']
        }
        return balance_info

    # ----------------------------------
    # Отримання поточних цін (тикерів)
    # ----------------------------------

    @_handle_error
    def fetch_ticker(self, symbol):
        "Параметри: symbol - торговий символ (наприклад, 'BTC/USDT')"
        ticker = self.exchange.fetch_ticker(symbol)
        return ticker
    
    # ----------------------------------
    # Отримання історії свічок
    # ----------------------------------
    
    @_save_to_db
    @IndicatorDecorator
    @_handle_error
    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        "Параметри: symbol - торговий символ (наприклад, 'BTC/USDT'), timeframe - таймфрейм (наприклад, '1m'), since - початкова дата в мілісекундах, limit - кількість свічок для отримання"
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since, limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        symbol_clean = symbol.replace("/", "_")
        table_name = f"{symbol_clean}_{timeframe}"

        return df, table_name