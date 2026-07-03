import os
import sys

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QMessageBox
from PyQt6.QtCore import pyqtSlot

from gui.visual.VisualRegistry import VisualRegistry
from gui.logic.LogicRegistry import LogicRegistry
from gui.GuiBinder import GuiBinder
from gui.status_bar import GlobalStatusBar

#==================================
# MainAppWindow
#==================================
class MainAppWindow(QMainWindow):
    # ----------------------------------
    # __init__, ініціалізація головного вікна
    # ----------------------------------
    # Параметри:
    # default_db_path (str): шлях до БД за замовчуванням
    def __init__(self, default_db_path=None):
        super().__init__()
        self.setWindowTitle("Торговий Термінал & Провідник БД")
        self.resize(1400, 900)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Статус бар
        self.global_status = GlobalStatusBar(self)
        self.setStatusBar(self.global_status)
        self.global_status.set_status("Ініціалізація...")

        # Ініціалізуємо реєстри
        self.visual_registry = VisualRegistry()
        self.logic_registry = LogicRegistry()

        # Передаємо початковий шлях до БД в експлорер, якщо є
        if default_db_path:
            self.logic_registry.explorer.db_service.connect(default_db_path)

        # Зв'язуємо все
        self.binder = GuiBinder(self.visual_registry, self.logic_registry)

        # Налаштовуємо колбеки для GuiBinder
        self.binder.is_db_locked_callback = self.is_db_downloading
        self.binder.switch_to_downloader_callback = self.switch_to_downloader

        # Виконуємо біндинг подій
        self.binder.bind_all()

        # Додаємо вкладки
        self.binder.attach_to_tabs(self.tabs)

        # Автоматичне оновлення даних при переході на іншу вкладку
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.global_status.set_status("Готово")

    # ----------------------------------
    # on_tab_changed, обробка зміни вкладки
    # ----------------------------------
    # Параметри:
    # index (int): Індекс вибраної вкладки
    @pyqtSlot(int)
    def on_tab_changed(self, index):
        # Оновлення статусу
        tab_name = self.tabs.tabText(index)
        self.global_status.set_tab(tab_name)

        # Отримуємо віджет вкладки
        widget = self.tabs.widget(index)

        if widget == self.visual_registry.explorer_tab:
            # Оновлюємо бази даних у провіднику асинхронно
            self.visual_registry.explorer_tab.tree_view.clear()
            from PyQt6.QtWidgets import QTreeWidgetItem
            self.visual_registry.explorer_tab.tree_view.addTopLevelItem(QTreeWidgetItem(["Завантаження..."]))
            self.logic_registry.explorer.request_databases_async(self.is_db_downloading)

    # ----------------------------------
    # is_db_downloading, чи завантажується БД
    # ----------------------------------
    # Параметри:
    # db_path (str): шлях до БД
    def is_db_downloading(self, db_path):
        active_db = self.logic_registry.downloader.get_active_download_db_path()
        return active_db is not None and os.path.abspath(active_db) == os.path.abspath(db_path)

    # ----------------------------------
    # switch_to_downloader, перехід до вкладки завантажувача
    # ----------------------------------
    # Параметри:
    # message (str): повідомлення
    def switch_to_downloader(self, message):
        self.tabs.setCurrentWidget(self.visual_registry.downloader_tab)
        QMessageBox.warning(self, "База даних зайнята", message)
