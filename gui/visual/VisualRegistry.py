from gui.visual.TabSettingsVisual import TabSettingsVisual
from gui.visual.TabExplorerVisual import TabExplorerVisual
from gui.visual.TabDownloaderVisual import TabDownloaderVisual
# ВІДКЛЮЧЕНО: вкладка "Графік" тимчасово знята з системи, підлягає
# рефакторингу й оновленню (буде переписана на іншому принципі).
# from gui.visual.TabChartVisual import TabChartVisual
# !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
# ВІДКЛЮЧЕНО (BACKTEST): вкладка "Тестер стратегій" тимчасово знята з
# системи, підлягає рефакторингу й оновленню. УВАГА: цей модуль торкається
# й інших файлів поза собою — див. однаково позначені блоки в:
# gui/logic/LogicRegistry.py, gui/GuiBinder.py, gui/MainWindow.py.
# !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
# from gui.visual.TabBacktestVisual import TabBacktestVisual
from gui.visual.TabCopilotVisual import TabCopilotVisual
from gui.visual.TabLiveAlgorithmicVisual import TabLiveAlgorithmicVisual

#==================================
# VisualRegistry
#==================================
class VisualRegistry:
    # ----------------------------------
    # __init__, ініціалізація реєстру візуалу
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        self.settings_tab = TabSettingsVisual()
        self.explorer_tab = TabExplorerVisual()
        self.downloader_tab = TabDownloaderVisual()
        # ВІДКЛЮЧЕНО: вкладка "Графік" тимчасово знята з системи,
        # підлягає рефакторингу й оновленню. self.chart_tab більше не існує.
        # self.chart_tab = TabChartVisual()
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # ВІДКЛЮЧЕНО (BACKTEST): вкладка "Тестер стратегій" тимчасово знята
        # з системи. self.backtest_tab більше не існує. Пов'язані блоки:
        # gui/logic/LogicRegistry.py, gui/GuiBinder.py, gui/MainWindow.py.
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # self.backtest_tab = TabBacktestVisual()
        self.copilot_tab = TabCopilotVisual()
        self.live_algo_tab = TabLiveAlgorithmicVisual()
