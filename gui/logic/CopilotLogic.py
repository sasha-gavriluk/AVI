from PyQt6.QtCore import QObject, pyqtSignal
from core.services.copilot_service import CopilotService
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
    # interval_minutes (int): інтервал у хвилинах
    def start_auto_routine(self, config_states: dict, interval_minutes: int):
        from utils.PathManager import PathManager
        self.service.start_scheduler(PathManager.get_db_path(), config_states, interval_minutes)

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
