class SymbolManager:
    """
    Централізований менеджер для конвертації назв активів (символів) 
    між внутрішнім форматом додатку (наприклад, EURUSD, BTC_USDT) 
    та форматами зовнішніх API (Massive Polygon, CCXT тощо).
    """

    @staticmethod
    @_handle_error
    def get_market_type(symbol: str) -> str:
        "Визначає ринок активу (crypto, forex, stocks)."
        if "_" in symbol or symbol.startswith("X:"):
            return "crypto"
        elif len(symbol) == 6 and symbol.isupper() and symbol.isalpha():
            return "forex"
        elif symbol.startswith("C:"):
            return "forex"
        else:
            # За замовчуванням вважаємо акціями, якщо не підпадає під інші
            return "stocks"

    @staticmethod
    @_handle_error
    def format_for_massive_rest(symbol: str) -> str:
        "Форматує символ для Massive REST API (наприклад, C:EURUSD, X:BTCUSD)."
        market = SymbolManager.get_market_type(symbol)
        if market == "crypto":
            clean_sym = symbol.replace("X:", "").replace("_", "")
            return f"X:{clean_sym}"
        elif market == "forex":
            clean_sym = symbol.replace("C:", "")
            return f"C:{clean_sym}"
        else:
            return symbol # Акції зазвичай йдуть як є (AAPL)

    @staticmethod
    @_handle_error
    def format_for_massive_ws(symbol: str) -> tuple:
        "Повертає кортеж (market_type, ws_subscription_string) для Polygon WebSocket."
        market = SymbolManager.get_market_type(symbol)
        if market == "crypto":
            # Polygon зазвичай використовує пари з USD (наприклад, BTC-USD замість BTC-USDT)
            if symbol.endswith("USDT"):
                symbol = symbol[:-4] + "USD"
            
            # Для крипти Polygon WS канали: XT (trades), XQ (quotes), XA (aggs). Символ містить дефіс.
            clean_sym = symbol.replace("X:", "").replace("_", "-")
            return ("crypto", f"XT.{clean_sym}")
        elif market == "forex":
            # Для форексу Polygon WS канали: C (quotes/trades), CA (aggs).
            clean_sym = symbol.replace("C:", "").replace("_", "").replace("/", "")
            return ("forex", f"C.{clean_sym}")
        else:
            return ("stocks", f"T.{symbol}")

    @staticmethod
    @_handle_error
    def format_for_ccxt(symbol: str) -> str:
        "Форматує символ для CCXT (наприклад, BTC/USDT)."
        # Базова заміна для крипти
        if "_" in symbol:
            return symbol.replace("_", "/")
        
        # Якщо це щось на кшталт BTCUSDT без підкреслення
        for stable in ["USDT", "BUSD", "USDC", "USD", "BTC", "ETH"]:
            if symbol.endswith(stable) and len(symbol) > len(stable):
                base = symbol[:-len(stable)]
                return f"{base}/{stable}"
                
        return symbol

    @staticmethod
    @_handle_error
    def extract_internal_symbol(polygon_sym: str, known_symbols: list) -> str:
        "Повертає оригінальну (внутрішню) назву символу, співставляючи її з відомими символами."
        if polygon_sym in known_symbols:
            return polygon_sym
            
        # Якщо прийшло C:EURUSD або X:BTCUSD або BTC-USD
        clean_polygon = polygon_sym.replace("C:", "").replace("X:", "").replace("-", "").replace("/", "")
        
        # Для крипти: якщо Polygon віддає USD, а в нас USDT (або навпаки), нормалізуємо обидва до USD
        if clean_polygon.endswith("USDT"):
            clean_polygon = clean_polygon[:-4] + "USD"
            
        for known in known_symbols:
            clean_known = known.replace("C:", "").replace("X:", "").replace("_", "").replace("-", "").replace("/", "")
            if clean_known.endswith("USDT"):
                clean_known = clean_known[:-4] + "USD"
                
            if clean_polygon == clean_known:
                return known
                
        return polygon_sym
