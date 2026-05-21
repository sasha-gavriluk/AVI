import time
import os
import threading
from PyQt6.QtCore import QObject, pyqtSignal

class TradingService(QObject):
    log_update = pyqtSignal(str)
    status_update = pyqtSignal(str)
    signal_received = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.mode = "paper" # "paper" or "live"
        self._thread = None
        self.db_path = "main.duckdb"
        self.symbol = "C:EURUSD"
        self.table_name = "EURUSD_15m"
        self.strategy = None
        
    def set_mode(self, mode: str):
        self.mode = mode
        
    def start(self):
        if self.is_running:
            return
            
        self.is_running = True
        self.log_update.emit(f"🚀 Запуск Live Trading у режимі: {self.mode.upper()}")
        self.status_update.emit("Активний")
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
    def stop(self):
        if not self.is_running:
            return
            
        self.is_running = False
        self.log_update.emit("🛑 Зупинка Live Trading...")
        self.status_update.emit("Зупинено")
        
    def _run_loop(self):
        from utils.DataBaseManager import DataBaseManager
        from utils.Trading.MassiveModule import MassiveModule
        from utils.rules_engine import IndicatorRegistry
        import json
        import datetime
        
        dbm = DataBaseManager(use_default=True)
        # TODO: Завантаження ключів налаштувань
        api_key = "DEMO_KEY" 
        try:
            with open("data/config/settings.json", "r") as f:
                settings = json.load(f)
                api_key = settings.get("binance_api_key", api_key)
        except:
            pass
            
        massive = MassiveModule(dbm, api_key)
        
        while self.is_running:
            try:
                self.log_update.emit(f"Отримання нових даних для {self.symbol}...")
                
                # 1. Завантажуємо свіжі дані (наприклад, останній день)
                now_str = datetime.datetime.now().strftime('%Y-%m-%d')
                massive._fetch_ohlcv(
                    self.symbol,
                    15,
                    "minute",
                    start_date=now_str,
                    end_date=now_str
                )
                
                # 2. Отримуємо оновлені дані
                df = dbm.get_data_by_number_range(self.table_name, 500)
                
                # 3. Перевіряємо умови (Rules Engine)
                if self.strategy and df is not None and not df.empty:
                    registry = IndicatorRegistry(df)
                    signals_df = self.strategy.execute(registry)
                    
                    last_signal = signals_df.iloc[-1]
                    if last_signal['entry']:
                        self.log_update.emit(f"🔥 ЗНАЙДЕНО СИГНАЛ НА ВХІД!")
                        self._execute_trade("BUY" if self.strategy else "SELL")
                    elif last_signal['exit']:
                        self.log_update.emit(f"📉 ЗНАЙДЕНО СИГНАЛ НА ВИХІД!")
                        self._execute_trade("EXIT")
                        
                time.sleep(15) # Перевіряємо кожні 15 секунд
            except Exception as e:
                self.log_update.emit(f"⚠️ Помилка в Live Trading: {e}")
                time.sleep(15)
                
    def _execute_trade(self, action):
        if self.mode == "live":
            self.log_update.emit(f"🔴 [LIVE] Відправка ордера {action} на біржу!")
        else:
            self.log_update.emit(f"🟢 [PAPER] Запис віртуальної угоди {action} в базу.")
