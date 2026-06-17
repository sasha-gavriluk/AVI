import os
import sys

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QMessageBox
from PyQt6.QtCore import pyqtSlot
import finplot as fplt

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
        
        # Сигнали, які раніше були в MainWindow
        self.visual_registry.explorer_tab.btn_open_chart.clicked.connect(self.on_open_chart_clicked)
        self.visual_registry.backtest_tab.request_show_chart.connect(self.on_backtest_show_chart)
        
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
            
        elif widget == self.visual_registry.chart_tab:
            # Оновлюємо список доступних активів на графіку
            if hasattr(self.visual_registry.chart_tab, 'refresh_menus'):
                self.visual_registry.chart_tab.refresh_menus()
                
            # Оновлюємо випадаючий список бектестів
            from PyQt6.QtGui import QAction
            tables = self.logic_registry.chart.get_backtest_tables()
            self.visual_registry.chart_tab.show_trades_menu.clear()
            if not tables:
                act = QAction(f"Немає бектестів", self.visual_registry.chart_tab)
                act.setEnabled(False)
                self.visual_registry.chart_tab.show_trades_menu.addAction(act)
            else:
                for tbl in tables:
                    act = QAction(f"{tbl.replace('backtest_', '')}", self.visual_registry.chart_tab)
                    act.triggered.connect(lambda checked, t=tbl: self._show_trades_from_action(t))
                    self.visual_registry.chart_tab.show_trades_menu.addAction(act)
                    
        elif widget == self.visual_registry.backtest_tab:
            # Оновлюємо списки активів у вкладці бектестів
            if hasattr(self.visual_registry.backtest_tab, 'refresh_menus'):
                self.visual_registry.backtest_tab.refresh_menus()

    def _load_chart_from_action(self, db_path, table_name):
        if self.visual_registry.chart_tab.ax is not None:
            self.visual_registry.chart_tab.ax.clear()
        self.logic_registry.chart.request_initial_data_async(db_path, table_name)

    def _show_trades_from_action(self, trades_table):
        if not self.logic_registry.chart.load_trades(trades_table): return
        import pandas as pd
        entries = pd.Series(index=self.logic_registry.chart.df.index, dtype=float)
        exits = pd.Series(index=self.logic_registry.chart.df.index, dtype=float)
        for _, trade in self.logic_registry.chart.trades_df.iterrows():
            try:
                entry_time = pd.to_datetime(trade['EntryTimestamp'], unit='ms')
                exit_time = pd.to_datetime(trade['ExitTimestamp'], unit='ms')
                if entry_time in self.logic_registry.chart.df.index:
                    high = self.logic_registry.chart.df.loc[entry_time, 'high']
                    entries.loc[entry_time] = high + (high * 0.0005)
                if exit_time in self.logic_registry.chart.df.index:
                    low = self.logic_registry.chart.df.loc[exit_time, 'low']
                    exits.loc[exit_time] = low - (low * 0.0005)
            except Exception: pass
        self.visual_registry.chart_tab.draw_trades(entries, exits)

    # ----------------------------------
    # on_open_chart_clicked, відкрити графік
    # ----------------------------------
    # Параметри: немає
    @pyqtSlot()
    def on_open_chart_clicked(self):
        table_name = self.logic_registry.explorer.current_table_name
        if not table_name:
            return
            
        db_path = self.logic_registry.explorer.db_service.current_db_path
        if db_path:
            db_name = os.path.basename(db_path)
            self._load_chart_from_action(db_name, table_name)
            self.tabs.setCurrentWidget(self.visual_registry.chart_tab)
            
    # ----------------------------------
    # on_backtest_show_chart, відкрити графік бектесту
    # ----------------------------------
    # Параметри: 
    # db_name (str): назва бд
    # backtest_table (str): назва таблиці бектесту
    # asset_table (str): назва оригінальної таблиці активу
    @pyqtSlot(str, str, str)
    def on_backtest_show_chart(self, db_name: str, backtest_table: str, asset_table: str):
        self._load_chart_from_action(db_name, asset_table)
        self._show_trades_from_action(backtest_table)
        self.tabs.setCurrentWidget(self.visual_registry.chart_tab)

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

