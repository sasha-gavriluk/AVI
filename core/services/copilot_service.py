import os
import time
import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from utils.DataBaseManager import DataBaseManager
from core.services.gap_analyzer import GapAnalyzer

class GapAnalyzerThread(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict, int) # (missing_gaps_per_table, total_real_gaps)
    error_signal = pyqtSignal(str)
    
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.gap_analyzer = GapAnalyzer()
        
    def run(self):
        try:
            dbm = DataBaseManager(self.db_path)
            tables = dbm.get_all_tables()
            
            missing_gaps_per_table = {}
            total_real_gaps = 0
            
            for table in tables:
                t_lower = table.lower()
                if "backtest" in t_lower or "auto_learn" in t_lower or table.startswith("sqlite_") or t_lower.startswith("temp_sim_"):
                    continue
                if t_lower in ["copilot_memory", "rules_changelog"]:
                    continue

                tf_ms = 60000
                if table.endswith('_1m'): tf_ms = 60000
                elif table.endswith('_5m'): tf_ms = 5 * 60000
                elif table.endswith('_15m'): tf_ms = 15 * 60000
                elif table.endswith('_30m'): tf_ms = 30 * 60000
                elif table.endswith('_1h'): tf_ms = 60 * 60000
                elif table.endswith('_4h'): tf_ms = 4 * 60 * 60000
                elif table.endswith('_1d'): tf_ms = 24 * 60 * 60000
                
                raw_gaps = dbm.get_time_gaps(table, tf_ms)
                
                if raw_gaps:
                    asset_name = table.split('_')[0]
                    real_gaps = self.gap_analyzer.filter_real_gaps(raw_gaps, asset_name, tf_ms)
                    
                    if real_gaps:
                        missing_gaps_per_table[table] = real_gaps
                        total_real_gaps += len(real_gaps)
                        self.log_signal.emit(f"⚠️ {table}: знайдено {len(real_gaps)} реальних прогалин (відфільтровано вихідних: {len(raw_gaps) - len(real_gaps)})")
                    else:
                        self.log_signal.emit(f"✅ {table}: всі {len(raw_gaps)} прогалини є вихідними/святами. Дані цілі.")
                else:
                    self.log_signal.emit(f"✅ {table}: прогалин не знайдено.")
            
            dbm.disconnect()
            self.result_signal.emit(missing_gaps_per_table, total_real_gaps)
            
        except Exception as e:
            self.error_signal.emit(str(e))

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
                    tf = parts[-1]
                    symbol = "_".join(parts[:-1])
                else:
                    continue
                    
                # Форматуємо для Massive
                symbol_formatted = f"C:{symbol}" if not symbol.startswith("C:") else symbol
                multiplier = int(''.join(filter(str.isdigit, tf)) or 1)
                unit_char = tf[-1] if tf[-1].isalpha() else 'm'
                unit_map = {'m': 'minute', 'h': 'hour', 'd': 'day'}
                timeframe_unit = unit_map.get(unit_char, 'minute')
                
                is_crypto = "_" in symbol
                
                use_mod = None
                if is_crypto:
                    if self.use_ccxt:
                        use_mod = "ccxt"
                    elif self.use_massive:
                        use_mod = "massive"
                else:
                    if self.use_massive:
                        use_mod = "massive"
                    elif self.use_ccxt:
                        self.log_signal.emit(f"⚠️ Пропуск {table_name}: це не біржовий актив (Forex), а Massive API вимкнено.")
                        continue
                        
                if use_mod == "massive":
                    massive_mod = MassiveModule(dbm, massive_key) if massive_key else None
                    if not massive_mod:
                        self.log_signal.emit("❌ Помилка: massive_key відсутній, автозавантаження Massive неможливе.")
                    else:
                        for gap in gaps:
                            if not self.is_running:
                                break
                            
                            start_date = pd.to_datetime(gap['gap_start'], unit='ms').strftime('%Y-%m-%d')
                            end_date = pd.to_datetime(gap['gap_end'], unit='ms').strftime('%Y-%m-%d')
                            
                            self.log_signal.emit(f"🔄 Завантаження [Massive]: {symbol} [{tf}] {start_date} -> {end_date}...")
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
                                
                elif use_mod == "ccxt":
                    try:
                        from utils.Trading.CCXTModule import CCXTModule
                        from utils.config import bybit_key, bybit_secret_key
                        
                        exchange_name = "bybit"
                        ccxt_mod = CCXTModule(exchange_name, dbm)
                        if bybit_key and bybit_secret_key:
                            ccxt_mod.connect(bybit_key, bybit_secret_key)
                        
                        for gap in gaps:
                            if not self.is_running: break
                            start_ms = gap['gap_start']
                            end_ms = gap['gap_end']
                            
                            start_date = pd.to_datetime(start_ms, unit='ms').strftime('%Y-%m-%d %H:%M')
                            end_date = pd.to_datetime(end_ms, unit='ms').strftime('%Y-%m-%d %H:%M')
                            
                            self.log_signal.emit(f"🔄 Завантаження [CCXT]: {symbol} [{tf}] {start_date} -> {end_date}...")
                            
                            symbol_ccxt = symbol.replace('_', '/')
                            if "/" not in symbol_ccxt:
                                for stable in ["USDT", "BUSD", "USDC", "USD", "BTC", "ETH"]:
                                    if symbol_ccxt.endswith(stable) and len(symbol_ccxt) > len(stable):
                                        base = symbol_ccxt[:-len(stable)]
                                        symbol_ccxt = f"{base}/{stable}"
                                        break

                            current_start = start_ms
                            while current_start < end_ms:
                                if not self.is_running: break
                                ccxt_mod.fetch_ohlcv(symbol_ccxt, tf, since=current_start, limit=1000)
                                
                                last_df = dbm._get_last_record_as_dataframe(table_name)
                                if last_df.empty: break
                                last_t = int(last_df['timestamp'].iloc[0])
                                if last_t <= current_start: break
                                current_start = last_t + 1
                                time.sleep(0.3)
                                
                            self.log_signal.emit(f"✅ Успішно завантажено прогалину [CCXT] {start_date} -> {end_date}")
                    except Exception as e:
                        self.log_signal.emit(f"❌ Помилка CCXT: {e}")
            
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
    cycle_started = pyqtSignal()

    def __init__(self, db_path, config_states, interval_minutes=60):
        super().__init__()
        self.db_path = db_path
        self.config_states = config_states
        self.interval_minutes = interval_minutes
        self.is_running = True

    def run(self):
        from utils.algorithms.backtesting.TradingCopilot import TradingCopilot
        from utils.algorithms.backtesting.StrategyGenerator import StrategyGenerator
        
        copilot = TradingCopilot(db_path=self.db_path)
        generator = StrategyGenerator(copilot=copilot)
        
        while self.is_running:
            import json, os
            try:
                from utils.PathManager import PathManager
                config_path = PathManager.get_settings_path()
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        settings_data = json.load(f)
                        copilot_view = settings_data.get("copilot_view", {})
                        if copilot_view:
                            self.config_states.update(copilot_view)
                        copilot_settings = settings_data.get("copilot", {})
                        if "routine_interval_minutes" in copilot_settings:
                            self.interval_minutes = float(copilot_settings["routine_interval_minutes"])
            except Exception: pass
            
            self.cycle_started.emit()
            self.log_signal.emit("🔄 [Рутина] Початок нового циклу...")
            
            is_auto = self.config_states.get("cb_auto_mode", True)
            if is_auto:
                use_ccxt = True
                use_massive = True
                gen_signals = True
                auto_gen = True
                has_download = True
            else:
                use_ccxt = self.config_states.get("cb_download_ccxt", False)
                use_massive = self.config_states.get("cb_download_massive", False)
                auto_gen = self.config_states.get("cb_auto_gen", False)
                gen_signals = self.config_states.get("cb_gen_signals", False)
                has_download = use_ccxt or use_massive
                if not has_download:
                    gen_signals = False

            if has_download:
                self.log_signal.emit("🔍 [Рутина] Крок 1-2: Аналіз прогалин та автозавантаження даних...")
                # Synchronous Gap Analysis
                from core.services.copilot_service import GapAnalyzerThread, AutoDownloaderThread
                gap_thread = GapAnalyzerThread(self.db_path)
                
                result_container = {}
                def on_gap_result(m, t): result_container['missing'] = m
                def on_log(msg): self.log_signal.emit(msg)
                
                gap_thread.log_signal.connect(on_log)
                gap_thread.result_signal.connect(on_gap_result)
                gap_thread.run() # Synchronous run
                
                missing = result_container.get('missing', {})
                if missing:
                    self.log_signal.emit("🔄 [Рутина] Знайдено прогалини, розпочинаю завантаження...")
                    dl_thread = AutoDownloaderThread(self.db_path, missing, use_ccxt, use_massive)
                    dl_thread.log_signal.connect(on_log)
                    dl_thread.run() # Synchronous run
                else:
                    self.log_signal.emit("✅ [Рутина] База даних не потребує оновлень.")
                    
            if not self.is_running: break

            if gen_signals:
                self.log_signal.emit("🔍 [Рутина] Крок 3-4: Сканування ринків та пошук сигналів...")
                import json, os
                from utils.PathManager import PathManager
                active_strategies = []
                try:
                    settings_path = PathManager.get_settings_path()
                    if os.path.exists(settings_path):
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            settings_data = json.load(f)
                            active_strategies = settings_data.get("copilot", {}).get("active_strategies", [])
                except Exception as e:
                    self.log_signal.emit(f"⚠️ [Рутина] Не вдалося завантажити налаштування: {e}")

                if active_strategies:
                    from core.services.notification_service import TelegramNotifier
                    notifier = TelegramNotifier()
                    try:
                        target_assets = settings_data.get("copilot", {}).get("target_assets", [])
                        target_timeframes = settings_data.get("copilot", {}).get("target_timeframes", [])
                        copilot.scan_markets_for_signals(
                            active_strategies, 
                            notifier,
                            target_assets=target_assets,
                            target_timeframes=target_timeframes
                        )
                        self.log_signal.emit("✅ [Рутина] Сканування завершено, звіти відправлено.")
                    except Exception as e:
                        self.log_signal.emit(f"❌ [Рутина] Помилка сканування: {e}")
                else:
                    self.log_signal.emit("⚠️ [Рутина] Немає активних стратегій для сканування.")

            if not self.is_running: break

            if auto_gen:
                self.log_signal.emit("🧠 [Рутина] Крок 5: Авто-генерація та тестування 100 стратегій...")
                try:
                    copilot.run_random_training(generator, n_strategies=100)
                    self.log_signal.emit("✅ [Рутина] Тренування завершено. Найкращі стратегії збережено в папці 'Copilot'.")
                except Exception as e:
                    self.log_signal.emit(f"❌ [Рутина] Помилка генерації: {e}")
            
            sleep_seconds = self.interval_minutes * 60
            self.log_signal.emit(f"💤 [Рутина] Засинаю на {self.interval_minutes} хв...")
            
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
    task_finished = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gap_analyzer = GapAnalyzer()
        self.downloader_thread = None
        self.scheduler_thread = None

    def analyze_database(self, db_path: str, use_ccxt: bool = False, use_massive: bool = False):
        if hasattr(self, '_gap_analyzer_thread') and self._gap_analyzer_thread.isRunning():
            self.log_update.emit("⚠️ Аналіз бази вже виконується.")
            return
            
        self.status_update.emit("Аналіз бази даних...")
        self.log_update.emit(f"🔍 Запуск аналізу бази: {os.path.basename(db_path)}")
        
        self._gap_analyzer_thread = GapAnalyzerThread(db_path)
        self._gap_analyzer_thread.log_signal.connect(lambda msg: self.log_update.emit(msg))
        
        def on_result(missing_gaps_per_table, total_real_gaps):
            if missing_gaps_per_table:
                if not use_ccxt and not use_massive:
                    self.log_update.emit(f"⚠️ Знайдено {total_real_gaps} прогалин, але всі джерела автозавантаження вимкнені в налаштуваннях.")
                    self.status_update.emit("Очікування даних")
                    self.task_finished.emit("analyze_database")
                else:
                    self.log_update.emit(f"🚨 Загалом знайдено {total_real_gaps} прогалин, що потребують завантаження.")
                    self.status_update.emit("Потрібне автозавантаження")
                    self.start_auto_download(db_path, missing_gaps_per_table, use_ccxt, use_massive)
            else:
                self.status_update.emit("База даних в ідеальному стані")
                self.log_update.emit("🎉 Аналіз завершено. Усі дані повні (з урахуванням свят).")
                self.task_finished.emit("analyze_database")
                
        def on_error(err_str):
            self.log_update.emit(f"❌ Помилка аналізу: {err_str}")
            self.status_update.emit("Помилка аналізу")
            self.task_finished.emit("analyze_database")
            
        self._gap_analyzer_thread.result_signal.connect(on_result)
        self._gap_analyzer_thread.error_signal.connect(on_error)
        self._gap_analyzer_thread.start()

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
        self.task_finished.emit("download")

    def start_scheduler(self, db_path, config_states, interval_minutes=60):
        if self.scheduler_thread and self.scheduler_thread.isRunning():
            self.log_update.emit("⚠️ Планувальник вже працює.")
            return
            
        self.scheduler_thread = CopilotSchedulerThread(db_path, config_states, interval_minutes)
        self.scheduler_thread.log_signal.connect(lambda msg: self.log_update.emit(msg))
        self.scheduler_thread.start()

    def stop_all(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.stop()
            self.downloader_thread.wait()
            
        if self.scheduler_thread and self.scheduler_thread.isRunning():
            self.scheduler_thread.stop()
            self.scheduler_thread.wait()
