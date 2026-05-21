from gui.logic.SettingsLogic import SettingsLogic
from gui.logic.ExplorerLogic import ExplorerLogic
from gui.logic.DownloaderLogic import DownloaderLogic
from gui.logic.ChartLogic import ChartLogic
from gui.logic.BacktestLogic import BacktestLogic
from gui.logic.LiveTradingLogic import LiveTradingLogic
from gui.logic.CopilotLogic import CopilotLogic

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
        self.chart = ChartLogic()
        self.backtest = BacktestLogic(self.copilot)
        self.live_trading = LiveTradingLogic(self.copilot)
