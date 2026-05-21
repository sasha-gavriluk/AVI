import sys
import os
import time
import re
import traceback
import pandas as pd
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

from utils.DataBaseManager import DataBaseManager
from utils.Trading.CCXTModule import CCXTModule
from utils.Trading.MassiveModule import MassiveModule
from utils.config import bybit_key, bybit_secret_key, massive_key

#==================================
# StringCapture
#==================================
class StringCapture:
    # ----------------------------------
    # __init__, ініціалізація перехоплювача
    # ----------------------------------
    # Параметри:
    # signal (pyqtSignal): Сигнал для передачі тексту
    def __init__(self, signal):
        self.signal = signal

    # ----------------------------------
    # write, запис тексту
    # ----------------------------------
    # Параметри:
    # text (str): Текст для запису
    def write(self, text):
        stripped = text.strip()
        if stripped:
            self.signal.emit(stripped)

    # ----------------------------------
    # flush, очищення
    # ----------------------------------
    # Параметри: немає
    def flush(self):
        pass

#==================================
# DownloaderWorker
#==================================
class DownloaderWorker(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    candles_updated = pyqtSignal(int)
    finished_ok = pyqtSignal(int)
    finished_error = pyqtSignal(str)

    # ----------------------------------
    # __init__, ініціалізація потоку завантаження
    # ----------------------------------
    # Параметри:
    # settings (dict): Словник налаштувань для завантаження
    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self.is_running = True

    # ----------------------------------
    # run, головний метод виконання потоку
    # ----------------------------------
    # Параметри: немає
    def run(self):
        old_stdout = sys.stdout
        sys.stdout = StringCapture(self.log_message)

        try:
            source_type = self.settings["source_type"]
            exchange_name = self.settings["exchange"].lower()
            symbols_raw = [s.strip() for s in self.settings["symbols"].split(",") if s.strip()]
            timeframes = self.settings["timeframes"]
            start_ms = self.settings["start_ms"]
            end_ms = self.settings["end_ms"]

            if not symbols_raw:
                self.finished_error.emit("Список активів порожній!")
                return
            if not timeframes:
                self.finished_error.emit("Не обрано таймфрейми!")
                return

            total_loaded_candles = 0

            if source_type == "massive":
                if not massive_key:
                    self.finished_error.emit("MASSIVE_KEY відсутній в .env файлі!")
                    return

                db_filename = "trading_data_massive.duckdb"
                db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db'))
                db_path = os.path.join(db_dir, db_filename)
                
                dbm = DataBaseManager(db_path)
                print(f"📁 Підключення до бази: {db_filename}")
                print(f"🔑 Ініціалізація MassiveModule...")
                
                massive_mod = MassiveModule(dbm, massive_key)
                
                start_date_str = datetime.fromtimestamp(start_ms / 1000).strftime('%Y-%m-%d')
                end_date_str = datetime.fromtimestamp(end_ms / 1000).strftime('%Y-%m-%d')

                d_start = pd.to_datetime(start_date_str)
                d_end = pd.to_datetime(end_date_str)
                total_days = (d_end - d_start).days
                if total_days <= 0: total_days = 1

                for symbol in symbols_raw:
                    for tf in timeframes:
                        if not self.is_running:
                            print("❌ Завантаження зупинено.")
                            dbm.disconnect()
                            return

                        symbol_formatted = symbol.upper()
                        if not symbol_formatted.startswith("C:"):
                            symbol_formatted = f"C:{symbol_formatted}"

                        print(f"\n📥 [MASSIVE] Початок завантаження {symbol_formatted} [{tf}] з {start_date_str} до {end_date_str}...")
                        
                        multiplier, tf_unit = self._parse_tf_for_massive(tf)
                        symbol_clean = symbol_formatted.replace(":", "")[1:]
                        suffix_map = {"minute": "m", "hour": "h", "day": "d"}
                        suffix = f"{multiplier}{suffix_map.get(tf_unit, tf_unit)}"
                        table_name = f"{symbol_clean}_{suffix}"

                        current_start = d_start
                        while current_start < d_end:
                            if not self.is_running: break
                            current_end = current_start + pd.Timedelta("30D")
                            if current_end > d_end: current_end = d_end + pd.Timedelta(days=1)

                            massive_mod._fetch_ohlcv(
                                symbol=symbol_formatted,
                                multiplier=multiplier,
                                timeframe=tf_unit,
                                start_date=current_start.strftime('%Y-%m-%d'),
                                end_date=current_end.strftime('%Y-%m-%d')
                            )

                            try:
                                count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                                if count_df: self.candles_updated.emit(total_loaded_candles + count_df[0])
                            except Exception: pass

                            days_done = (current_end - d_start).days
                            percent_done = min(99, int((days_done / total_days) * 100))
                            self.progress_update.emit(percent_done)

                            current_start = current_end
                            time.sleep(1.5)

                        try:
                            count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                            if count_df:
                                total_loaded_candles += count_df[0]
                                self.candles_updated.emit(total_loaded_candles)
                        except Exception: pass
                dbm.disconnect()

            else:
                db_filename = f"{exchange_name}_data.duckdb"
                db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db'))
                db_path = os.path.join(db_dir, db_filename)
                dbm = DataBaseManager(db_path)
                
                print(f"📁 Підключення до бази: {db_filename}")
                print(f"🔌 Ініціалізація CCXTModule для {exchange_name.upper()}...")
                
                ccxt_mod = CCXTModule(exchange_name, dbm)
                
                if exchange_name == "bybit" and bybit_key and bybit_secret_key:
                    print("🔑 Використання API ключів Bybit...")
                    ccxt_mod.connect(bybit_key, bybit_secret_key)
                
                total_range_ms = end_ms - start_ms
                if total_range_ms <= 0: total_range_ms = 1

                for symbol_raw in symbols_raw:
                    symbol = self._normalize_symbol_for_ccxt(symbol_raw)
                    for tf in timeframes:
                        if not self.is_running:
                            print("❌ Завантаження зупинено.")
                            dbm.disconnect()
                            return

                        print(f"\n📥 [{exchange_name.upper()}] Початок завантаження {symbol} [{tf}]...")
                        
                        current_start = start_ms
                        while current_start < end_ms:
                            if not self.is_running: break

                            ccxt_mod.fetch_ohlcv(symbol, tf, since=current_start, limit=1000)
                            symbol_clean = symbol.replace("/", "_").replace(":", "_")
                            table_name = f"{symbol_clean}_{tf}"
                            
                            tables = dbm.get_all_tables()
                            if table_name not in tables:
                                print(f"⚠️ Немає даних для {symbol} ({tf}).")
                                break
                                
                            last_df = dbm._get_last_record_as_dataframe(table_name)
                            if last_df.empty: break
                                
                            last_t = int(last_df['timestamp'].iloc[0])
                            if last_t <= current_start: break
                                
                            current_start = last_t + 1
                            
                            try:
                                count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                                if count_df: self.candles_updated.emit(total_loaded_candles + count_df[0])
                            except Exception: pass

                            ms_done = last_t - start_ms
                            percent_done = min(99, int((ms_done / total_range_ms) * 100))
                            self.progress_update.emit(percent_done)

                            time.sleep(0.3)

                        try:
                            count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                            if count_df:
                                total_loaded_candles += count_df[0]
                                self.candles_updated.emit(total_loaded_candles)
                        except Exception: pass
                dbm.disconnect()

            sys.stdout = old_stdout
            self.finished_ok.emit(total_loaded_candles)

        except Exception as e:
            sys.stdout = old_stdout
            self.finished_error.emit(traceback.format_exc())

    # ----------------------------------
    # stop, зупинка потоку
    # ----------------------------------
    # Параметри: немає
    def stop(self):
        self.is_running = False

    # ----------------------------------
    # _parse_tf_for_massive, парсинг таймфрейму
    # ----------------------------------
    # Параметри:
    # tf (str): Таймфрейм
    def _parse_tf_for_massive(self, tf: str) -> tuple:
        match = re.match(r'(\d+)([mhd])', tf)
        if match:
            val = int(match.group(1))
            unit = match.group(2)
        else:
            val = 1
            unit = tf[-1] if tf[-1] in ["m", "h", "d"] else "m"
        unit_map = {"m": "minute", "h": "hour", "d": "day"}
        return val, unit_map.get(unit, "minute")

    # ----------------------------------
    # _normalize_symbol_for_ccxt, нормалізація символу
    # ----------------------------------
    # Параметри:
    # symbol (str): Символ
    def _normalize_symbol_for_ccxt(self, symbol: str) -> str:
        symbol = symbol.strip().upper()
        if "/" not in symbol:
            for stable in ["USDT", "BUSD", "USDC", "USD", "BTC", "ETH"]:
                if symbol.endswith(stable) and len(symbol) > len(stable):
                    base = symbol[:-len(stable)]
                    return f"{base}/{stable}"
        return symbol

#==================================
# DownloaderLogic
#==================================
class DownloaderLogic:
    # ----------------------------------
    # __init__, ініціалізація логіки завантажувача
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        self.worker = None

    # ----------------------------------
    # start_download, старт завантаження
    # ----------------------------------
    # Параметри:
    # settings (dict): Налаштування
    def start_download(self, settings: dict) -> DownloaderWorker:
        self.worker = DownloaderWorker(settings)
        return self.worker

    # ----------------------------------
    # stop_download, зупинка завантаження
    # ----------------------------------
    # Параметри: немає
    def stop_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            
    # ----------------------------------
    # get_active_download_db_path, отримання бази, що завантажується
    # ----------------------------------
    # Параметри:
    # source_type (str): Тип джерела
    # exchange (str): Назва біржі
    def get_active_download_db_path(self, source_type: str, exchange: str) -> str:
        if self.worker and self.worker.isRunning():
            if source_type == "massive":
                db_filename = "trading_data_massive.duckdb"
            else:
                db_filename = f"{exchange.lower()}_data.duckdb"
                
            db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db'))
            return os.path.join(db_dir, db_filename)
        return None
