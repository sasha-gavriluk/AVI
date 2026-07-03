from gui.visual.TabSettingsVisual import TabSettingsVisual
from gui.visual.TabExplorerVisual import TabExplorerVisual
from gui.visual.TabDownloaderVisual import TabDownloaderVisual
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
        # Вкладки "Графік" і "Тестер стратегій" тимчасово відсутні в
        # системі (заморожено, підлягають рефакторингу). Історія й
        # обґрунтування — Code/REFACTOR_LOG.md, старий код — git-коміт 0eeea95.
        self.copilot_tab = TabCopilotVisual()
        self.live_algo_tab = TabLiveAlgorithmicVisual()
