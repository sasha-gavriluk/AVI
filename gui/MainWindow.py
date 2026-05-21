import os
import sys

from PyQt6.QtWidgets import QMainWindow, QTabWidget
from PyQt6.QtCore import pyqtSlot
import finplot as fplt

from gui.views.ExplorerView import DuckDBExplorerWindow
from gui.views.ChartView import TradingChartApp
from gui.views.BacktestView import BacktestView
from gui.views.DownloaderView import DataDownloaderWindow
from gui.views.SettingsView import SettingsView
from gui.views.CopilotView import CopilotView
from gui.views.LiveTradingView import LiveTradingView
from gui.status_bar import GlobalStatusBar

class MainAppWindow(QMainWindow):
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
        
        # Ініціалізуємо вкладки
        self.explorer_tab = DuckDBExplorerWindow(default_db_path)
        self.chart_tab = TradingChartApp()
        
        # Шлях до конфігу стратегій
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'config', 'strategy_meta.json')
        self.backtest_tab = BacktestView(config_path)
        self.downloader_tab = DataDownloaderWindow()
        self.settings_tab = SettingsView()
        self.copilot_tab = CopilotView()
        self.live_trading_tab = LiveTradingView()
        
        # Налаштування колбеків для блокування БД
        self.explorer_tab.is_db_locked_callback = self.is_db_downloading
        self.explorer_tab.switch_to_downloader_callback = self.switch_to_downloader
        
        # Додаємо вкладки
        self.tabs.addTab(self.explorer_tab, "Провідник БД")
        self.tabs.addTab(self.chart_tab, "Торговий графік")
        self.tabs.addTab(self.backtest_tab, "Налаштування бектестів")
        self.tabs.addTab(self.downloader_tab, "Завантаження даних")
        self.tabs.addTab(self.copilot_tab, "Автономний Копілот")
        self.tabs.addTab(self.live_trading_tab, "Live Trading")
        self.tabs.addTab(self.settings_tab, "Налаштування")
        
        # Зв'язуємо натискання кнопки "Відкрити на графіку"
        self.explorer_tab.btn_open_chart.clicked.connect(self.on_open_chart_clicked)
        
        # Зв'язуємо сигнал "Відобразити на графіку" з вкладки бектестів
        self.backtest_tab.request_show_chart.connect(self.on_backtest_show_chart)
        
        # Автоматичне оновлення даних при переході на іншу вкладку
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.global_status.set_status("Готово")
        
    @pyqtSlot(int)
    def on_tab_changed(self, index):
        # Оновлення статусу
        tab_name = self.tabs.tabText(index)
        self.global_status.set_tab(tab_name)
        
        # Отримуємо віджет вкладки
        widget = self.tabs.widget(index)
        
        if widget == self.explorer_tab:
            # Оновлюємо бази даних у провіднику без блокування підключення
            self.explorer_tab.load_all_databases()
            
        elif widget == self.chart_tab:
            # Оновлюємо список доступних активів на графіку
            self.chart_tab._load_all_tables()
            # Оновлюємо випадаючий список бектестів для цього активу
            self.chart_tab.update_trades_menu()
            
        elif widget == self.backtest_tab:
            # Оновлюємо списки баз даних та активів у вкладці бектестів (із збереженням вибору)
            self.backtest_tab._load_databases()
        
    @pyqtSlot()
    def on_open_chart_clicked(self):
        # Коли натиснули кнопку відкриття, беремо поточну вибрану таблицю
        table_name = self.explorer_tab.current_table_name
        if not table_name:
            return
            
        db_path = self.explorer_tab.db_service.current_db_path
        if db_path:
            db_name = os.path.basename(db_path)
            # Завантажуємо графік
            self.chart_tab.load_chart(db_name, table_name)
            # Автоматично перемикаємось на вкладку графіка
            self.tabs.setCurrentWidget(self.chart_tab)
            
    @pyqtSlot(str, str)
    def on_backtest_show_chart(self, db_name: str, table_name: str):
        # При натисканні "Відобразити на графіку" з вкладки бектестів
        self.chart_tab.load_backtest(db_name, table_name)
        self.tabs.setCurrentWidget(self.chart_tab)

    def is_db_downloading(self, db_path):
        active_db = self.downloader_tab.get_active_download_db_path()
        return active_db is not None and os.path.abspath(active_db) == os.path.abspath(db_path)

    def switch_to_downloader(self, message):
        from PyQt6.QtWidgets import QMessageBox
        self.tabs.setCurrentWidget(self.downloader_tab)
        QMessageBox.warning(self, "База даних зайнята", message)

