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
        # ЧАСТКОВО ВІДКЛЮЧЕНО: вкладка "Графік" (TabChartVisual) знята з
        # системи й підлягає рефакторингу, але self.chart лишається живим —
        # get_available_assets()/get_backtest_tables() використовуються
        # вкладками Налаштування й Бектест, не тільки самим графіком.
        self.chart = ChartLogic()
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # ЧАСТКОВО ВІДКЛЮЧЕНО (BACKTEST): вкладка "Тестер стратегій"
        # (TabBacktestVisual) знята з системи й підлягає рефакторингу, але
        # self.backtest навмисно ЛИШАЄТЬСЯ живим — BacktestLogic.__init__
        # безпечний (лише читає strategy_meta.json, жодних потоків/таймерів),
        # а self.copilot тут — це та сама TradingCopilot-логіка, якою
        # користується "Автономний Копілот" (CopilotLogic), тож видаляти
        # інстанціювання не можна. Пов'язані блоки: gui/visual/VisualRegistry.py,
        # gui/GuiBinder.py, gui/MainWindow.py.
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        self.backtest = BacktestLogic(self.copilot)
        self.live_algo = LiveAlgorithmicLogic()
