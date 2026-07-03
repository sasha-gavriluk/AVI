from gui.logic.SettingsLogic import SettingsLogic
from gui.logic.ExplorerLogic import ExplorerLogic
from gui.logic.DownloaderLogic import DownloaderLogic
from gui.logic.ChartLogic import ChartLogic
from gui.logic.BacktestLogic import BacktestLogic
from gui.logic.CopilotLogic import CopilotLogic
from gui.logic.LiveAlgorithmicLogic import LiveAlgorithmicLogic

#==================================
# LogicRegistry
#==================================
class LogicRegistry:
    # ----------------------------------
    # __init__, ініціалізація реєстру логіки
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        # Ініціалізуємо Copilot першим і прокидаємо його далі
        self.copilot = CopilotLogic()
        self.settings = SettingsLogic()
        self.explorer = ExplorerLogic()
        self.downloader = DownloaderLogic()
        # Вкладка "Графік" відсутня, але self.chart лишається живим —
        # get_available_assets()/get_backtest_tables() потрібні Налаштуванням
        # і Бектесту (Code/REFACTOR_LOG.md).
        self.chart = ChartLogic()
        # Вкладка "Тестер стратегій" відсутня, але self.backtest лишається
        # живим — self.copilot тут та сама TradingCopilot-логіка, якою
        # користується "Автономний Копілот" (Code/REFACTOR_LOG.md).
        self.backtest = BacktestLogic(self.copilot)
        self.live_algo = LiveAlgorithmicLogic()
