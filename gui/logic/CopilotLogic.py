from PyQt6.QtCore import QObject, pyqtSignal
from gui.logic.copilot_service import CopilotService
from utils.algorithms.backtesting.TradingCopilot import TradingCopilot

#==================================
# CopilotLogic
#==================================
class CopilotLogic(QObject):
    stats_ready = pyqtSignal(object, dict) # df, best_comps
    
    # ----------------------------------
    # __init__, ініціалізація логіки Copilot
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        super().__init__()
        from utils.PathManager import PathManager
        # Ініціалізуємо TradingCopilot один раз для всього додатку
        self.trading_copilot = TradingCopilot(db_path=PathManager.get_db_path())
        self.service = CopilotService()
        self._scan_workers = {}
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): live-тригер сканування
        # класичних стратегій по закритій свічці (websocket-режим).
        # _on_trigger_signal_scan нижче тепер лише логує повідомлення,
        # з'єднання сигналу закоментовано, щоб не створювався ScanWorker,
        # який усе одно впав би (scan_markets_for_signals заморожений).
        # Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # self.service.trigger_signal_scan.connect(self._on_trigger_signal_scan)

    def _on_trigger_signal_scan(self, tf_str: str):
        # ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): див. коментар у __init__ —
        # сигнал, що викликав цей метод, більше не підключений.
        self.service.log_update.emit(f"⏸️ Сканування класичних стратегій ({tf_str}) тимчасово заморожене.")
        return

        # active_strategies = []
        # target_assets = []
        # try:
        #     from utils.PathManager import PathManager
        #     import json, os
        #     settings_path = PathManager.get_settings_path()
        #     if os.path.exists(settings_path):
        #         with open(settings_path, 'r', encoding='utf-8') as f:
        #             settings_data = json.load(f)
        #             active_strategies = settings_data.get("copilot", {}).get("active_strategies_tree", {}).get(tf_str, [])
        #             target_assets = settings_data.get("copilot", {}).get("target_assets", [])
        # except Exception as e:
        #     self.service.log_update.emit(f"⚠️ Помилка завантаження налаштувань для сканування: {e}")
        #
        # if active_strategies:
        #     self.service.log_update.emit(f"🔍 Запуск сканування стратегій для {tf_str}...")
        #
        #     from PyQt6.QtCore import QThread
        #     from utils.notification_service import TelegramNotifier
        #
        #     class ScanWorker(QThread):
        #         def __init__(self, copilot, strats, assets, tf):
        #             super().__init__()
        #             self.copilot = copilot
        #             self.strats = strats
        #             self.assets = assets
        #             self.tf = tf
        #             self.notifier = TelegramNotifier()
        #         def run(self):
        #             try:
        #                 self.copilot.scan_markets_for_signals(
        #                     self.strats,
        #                     self.notifier,
        #                     target_assets=self.assets,
        #                     target_timeframes=[self.tf]
        #                 )
        #             except Exception as e:
        #                 print(f"Signal scan error: {e}")
        #
        #     # Keep reference to avoid garbage collection
        #     worker = ScanWorker(self.trading_copilot, active_strategies, target_assets, tf_str)
        #     self._scan_workers[tf_str] = worker
        #
        #     def on_finished(t=tf_str):
        #         self.service.log_update.emit(f"✅ Сканування {t} завершено.")
        #         if t in self._scan_workers:
        #             del self._scan_workers[t]
        #
        #     worker.finished.connect(on_finished)
        #     worker.start()

    # ----------------------------------
    # analyze_database, запуск аналізу прогалин в БД
    # ----------------------------------
    # Параметри:
    # use_ccxt (bool): чи використовувати CCXT
    # use_massive (bool): чи використовувати Massive
    def analyze_database(self, use_ccxt: bool, use_massive: bool):
        from utils.PathManager import PathManager
        self.service.analyze_database(PathManager.get_db_path(), use_ccxt, use_massive)

    # ----------------------------------
    # start_auto_routine, запуск автономного планувальника
    # ----------------------------------
    # Параметри:
    # config_states (dict): словник станів чекбоксів
    def start_auto_routine(self, config_states: dict):
        from utils.PathManager import PathManager
        self.service.start_scheduler(PathManager.get_db_path(), config_states)

    # ----------------------------------
    # stop_auto_routine, зупинка планувальника
    # ----------------------------------
    # Параметри: немає
    def stop_auto_routine(self):
        self.service.stop_all()

    # ----------------------------------
    # request_stats_async, отримання статистики для візуалу асинхронно
    # ----------------------------------
    # Параметри: немає
    def request_stats_async(self):
        if hasattr(self, '_stats_thread') and self._stats_thread.isRunning():
            return
            
        from PyQt6.QtCore import QThread, pyqtSignal
        class StatsFetcherThread(QThread):
            result_signal = pyqtSignal(object, dict) # df, best_comps
            def __init__(self, copilot):
                super().__init__()
                self.copilot = copilot
            def run(self):
                df = self.copilot.get_memory_df()
                best_comps = self.copilot.get_best_components()
                self.result_signal.emit(df, best_comps)
                
        self._stats_thread = StatsFetcherThread(self.trading_copilot)
        self._stats_thread.result_signal.connect(self._on_stats_ready)
        self._stats_thread.start()
        
    def _on_stats_ready(self, df, best_comps):
        if hasattr(self, 'stats_ready'):
            self.stats_ready.emit(df, best_comps)
