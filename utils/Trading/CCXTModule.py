import ccxt
import time
import pandas as pd

from utils.DataBaseManager import DataBaseManager
from utils.other_utils import _handle_error, _save_to_db

# Декоратор для обчислення індикаторів та WCE
from utils.IndicatorDecorator import IndicatorDecorator

class CCXTModule:

    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, exchange_name: str, db_manager: DataBaseManager):
        self.exchange_name = exchange_name.lower()
        self.db_manager = db_manager
        
        # Обробка Bybit linear та інших особливостей ф'ючерсів
        exid = self.exchange_name
        if exid in ("binance", "binanceusdm", "binance-futures", "binance_futures"):
            exid = "binanceusdm"
            
        opts = {}
        if exid == "bybit":
            opts = {"defaultType": "swap"}
            
        self.exchange = getattr(ccxt, exid)({"options": opts})
        self.ccxt_id = exid

    # ----------------------------------
    # Підключення
    # ----------------------------------

    @_handle_error
    def connect(self, api_key: str, secret_key: str):
        "Параметри: api_key - ключ API, secret_key - секретний ключ"
        self.exchange.apiKey = api_key
        self.exchange.secret = secret_key
        self.exchange.enableRateLimit = True
        self.exchange.load_markets()
        print(f"[{self.exchange_name.upper()}] Підключено як {self.ccxt_id}.")

    def is_connected(self) -> bool:
        return self.exchange.apiKey is not None
        
    def disconnect(self):
        self.exchange.apiKey = None
        self.exchange.secret = None
        print(f"[{self.exchange_name.upper()}] Відключено вручну.")

    # ----------------------------------
    # Утиліти
    # ----------------------------------
    
    def _get_market_symbol(self, symbol: str, params={}):
        """
        Перетворює стандартний символ у біржовий, якщо потрібно (Bybit/linear -> ':USDT').
        """
        if self.exchange_name == 'bybit' and params.get('category', 'linear') == 'linear':
            if ':' not in symbol and 'USDT' in symbol and '/' in symbol:
                return f"{symbol}:USDT"
        return symbol

    # ----------------------------------
    # Отримання балансу
    # ----------------------------------

    @_handle_error
    def fetch_balance(self):
        "Отримання балансу"
        if self.exchange_name == 'bybit':
            balance = self.exchange.fetch_balance(params={'accountType': 'UNIFIED'})
        else:
            balance = self.exchange.fetch_balance()
            
        balance_info = {
            "total": balance.get('total', {}),
            "free": balance.get('free', {}),
            "used": balance.get('used', {})
        }
        return balance_info
        
    @_handle_error
    def get_usdt_balance(self) -> float:
        balance_data = self.fetch_balance()
        usdt_info = balance_data.get('free', {})
        return float(usdt_info.get('USDT', 0.0))

    # ----------------------------------
    # Отримання поточних цін (тикерів)
    # ----------------------------------

    @_handle_error
    def fetch_ticker(self, symbol):
        "Параметри: symbol - торговий символ (наприклад, 'BTC/USDT')"
        ticker = self.exchange.fetch_ticker(symbol)
        return ticker
        
    @_handle_error
    def fetch_all_symbols(self):
        if not self.exchange.markets:
            self.exchange.load_markets()
        return list(self.exchange.markets.keys())

    # ----------------------------------
    # Отримання історії свічок
    # ----------------------------------
    
    @_save_to_db
    @IndicatorDecorator
    @_handle_error
    def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
        "Параметри: symbol - торговий символ, timeframe - таймфрейм ('1m'), since - початкова дата, limit - кількість"
        
        market_symbol = self._get_market_symbol(symbol)
        ohlcv = self.exchange.fetch_ohlcv(market_symbol, timeframe, since, limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        symbol_clean = symbol.replace("/", "_").replace(":", "_")
        table_name = f"{symbol_clean}_{timeframe}"

        return df, table_name
        
    # ----------------------------------
    # Торгові операції (Ордери, Позиції, Плече)
    # ----------------------------------
    
    @_handle_error
    def set_leverage(self, symbol: str, leverage: int, params={}):
        if not self.exchange.has.get('setLeverage'):
            print(f"[{self.exchange_name.upper()}] Біржа не підтримує встановлення плеча через API.")
            return
            
        try:
            market_symbol = self._get_market_symbol(symbol, params)
            self.exchange.set_leverage(leverage, market_symbol, params)
            print(f"[{self.exchange_name.upper()}] Встановлено плече {leverage}x для {market_symbol}.")
        except Exception as e:
            error_message = str(e)
            if "leverage not modified" in error_message or "110043" in error_message:
                print(f"[{self.exchange_name.upper()}] Плече вже {leverage}x для {market_symbol}.")
            else:
                print(f"[{self.exchange_name.upper()}] Помилка встановлення плеча для {symbol}: {e}")
                raise e

    @_handle_error
    def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: float = None, params={}, stop_loss: float = None, take_profit: float = None, leverage: int = None):
        order_params = params.copy()
        
        if self.exchange_name == 'bybit':
            order_params.update({'category': 'linear'})
            
        market_symbol = self._get_market_symbol(symbol, order_params)
        
        if leverage is not None:
            self.set_leverage(symbol, leverage, order_params)
            
        if self.exchange_name == 'bybit':
            if stop_loss:
                order_params['stopLoss'] = str(stop_loss)
            if take_profit:
                order_params['takeProfit'] = str(take_profit)
                
        order = self.exchange.create_order(market_symbol, order_type, side, amount, price, order_params)
        print(f"[{self.exchange_name.upper()}] Ордер створено: {order['id']}")
        return order

    @_handle_error
    def fetch_positions(self, symbols: list, params={}):
        if not self.exchange.has.get('fetchPositions'):
            return {}
            
        params = params.copy()
        if self.exchange_name == 'bybit':
            params.update({'category': 'linear'})
            
        market_symbols = [self._get_market_symbol(s, params) for s in symbols]
        symbol_map = {m: s for s, m in zip(symbols, market_symbols)}
        
        positions = self.exchange.fetch_positions(symbols=market_symbols, params=params)
        result = {}
        for pos in positions:
            size = pos.get('size', 0) or pos.get('contracts', 0)
            if size and float(size) > 0:
                market_symbol = pos.get('symbol')
                std_symbol = symbol_map.get(market_symbol, market_symbol)
                result[std_symbol] = pos
        return result

    @_handle_error
    def close_position(self, symbol: str, params={}):
        if self.exchange_name == 'bybit':
            params.update({'category': 'linear'})
            
        market_symbol = self._get_market_symbol(symbol, params)
        positions = self.exchange.fetch_positions(symbols=[market_symbol], params=params)
        open_positions = [p for p in positions if p.get('contracts') is not None and float(p.get('contracts', 0)) > 0]
        
        if not open_positions:
            print(f"[{self.exchange_name.upper()}] Не знайдено відкритих позицій для {symbol}.")
            return None
            
        position_to_close = open_positions[0]
        amount = float(position_to_close['contracts'])
        side = 'sell' if position_to_close['side'] == 'long' else 'buy'
        
        print(f"[{self.exchange_name.upper()}] Закриття {position_to_close['side']} позиції {symbol} розміром {amount}...")
        close_order = self.create_order(symbol, 'market', side, amount, params=params)
        return close_order
        
    @_handle_error
    def fetch_open_orders(self, symbol: str = None, since: int = None, limit: int = None, params: dict = None):
        if not self.exchange.has.get('fetchOpenOrders'):
            return []
            
        params = (params or {}).copy()
        if self.exchange_name == 'bybit' and 'category' not in params:
            params['category'] = 'linear'
            
        if symbol:
            market_symbol = self._get_market_symbol(symbol, params)
            return self.exchange.fetch_open_orders(market_symbol, since=since, limit=limit, params=params)
            
        try:
            return self.exchange.fetch_open_orders(None, since=since, limit=limit, params=params)
        except Exception:
            pass
            
        if not self.exchange.markets:
            self.exchange.load_markets()
            
        out = []
        for sym in self.exchange.symbols:
            ms = self._get_market_symbol(sym, params)
            try:
                chunk = self.exchange.fetch_open_orders(ms, since=since, limit=limit, params=params)
                if chunk:
                    out.extend(chunk)
            except Exception:
                pass
            time.sleep(self.exchange.rateLimit / 1000.0)
        return out
        
    @_handle_error
    def fetch_last_trades(self, symbol: str, limit: int = 50, params: dict = None, sort_ascending: bool = True):
        if not self.exchange.has.get('fetchMyTrades'):
            return []
            
        params = (params or {}).copy()
        if self.exchange_name == 'bybit' and 'category' not in params:
            params['category'] = 'linear'
            
        market_symbol = self._get_market_symbol(symbol, params)
        since_timestamp = params.pop('since', None)
        trades = self.exchange.fetch_my_trades(market_symbol, since=since_timestamp, limit=limit, params=params) or []
        
        if sort_ascending:
            trades.sort(key=lambda t: t.get('timestamp') or 0)
        return trades

    @_handle_error
    def fetch_my_trades(self, symbol: str, since: int = None, limit: int = 20, params: dict = None):
        params = (params or {}).copy()
        if self.exchange_name == 'bybit' and 'category' not in params:
            params['category'] = 'linear'
        market_symbol = self._get_market_symbol(symbol, params)
        return self.exchange.fetch_my_trades(market_symbol, since=since, limit=limit, params=params)