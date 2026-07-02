import os
import time
import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from utils.DataBaseManager import DataBaseManager
from utils.gap_analyzer import GapAnalyzer
from utils.Trading.WebsocketStreamer import WebsocketStreamerThread

class GapAnalyzerThread(QThread):
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict, int) # (missing_gaps_per_table, total_real_gaps)
    error_signal = pyqtSignal(str)
    
    def __init__(self, db_path, target_assets=None, target_timeframes=None, api_delay_minutes=0):
        super().__init__()
        self.db_path = db_path
        self.gap_analyzer = GapAnalyzer()
        self.target_assets = target_assets
        self.target_timeframes = target_timeframes
        self.api_delay_minutes = api_delay_minutes
        
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

                parts = table.split('_')
                if len(parts) >= 2:
                    asset = "_".join(parts[:-1])
                    tf = parts[-1]
                    if self.target_assets and asset not in self.target_assets:
                        continue
                    if self.target_timeframes and tf not in self.target_timeframes:
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
                
                # Додаємо перевірку від останньої збереженої свічки до поточного часу (NOW)
                last_df = dbm._get_last_record_as_dataframe(table)
                if not last_df.empty and 'timestamp' in last_df.columns:
                    try:
                        last_time = int(last_df['timestamp'].iloc[0])
                        import time
                        current_time_ms = int(time.time() * 1000)
                        effective_time_ms = current_time_ms - (self.api_delay_minutes * 60000)
                        # Якщо пройшло більше часу ніж один таймфрейм
                        if (effective_time_ms - last_time) > tf_ms:
                            raw_gaps.append({'gap_start': last_time, 'gap_end': effective_time_ms})
                    except Exception:
                        pass
                
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
                    
                from utils.SymbolManager import SymbolManager
                market_type = SymbolManager.get_market_type(symbol)
                symbol_formatted = SymbolManager.format_for_massive_rest(symbol)
                
                multiplier = int(''.join(filter(str.isdigit, tf)) or 1)
                unit_char = tf[-1] if tf[-1].isalpha() else 'm'
                unit_map = {'m': 'minute', 'h': 'hour', 'd': 'day'}
                timeframe_unit = unit_map.get(unit_char, 'minute')
                
                use_mod = None
                if market_type == "crypto":
                    if self.use_ccxt:
                        use_mod = "ccxt"
                    elif self.use_massive:
                        use_mod = "massive"
                else:
                    if self.use_massive:
                        use_mod = "massive"
                    elif self.use_ccxt:
                        self.log_signal.emit(f"⚠️ Пропуск {table_name}: це {market_type}, а Massive API вимкнено.")
                        continue
                        
                if use_mod == "massive":
                    import json, os
                    from utils.PathManager import PathManager
                    massive_free_tier = True
                    massive_reqs = 5
                    massive_wait = 3
                    try:
                        config_path = PathManager.get_settings_path()
                        if os.path.exists(config_path):
                            with open(config_path, 'r', encoding='utf-8') as f:
                                s_data = json.load(f)
                                dl = s_data.get("downloader", {})
                                massive_free_tier = dl.get("massive_free_tier", True)
                                massive_reqs = dl.get("massive_free_requests", 5)
                                massive_wait = dl.get("massive_free_wait_minutes", 3)
                    except Exception: pass

                    massive_mod = MassiveModule(dbm, massive_key, free_tier=massive_free_tier, free_requests=massive_reqs, free_wait_minutes=massive_wait) if massive_key else None
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
                                massive_mod.fetch_ohlcv_auto_download(
                                    symbol=symbol_formatted,
                                    multiplier=multiplier,
                                    timeframe=timeframe_unit,
                                    start_date=start_date,
                                    end_date=end_date,
                                    batch_size="30D",
                                    time_sleep=1.5 if not massive_free_tier else max(1.5, (massive_wait * 60) / massive_reqs),
                                    internal_symbol=symbol
                                )
                                self.log_signal.emit(f"✅ Успішно завантажено прогалину {start_date} -> {end_date}")
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
                            
                            symbol_ccxt = SymbolManager.format_for_ccxt(symbol)

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

    def __init__(self, db_path, config_states):
        super().__init__()
        self.db_path = db_path
        self.config_states = config_states
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
                from gui.logic.copilot_service import GapAnalyzerThread, AutoDownloaderThread
                try:
                    t_assets = settings_data.get("copilot", {}).get("target_assets", [])
                    t_tfs = settings_data.get("copilot", {}).get("target_timeframes", [])
                    if use_massive:
                        dl_settings = settings_data.get("downloader", {})
                        if dl_settings.get("massive_free_tier", True):
                            api_delay = dl_settings.get("massive_api_delay_minutes", 15)
                        else:
                            api_delay = 0
                    else:
                        api_delay = 0
                except Exception:
                    t_assets = []
                    t_tfs = []
                    api_delay = 0
                gap_thread = GapAnalyzerThread(self.db_path, target_assets=t_assets, target_timeframes=t_tfs, api_delay_minutes=api_delay)
                
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
                active_strategies_tree = {}
                signal_mode = "Класичні Стратегії"
                try:
                    settings_path = PathManager.get_settings_path()
                    if os.path.exists(settings_path):
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            settings_data = json.load(f)
                            active_strategies_tree = settings_data.get("copilot", {}).get("active_strategies_tree", {})
                            signal_mode = settings_data.get("copilot_view", {}).get("signal_mode", "Класичні Стратегії")
                except Exception as e:
                    self.log_signal.emit(f"⚠️ [Рутина] Не вдалося завантажити налаштування: {e}")

                from utils.notification_service import TelegramNotifier
                notifier = TelegramNotifier()
                target_assets = settings_data.get("copilot", {}).get("target_assets", [])

                if signal_mode == "Класичні Стратегії":
                    has_any_strategies = any(len(strats) > 0 for strats in active_strategies_tree.values())
                    if has_any_strategies:
                        try:
                            # Запускаємо сканування для кожного таймфрейму, де є стратегії
                            for tf, strats in active_strategies_tree.items():
                                if strats:
                                    self.log_signal.emit(f"🔍 [Рутина] Сканування для таймфрейму {tf}...")
                                    copilot.scan_markets_for_signals(
                                        strats, 
                                        notifier,
                                        target_assets=target_assets,
                                        target_timeframes=[tf]
                                    )
                            self.log_signal.emit("✅ [Рутина] Сканування завершено, звіти відправлено.")
                        except Exception as e:
                            self.log_signal.emit(f"❌ [Рутина] Помилка сканування: {e}")
                    else:
                        self.log_signal.emit("⚠️ [Рутина] Немає активних стратегій для сканування.")
                else:
                    # Режим Нейромереж
                    self.log_signal.emit("🧠 [Рутина] Аналіз ринків через Нейромережі (Golden Trio)...")
                    try:
                        from utils.DataBaseManager import DataBaseManager
                        from utils.algorithms.indicators.IndicatorProcessor import IndicatorProcessor
                        from utils.algorithms.indicators.PatternDetector import PatternDetector
                        from utils.algorithms.indicators.BacktestAlgorithmProcessor import BacktestAlgorithmProcessor
                        from utils.algorithms.CopilotAlgorithmicLogic import CopilotAlgorithmicLogic
                        
                        nn_logic = CopilotAlgorithmicLogic(use_context_rules=True)
                        db_path = PathManager.get_db_path()
                        
                        with DataBaseManager(db_path) as db:
                            for asset in target_assets:
                                df = db.get_data_by_number_range(asset, 2000)
                                if df is None or len(df) < 100:
                                    continue
                                
                                processor = IndicatorProcessor(df, df.copy())
                                df = processor.process_data()
                                detector = PatternDetector(df, df)
                                df = detector.process_data()
                                algo_processor = BacktestAlgorithmProcessor(df, df, algorithm_params=['Order_Blocks', 'Fair_Value_Gaps', 'Market_Structure'])
                                df = algo_processor.process_data()
                                
                                window = df.iloc[-10:]
                                res = nn_logic.analyze_window(window, asset=asset)
                                signal = res.get('signal')
                                
                                if signal:
                                    prob = res.get('probabilities', {}).get(signal.lower(), 0.0)
                                    price = window['close'].iloc[-1]
                                    tg_msg = f"🔥 <b>LIVE SIGNAL</b> 🔥\n\n📌 <b>Актив:</b> {asset}\n📈 <b>Тип:</b> {signal}\n💰 <b>Ціна:</b> {price:.5f}\n🧠 <b>Впевненість NN:</b> {prob:.2f}\n⚖️ <b>Захист (MR/FB/RS):</b> Пройдено"
                                    notifier.send_message(tg_msg)
                                    self.log_signal.emit(f"🔔 СИГНАЛ {asset}: {signal} за {price:.5f} (Впевненість: {prob:.2f})")
                        self.log_signal.emit("✅ [Рутина] Сканування нейромережами завершено.")
                    except Exception as e:
                        self.log_signal.emit(f"❌ [Рутина] Помилка NN сканування: {e}")

            if not self.is_running: break

            if auto_gen:
                self.log_signal.emit("🧠 [Рутина] Крок 5: Авто-генерація та тестування 100 стратегій...")
                try:
                    copilot.run_random_training(generator, n_strategies=100)
                    self.log_signal.emit("✅ [Рутина] Тренування завершено. Найкращі стратегії збережено в папці 'Copilot'.")
                except Exception as e:
                    self.log_signal.emit(f"❌ [Рутина] Помилка генерації: {e}")
            
            # Розумне очікування нової свічки
            import time
            current_time = time.time()
            wait_seconds = 3600 # дефолт, якщо щось піде не так
            
            try:
                import json, os
                from utils.PathManager import PathManager
                config_path = PathManager.get_settings_path()
                tfs = []
                api_delay = 0
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        local_settings = json.load(f)
                        tfs = local_settings.get("copilot", {}).get("target_timeframes", [])
                        if use_massive:
                            dl_settings = local_settings.get("downloader", {})
                            if dl_settings.get("massive_free_tier", True):
                                api_delay = dl_settings.get("massive_api_delay_minutes", 15)
                            else:
                                api_delay = 0
                        
                if not tfs:
                    tfs = ["15m"] # За замовчуванням орієнтуємось на 15 хв
                    
                tf_seconds_list = []
                for tf in tfs:
                    if tf.endswith('m'): tf_seconds_list.append(int(tf[:-1]) * 60)
                    elif tf.endswith('h'): tf_seconds_list.append(int(tf[:-1]) * 3600)
                    elif tf.endswith('d'): tf_seconds_list.append(int(tf[:-1]) * 86400)
                    
                if tf_seconds_list:
                    # Шукаємо час закриття наступної свічки для кожного таймфрейму
                    next_closes = [((int(current_time) // tfs_sec) + 1) * tfs_sec for tfs_sec in tf_seconds_list]
                    # Беремо найближчу свічку + 5 секунд буферу (щоб біржа встигла її опублікувати) + затримка API
                    next_close = min(next_closes)
                    wait_seconds = (next_close - current_time) + 5 + (api_delay * 60)
            except Exception as e:
                self.log_signal.emit(f"⚠️ [Рутина] Помилка розрахунку часу наступної свічки: {e}")
            
            if wait_seconds < 5: 
                wait_seconds = 5 # Мінімальний час очікування
                
            mins = int(wait_seconds // 60)
            secs = int(wait_seconds % 60)
            self.log_signal.emit(f"⏳ [Рутина] Очікую появи нової свічки... Сон до наступного циклу: {mins} хв {secs} сек.")
            
            # Спимо циклами по 1 секунді щоб миттєво реагувати на команду stop()
            for _ in range(int(wait_seconds)):
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
    trigger_signal_scan = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gap_analyzer = GapAnalyzer()
        self.downloader_thread = None
        self.scheduler_thread = None
        self.websocket_thread = None

    def analyze_database(self, db_path: str, use_ccxt: bool = False, use_massive: bool = False):
        import json, os
        from utils.PathManager import PathManager
        
        if hasattr(self, '_gap_analyzer_thread') and self._gap_analyzer_thread.isRunning():
            self.log_update.emit("⚠️ Аналіз бази вже виконується.")
            return
            
        self.status_update.emit("Аналіз бази даних...")
        self.log_update.emit(f"🔍 Запуск аналізу бази: {os.path.basename(db_path)}")
        
        api_delay = 0
        target_assets = None
        target_timeframes = None
        try:
            config_path = PathManager.get_settings_path()
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                    
                    target_assets = settings_data.get("copilot", {}).get("target_assets", [])
                    target_timeframes = settings_data.get("copilot", {}).get("target_timeframes", [])
                    
                    if use_massive:
                        dl_settings = settings_data.get("downloader", {})
                        if dl_settings.get("massive_free_tier", True):
                            api_delay = dl_settings.get("massive_api_delay_minutes", 15)
                        else:
                            api_delay = 0
        except Exception: pass
        
        self._gap_analyzer_thread = GapAnalyzerThread(
            db_path, 
            target_assets=target_assets, 
            target_timeframes=target_timeframes,
            api_delay_minutes=api_delay
        )
        self._gap_analyzer_thread.log_signal.connect(lambda msg: self.log_update.emit(msg))
        
        def on_result(missing_gaps_per_table, total_real_gaps):
            if missing_gaps_per_table:
                if not use_ccxt and not use_massive:
                    self.log_update.emit(f"⚠️ Знайдено {total_real_gaps} прогалин, але всі джерела автозавантаження вимкнені в налаштуваннях.")
                    self.status_update.emit("Очікування даних")
                    self.task_finished.emit("analyze_database")
                    
                    if getattr(self, '_pending_websocket_start', False):
                        self._pending_websocket_start = False
                        self.log_update.emit("🚀 Запуск Live-стрімінгу з очікуванням початку наступної хвилини...")
                        self.start_websocket_stream(getattr(self, '_websocket_provider', 'massive'), getattr(self, '_websocket_symbols', []))
                else:
                    self.log_update.emit(f"🚨 Загалом знайдено {total_real_gaps} прогалин, що потребують завантаження.")
                    self.status_update.emit("Потрібне автозавантаження")
                    self.start_auto_download(db_path, missing_gaps_per_table, use_ccxt, use_massive)
            else:
                self.status_update.emit("База даних в ідеальному стані")
                self.log_update.emit("🎉 Аналіз завершено. Усі дані повні (з урахуванням свят).")
                self.task_finished.emit("analyze_database")
                
                if getattr(self, '_pending_websocket_start', False):
                    self._pending_websocket_start = False
                    self.log_update.emit("🚀 Запуск Live-стрімінгу з очікуванням початку наступної хвилини...")
                    self.start_websocket_stream(getattr(self, '_websocket_provider', 'massive'), getattr(self, '_websocket_symbols', []))
                
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
        
        if getattr(self, '_pending_websocket_start', False):
            self._pending_websocket_start = False
            self.log_update.emit("🚀 Історія завантажена. Запуск Live-стрімінгу з очікуванням початку наступної хвилини...")
            self.start_websocket_stream(getattr(self, '_websocket_provider', 'massive'), getattr(self, '_websocket_symbols', []))

    def start_scheduler(self, db_path, config_states):
        import json, os
        from utils.PathManager import PathManager
        
        # Перевірка режиму оновлення даних
        update_mode = "polling"
        target_assets = []
        try:
            config_path = PathManager.get_settings_path()
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    settings_data = json.load(f)
                    update_mode = settings_data.get("downloader", {}).get("update_mode", "polling")
                    target_assets = settings_data.get("copilot", {}).get("target_assets", [])
        except Exception: pass

        if update_mode == "websockets":
            self.log_update.emit("📡 Режим Websockets увімкнено. Підготовка: скачування історії через API...")
            self._pending_websocket_start = True
            self._websocket_symbols = target_assets if target_assets else ["C:EURUSD"]
            self._websocket_provider = "massive"
            self._db_path_cache = db_path
            self._config_states_cache = config_states
            
            use_massive = config_states.get("cb_download_massive", False)
            use_ccxt = config_states.get("cb_download_ccxt", False)
            self.analyze_database(db_path, use_ccxt=use_ccxt, use_massive=use_massive)
        else:
            if self.scheduler_thread and self.scheduler_thread.isRunning():
                self.log_update.emit("⚠️ Планувальник вже працює.")
                return
                
            self.scheduler_thread = CopilotSchedulerThread(db_path, config_states)
            self.scheduler_thread.log_signal.connect(lambda msg: self.log_update.emit(msg))
            self.scheduler_thread.start()

    def start_websocket_stream(self, provider: str, symbols: list):
        if self.websocket_thread and self.websocket_thread.isRunning():
            self.log_update.emit("⚠️ WebSocket трансляція вже працює.")
            return
            
        self.websocket_thread = WebsocketStreamerThread(provider, symbols)
        self.websocket_thread.log_signal.connect(lambda msg: self.log_update.emit(msg))
        
        # Обробка збереження пакету тіків у БД
        def on_flush_ticks(sym, ticks):
            import pandas as pd
            from utils.PathManager import PathManager
            dbm = DataBaseManager(PathManager.get_db_path())
            table_name = f"{sym.replace(':', '')}_ticks"
            df = pd.DataFrame(ticks)
            dbm.insert_data_from_pandas_auto(table_name, df)
            dbm.disconnect()

        self.websocket_thread.flush_ticks_signal.connect(on_flush_ticks)
        
        # Обробка закритої свічки - зберігаємо в БД
        def on_candle_closed(table_name, closed_candle):
            import pandas as pd
            from utils.PathManager import PathManager
            dbm = DataBaseManager(PathManager.get_db_path())
            df = pd.DataFrame([closed_candle])
            dbm.insert_data_from_pandas_auto(table_name, df)
            dbm.disconnect()
            self.log_update.emit(f"🕯️ Нова свічка збережена: {table_name}")
            
            # Емітуємо подію для сканування стратегій саме на цьому таймфреймі
            tf_str = table_name.split('_')[-1]
            self.trigger_signal_scan.emit(tf_str)
            
            # Також емітуємо звичайну подію для можливих UI тригерів
            self.task_finished.emit("download")
            
        self.websocket_thread.candle_closed_signal.connect(on_candle_closed)
        self.websocket_thread.start()
        self.status_update.emit(f"Live Stream ({provider})...")
        
        # Запускаємо таймер для одноразового завантаження пропущеної (перехідної) свічки
        import time
        from PyQt6.QtCore import QTimer
        current_time = time.time()
        seconds_to_next_minute = 60 - (current_time % 60)
        # Додаємо 5 секунд буферу для того, щоб біржа встигла закрити свічку
        delay_ms = int((seconds_to_next_minute + 5) * 1000)
        
        def fetch_missing_candle():
            self.log_update.emit("🔍 Запуск REST API для завантаження пропущеної (перехідної) свічки...")
            use_massive = getattr(self, '_config_states_cache', {}).get("cb_download_massive", False)
            use_ccxt = getattr(self, '_config_states_cache', {}).get("cb_download_ccxt", False)
            if hasattr(self, '_db_path_cache'):
                self.analyze_database(self._db_path_cache, use_ccxt=use_ccxt, use_massive=use_massive)
                
        QTimer.singleShot(delay_ms, fetch_missing_candle)

    def stop_all(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.stop()
            self.downloader_thread.wait()
            
        if self.scheduler_thread and self.scheduler_thread.isRunning():
            self.scheduler_thread.stop()
            self.scheduler_thread.wait()

        if self.websocket_thread and self.websocket_thread.isRunning():
            self.websocket_thread.stop()
            self.websocket_thread.wait()
