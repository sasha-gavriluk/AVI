from PyQt6.QtCore import QObject, QThread, pyqtSignal
from gui.logic.CopilotService import CopilotService
from utils.algorithms.backtesting.TradingCopilot import TradingCopilot
from utils.PathManager import PathManager

#==================================
# StatsFetcherThread, фонове читання пам'яті/рейтингу Копілота
#==================================
class StatsFetcherThread(QThread):
    result_signal = pyqtSignal(object, dict) # df, best_comps

    def __init__(self, copilot):
        super().__init__()
        self.copilot = copilot

    def run(self):
        df = self.copilot.get_memory_df()
        best_comps = self.copilot.get_best_components()
        self.result_signal.emit(df, best_comps)

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
        # Ініціалізуємо TradingCopilot один раз для всього додатку
        self.trading_copilot = TradingCopilot(db_path=PathManager.get_db_path())
        self.service = CopilotService()
        self._stats_thread = None

    # ----------------------------------
    # analyze_database, запуск аналізу прогалин в БД
    # ----------------------------------
    # Параметри:
    # use_ccxt (bool): чи використовувати CCXT
    # use_massive (bool): чи використовувати Massive
    def analyze_database(self, use_ccxt: bool, use_massive: bool):
        self.service.analyze_database(PathManager.get_db_path(), use_ccxt, use_massive)

    # ----------------------------------
    # start_auto_routine, запуск автономного планувальника
    # ----------------------------------
    # Параметри:
    # config_states (dict): словник станів чекбоксів
    def start_auto_routine(self, config_states: dict):
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
        if self._stats_thread is not None and self._stats_thread.isRunning():
            return

        self._stats_thread = StatsFetcherThread(self.trading_copilot)
        self._stats_thread.result_signal.connect(self._on_stats_ready)
        self._stats_thread.start()

    def _on_stats_ready(self, df, best_comps):
        self.stats_ready.emit(df, best_comps)
