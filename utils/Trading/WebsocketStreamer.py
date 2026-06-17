import time
import asyncio
from PyQt6.QtCore import QThread, pyqtSignal
from utils.Trading.TickAggregator import TickAggregator

class WebsocketStreamerThread(QThread):
    """
    Фоновий потік для WebSocket підключення (Live Data Streaming).
    Підтримує масове підключення до Polygon.io (через пакет massive).
    """
    log_signal = pyqtSignal(str)
    candle_closed_signal = pyqtSignal(str, dict) # (table_name, closed_candle_dict)
    flush_ticks_signal = pyqtSignal(str, list) # (symbol, list_of_ticks)
    
    def __init__(self, provider: str, symbols: list):
        super().__init__()
        self.provider = provider
        self.symbols = symbols
        self.is_running = True
        
        # Читаємо вибрані таймфрейми з налаштувань (або беремо 1m за замовчуванням)
        try:
            import json, os
            from gui.logic.SettingsLogic import SettingsLogic
            from utils.PathManager import PathManager
            config_path = PathManager.get_settings_path()
            target_tfs = ["1m"]
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                    target_tfs = settings_data.get("copilot", {}).get("target_tfs", ["1m"])
                    if not target_tfs: target_tfs = ["1m"]
        except Exception:
            target_tfs = ["1m"]
            
        # Конвертація таймфреймів у мілісекунди
        tf_ms_map = {"1m": 60000, "3m": 180000, "5m": 300000, "15m": 900000, "30m": 1800000, "1h": 3600000, "2h": 7200000, "4h": 14400000, "1d": 86400000}
        
        self.aggregators = {}
        for sym in symbols:
            self.aggregators[sym] = {}
            for tf in target_tfs:
                tf_ms = tf_ms_map.get(tf, 60000)
                self.aggregators[sym][tf] = TickAggregator(tf_ms, wait_for_boundary=True)
                
        # Буфер для пакетного збереження тіків (по 1000)
        self.tick_buffers = {sym: [] for sym in symbols}
        self.loop = None
        
    def _flush_ticks(self, sym: str):
        """Примусово скидає накопичені тіки в базу (викликається коли буфер повний або свічка закрилась)"""
        buffer = self.tick_buffers.get(sym, [])
        if buffer:
            self.flush_ticks_signal.emit(sym, list(buffer))
            self.tick_buffers[sym] = []

    def run(self):
        self.log_signal.emit(f"🔄 Запуск WebSocket ({self.provider}) для {len(self.symbols)} активів...")
        
        # Створюємо новий event loop для цього потоку
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            if self.provider == "ccxt":
                self.loop.run_until_complete(self._stream_ccxt())
            elif self.provider == "massive":
                self.loop.run_until_complete(self._stream_massive())
            else:
                self.log_signal.emit(f"❌ Провайдер {self.provider} не підтримується для WebSocket")
        except Exception as e:
            self.log_signal.emit(f"❌ Помилка WebSocket: {str(e)}")
        finally:
            self.loop.close()
            self.log_signal.emit("🛑 WebSocket потік зупинено.")

    async def _stream_massive(self):
        """Підключення до Polygon.io (Massive) WebSocket"""
        self.log_signal.emit("🔄 Massive WebSocket (Polygon.io) ініціалізовано...")
        from massive import WebSocketClient
        from massive.websocket.models.common import Market
        import json
        import os
        from gui.logic.SettingsLogic import SettingsLogic
        
        keys = SettingsLogic().load_api_keys()
        api_key = keys.get("MASSIVE_KEY", "")
        
        if not api_key:
            self.log_signal.emit("❌ MASSIVE_KEY не знайдено.")
            return

        from utils.SymbolManager import SymbolManager
        
        # Групуємо активи за ринками через SymbolManager
        markets = {
            "crypto": [],
            "forex": [],
            "stocks": []
        }
        for sym in self.symbols:
            market, ws_sub = SymbolManager.format_for_massive_ws(sym)
            markets[market].append(ws_sub)

        async def handle_message(msg):
            import json
            try:
                # massive websocket clients usually return objects or dicts
                # depending on raw/custom json. If it's list of dicts:
                if not isinstance(msg, list):
                    msg = [msg]
                
                for t in msg:
                    # t can be dict or object
                    data = t if isinstance(t, dict) else vars(t)
                    
                    # Нормалізація ключів об'єкта `massive` (polygon-api-client)
                    if 'price' in data and 'size' in data and 'timestamp' in data:
                        data['p'] = data['price']
                        data['v'] = data['size']
                        data['t'] = data['timestamp']
                    elif 'price' in data and 'timestamp' in data:
                        data['p'] = data['price']
                        data['v'] = data.get('size', 0)
                        data['t'] = data['timestamp']
                    
                    if 'symbol' in data:
                        data['sym'] = data['symbol']
                    if 'pair' in data:
                        data['sym'] = data['pair']
                        
                    # Оригінальна нормалізація 'v' (raw JSON Crypto trades)
                    if 'v' not in data and 's' in data:
                        data['v'] = data['s']
                    
                    if 'sym' in data and 'p' in data and 'v' in data and 't' in data:
                        sym = data['sym']
                        orig_sym = SymbolManager.extract_internal_symbol(sym, list(self.aggregators.keys()))
                    else:
                        if data.get('ev') != 'status' and data.get('event_type') != 'status':
                            self.log_signal.emit(f"⚠️ [WebSocket] Невідомий формат: {list(data.keys())} - {str(data)[:100]}")
                        continue
                        
                    if orig_sym in self.aggregators:
                            # 1. Додаємо тік у буфер
                            tick_dict = {
                                'timestamp': data['t'],
                                'price': data['p'],
                                'volume': data['v']
                            }
                            self.tick_buffers[orig_sym].append(tick_dict)
                            self.log_signal.emit(f"🛜 [WebSocket] {orig_sym}: Ціна {data['p']}, Об'єм {data['v']}")
                            
                            candle_closed_this_tick = False
                            
                            # 2. Проганяємо через усі таймфрейми
                            for tf_str, agg in self.aggregators[orig_sym].items():
                                closed_candle = agg.process_tick(
                                    timestamp_ms=data['t'],
                                    price=data['p'],
                                    volume=data['v']
                                )
                                
                                if closed_candle:
                                    candle_closed_this_tick = True
                                    table_name = f"{orig_sym.replace(':', '')}_{tf_str}" 
                                    self.candle_closed_signal.emit(table_name, closed_candle)
                            
                            # 3. Синхронізація: якщо закрилась будь-яка свічка АБО зібралось 1000 тіків -> скидаємо в БД
                            if candle_closed_this_tick or len(self.tick_buffers[orig_sym]) >= 1000:
                                self._flush_ticks(orig_sym)
                                
            except Exception as e:
                self.log_signal.emit(f"⚠️ [WebSocket] Помилка обробки повідомлення: {e} - Дані: {msg}")

        # Створюємо клієнти для кожного потрібного ринку
        tasks = []
        if markets["crypto"]:
            client_c = WebSocketClient(api_key=api_key, market=Market.Crypto, subscriptions=markets["crypto"])
            tasks.append(client_c.connect(handle_message))
            self.log_signal.emit(f"✅ Crypto WebSocket: {len(markets['crypto'])} активів")
            
        if markets["forex"]:
            client_f = WebSocketClient(api_key=api_key, market=Market.Forex, subscriptions=markets["forex"])
            tasks.append(client_f.connect(handle_message))
            self.log_signal.emit(f"✅ Forex WebSocket: {len(markets['forex'])} активів")
            
        if markets["stocks"]:
            client_s = WebSocketClient(api_key=api_key, market=Market.Stocks, subscriptions=markets["stocks"])
            tasks.append(client_s.connect(handle_message))
            self.log_signal.emit(f"✅ Stocks WebSocket: {len(markets['stocks'])} активів")

        if tasks:
            self.log_signal.emit("🛜 [WebSocket] Завдання підключення створені. Очікування даних...")
            await asyncio.gather(*tasks)
        else:
            self.log_signal.emit("⚠️ Немає валідних активів для Massive WebSocket.")


    def stop(self):
        self.is_running = False
        # Прокидаємо loop якщо він чекає
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
