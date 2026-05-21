import os
import time
import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from utils.DataBaseManager import DataBaseManager
from core.services.gap_analyzer import GapAnalyzer

class AutoDownloaderThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, target_db_path, missing_gaps_per_table, use_ccxt=False, use_massive=False):
        super().__init__()
        self.target_db_path = target_db_path
        self.missing_gaps_per_table = missing_gaps_per_table
        self.use_ccxt = use_ccxt
        self.use_massive = use_massive
        self.is_running = True

    def run(self):
        self.log_signal.emit("🤖 Автозавантажувач запущено...")
        # Тут треба викликати MassiveModule або CCXTModule
        # Для простоти на даному етапі ми лише імітуємо або робимо базовий виклик.
        try:
            from utils.Trading.MassiveModule import MassiveModule
            from utils.config import massive_key
            
            dbm = DataBaseManager(self.target_db_path)
            
            for table_name, gaps in self.missing_gaps_per_table.items():
                if not self.is_running:
                    break
                    
                # Визначаємо символ і таймфрейм з назви таблиці (напр. EURUSD_15m)
                parts = table_name.split('_')
                if len(parts) >= 2:
                    symbol = parts[0]
                    tf = parts[1]
                else:
                    continue
                    
                # Форматуємо для Massive
                symbol_formatted = f"C:{symbol}" if not symbol.startswith("C:") else symbol
                multiplier = int(''.join(filter(str.isdigit, tf)) or 1)
                unit_char = tf[-1] if tf[-1].isalpha() else 'm'
                unit_map = {'m': 'minute', 'h': 'hour', 'd': 'day'}
                timeframe_unit = unit_map.get(unit_char, 'minute')
                
                if self.use_massive:
                    massive_mod = MassiveModule(dbm, massive_key) if massive_key else None
                    if not massive_mod:
                        self.log_signal.emit("❌ Помилка: massive_key відсутній, автозавантаження Massive неможливе.")
                    else:
                        for gap in gaps:
                            if not self.is_running:
                                break
                            
                            start_date = pd.to_datetime(gap['gap_start'], unit='ms').strftime('%Y-%m-%d')
                            end_date = pd.to_datetime(gap['gap_end'], unit='ms').strftime('%Y-%m-%d')
                            
                            self.log_signal.emit(f"🔄 Завантаження: {symbol} [{tf}] {start_date} -> {end_date}...")
                            try:
                                massive_mod._fetch_ohlcv(
                                    symbol=symbol_formatted,
                                    multiplier=multiplier,
                                    timeframe=timeframe_unit,
                                    start_date=start_date,
                                    end_date=end_date
                                )
                                self.log_signal.emit(f"✅ Успішно завантажено прогалину {start_date} -> {end_date}")
                                time.sleep(1.5) # Пауза щоб не спамити API
                            except Exception as e:
                                self.log_signal.emit(f"❌ Помилка завантаження: {e}")
                                
                if self.use_ccxt:
                    self.log_signal.emit("ℹ️ Автозавантаження через CCXT ще в розробці.")
            
            dbm.disconnect()
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"❌ Критична помилка: {e}")
            self.finished_signal.emit(False)

    def stop(self):
        self.is_running = False

class CopilotSchedulerThread(QThread):
    """
    Фоновий потік для автоматичної рутини Копілота.
    Виконує:
    1. Генерацію стратегій
    2. Тестування (через TradingCopilot)
    """
    log_signal = pyqtSignal(str)

    def __init__(self, db_path, auto_download, auto_gen, interval_hours=1):
        super().__init__()
        self.db_path = db_path
        self.auto_download = auto_download
        self.auto_gen = auto_gen
        self.interval_hours = interval_hours
        self.is_running = True

    def run(self):
        from utils.algorithms.backtesting.TradingCopilot import TradingCopilot
        from utils.algorithms.backtesting.StrategyGenerator import StrategyGenerator
        
        copilot = TradingCopilot(db_path=self.db_path)
        generator = StrategyGenerator(copilot=copilot)
        
        while self.is_running:
            self.log_signal.emit("🔄 [Рутина] Початок нового циклу...")
            
            if self.auto_gen:
                self.log_signal.emit("🧠 [Рутина] Аналіз досвіду та генерація нових стратегій...")
                try:
                    # Запускаємо 10 стратегій для швидкого циклу
                    copilot.run_random_training(generator, n_strategies=10)
                    self.log_signal.emit("✅ [Рутина] Тренування завершено. Досвід збережено.")
                except Exception as e:
                    self.log_signal.emit(f"❌ [Рутина] Помилка генерації: {e}")
            
            # Засинаємо дрібними кроками для швидкої зупинки
            sleep_seconds = self.interval_hours * 3600
            self.log_signal.emit(f"💤 [Рутина] Засинаю на {self.interval_hours} год...")
            
            for _ in range(int(sleep_seconds)):
                if not self.is_running:
                    break
                time.sleep(1)

    def stop(self):
        self.is_running = False
        self.log_signal.emit("🛑 [Рутина] Отримано сигнал зупинки.")

class CopilotService(QObject):
    log_update = pyqtSignal(str)
    status_update = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gap_analyzer = GapAnalyzer()
        self.downloader_thread = None
        self.scheduler_thread = None

    def analyze_database(self, db_path: str, use_ccxt: bool = False, use_massive: bool = False):
        self.status_update.emit("Аналіз бази даних...")
        self.log_update.emit(f"🔍 Запуск аналізу бази: {os.path.basename(db_path)}")
        
        try:
            dbm = DataBaseManager(db_path)
            tables = dbm.get_all_tables()
            
            missing_gaps_per_table = {}
            total_real_gaps = 0
            
            for table in tables:
                # Очікуваний крок в мс
                tf_ms = 60000
                if table.endswith('_15m'): tf_ms = 15 * 60000
                elif table.endswith('_1h'): tf_ms = 60 * 60000
                elif table.endswith('_4h'): tf_ms = 4 * 60 * 60000
                elif table.endswith('_1d'): tf_ms = 24 * 60 * 60000
                
                # Отримуємо всі прогалини
                raw_gaps = dbm.get_time_gaps(table, tf_ms)
                
                if raw_gaps:
                    asset_name = table.split('_')[0]
                    # Відфільтровуємо свята та вихідні
                    real_gaps = self.gap_analyzer.filter_real_gaps(raw_gaps, asset_name, tf_ms)
                    
                    if real_gaps:
                        missing_gaps_per_table[table] = real_gaps
                        total_real_gaps += len(real_gaps)
                        self.log_update.emit(f"⚠️ {table}: знайдено {len(real_gaps)} реальних прогалин (відфільтровано вихідних: {len(raw_gaps) - len(real_gaps)})")
                    else:
                        self.log_update.emit(f"✅ {table}: всі {len(raw_gaps)} прогалини є вихідними/святами. Дані цілі.")
                else:
                    self.log_update.emit(f"✅ {table}: прогалин не знайдено.")
            
            dbm.disconnect()
            
            if missing_gaps_per_table:
                if not use_ccxt and not use_massive:
                    self.log_update.emit(f"⚠️ Знайдено {total_real_gaps} прогалин, але всі джерела автозавантаження вимкнені в налаштуваннях.")
                    self.status_update.emit("Очікування даних")
                else:
                    self.log_update.emit(f"🚨 Загалом знайдено {total_real_gaps} прогалин, що потребують завантаження.")
                    self.status_update.emit("Потрібне автозавантаження")
                    # Автоматичний запуск завантаження
                    self.start_auto_download(db_path, missing_gaps_per_table, use_ccxt, use_massive)
            else:
                self.status_update.emit("База даних в ідеальному стані")
                self.log_update.emit("🎉 Аналіз завершено. Усі дані повні (з урахуванням свят).")
                
        except Exception as e:
            self.log_update.emit(f"❌ Помилка аналізу: {e}")
            self.status_update.emit("Помилка аналізу")

    def start_auto_download(self, db_path, missing_gaps_per_table, use_ccxt=False, use_massive=False):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.log_update.emit("⚠️ Автозавантаження вже працює.")
            return
            
        self.downloader_thread = AutoDownloaderThread(db_path, missing_gaps_per_table, use_ccxt, use_massive)
        self.downloader_thread.log_signal.connect(lambda msg: self.log_update.emit(msg))
        self.downloader_thread.finished_signal.connect(self._on_download_finished)
        self.downloader_thread.start()
        self.status_update.emit("Автозавантаження даних...")

    def _on_download_finished(self, success):
        if success:
            self.status_update.emit("База даних в ідеальному стані")
            self.log_update.emit("🎉 Автозавантаження завершено успішно!")
        else:
            self.status_update.emit("Помилка автозавантаження")

    def start_scheduler(self, db_path, use_ccxt, use_massive, auto_gen, interval_hours=1.0):
        if self.scheduler_thread and self.scheduler_thread.isRunning():
            self.log_update.emit("⚠️ Планувальник вже працює.")
            return
            
        auto_download = use_ccxt or use_massive
        self.scheduler_thread = CopilotSchedulerThread(db_path, auto_download, auto_gen, interval_hours)
        self.scheduler_thread.log_signal.connect(lambda msg: self.log_update.emit(msg))
        self.scheduler_thread.start()
        
        # Відразу запускаємо і аналіз бази (в основному потоці чи окремо)
        if auto_download:
            self.analyze_database(db_path, use_ccxt, use_massive)

    def stop_all(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.stop()
            self.downloader_thread.wait()
            
        if self.scheduler_thread and self.scheduler_thread.isRunning():
            self.scheduler_thread.stop()
            self.scheduler_thread.wait()
