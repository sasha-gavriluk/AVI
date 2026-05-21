from gui.visual.TabSettingsVisual import TabSettingsVisual
from gui.visual.TabExplorerVisual import TabExplorerVisual
from gui.visual.TabDownloaderVisual import TabDownloaderVisual
from gui.visual.TabChartVisual import TabChartVisual
from gui.visual.TabBacktestVisual import TabBacktestVisual
from gui.visual.TabLiveTradingVisual import TabLiveTradingVisual
from gui.visual.TabCopilotVisual import TabCopilotVisual

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
        self.chart_tab = TabChartVisual()
        self.backtest_tab = TabBacktestVisual()
        self.copilot_tab = TabCopilotVisual()
        self.live_trading_tab = TabLiveTradingVisual()
