from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox, QRadioButton,
    QComboBox, QLineEdit, QCheckBox, QDateTimeEdit, QPushButton,
    QProgressBar, QTextEdit, QLabel, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QDateTime
from gui.visual.UiElements import TitleLabel

#==================================
# StatsCard
#==================================
class StatsCard(QFrame):
    # ----------------------------------
    # __init__, ініціалізація картки статистики
    # ----------------------------------
    # Параметри:
    # title (str): Заголовок картки
    # value (str): Значення
    # color_hex (str): Колір тексту значення
    def __init__(self, title: str, value: str, color_hex: str):
        super().__init__()
        self.setStyleSheet("QFrame { background-color: #181825; border: 1px solid #313244; border-radius: 6px; padding: 10px; }")
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        
        t_label = QLabel(title)
        t_label.setStyleSheet("font-size: 10px; font-weight: bold; color: #89DCEB;")
        layout.addWidget(t_label)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color_hex};")
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)

#==================================
# TabDownloaderVisual
#==================================
class TabDownloaderVisual(QWidget):
    # ----------------------------------
    # __init__, ініціалізація вкладки завантажувача
    # ----------------------------------
    # Параметри:
    # parent (QWidget): Батьківський віджет
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    # ----------------------------------
    # init_ui, побудова інтерфейсу
    # ----------------------------------
    # Параметри: немає
    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Ліва панель
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        left_layout.addWidget(TitleLabel("📥 ІНТЕГРОВАНИЙ ЗАВАНТАЖУВАЧ API"))
        
        source_group = QGroupBox("Цільове джерело та база даних")
        source_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; margin-top: 12px; padding-top: 12px; font-weight: bold; color: #A6ADC8; }")
        source_layout = QVBoxLayout(source_group)
        self.radio_massive = QRadioButton("Massive API (База 'main.duckdb')")
        self.radio_massive.setChecked(True)
        self.radio_exchange = QRadioButton("Біржовий коннектор (Окремі бази)")
        source_layout.addWidget(self.radio_massive)
        source_layout.addWidget(self.radio_exchange)
        left_layout.addWidget(source_group)
        
        self.exchange_group = QGroupBox("Вибір Біржі (для біржового коннектору)")
        self.exchange_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; margin-top: 10px; padding-top: 12px; color: #A6ADC8; }")
        exchange_layout = QHBoxLayout(self.exchange_group)
        exchange_layout.addWidget(QLabel("Конектор:"))
        self.exchange_combo = QComboBox()
        self.exchange_combo.addItems(["Bybit", "Binance"])
        exchange_layout.addWidget(self.exchange_combo, stretch=1)
        left_layout.addWidget(self.exchange_group)
        self.exchange_group.setEnabled(False)
        
        symbols_group = QGroupBox("Активи для завантаження")
        symbols_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; margin-top: 10px; padding-top: 12px; color: #A6ADC8; }")
        symbols_layout = QVBoxLayout(symbols_group)
        self.symbols_input = QLineEdit("EURUSD, GBPUSD")
        symbols_layout.addWidget(self.symbols_input)
        self.presets_row = QHBoxLayout()
        self.presets_row.addWidget(QLabel("Пресети:"))
        symbols_layout.addLayout(self.presets_row)
        left_layout.addWidget(symbols_group)
        
        tf_group = QGroupBox("Таймфрейми")
        tf_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; margin-top: 10px; padding-top: 12px; color: #A6ADC8; }")
        tf_grid = QGridLayout(tf_group)
        self.tf_checkboxes = {}
        for i, tf in enumerate(["1m", "5m", "15m", "30m", "1h", "4h", "1d"]):
            cb = QCheckBox(tf)
            if tf in ["15m", "1h"]: cb.setChecked(True)
            tf_grid.addWidget(cb, i // 4, i % 4)
            self.tf_checkboxes[tf] = cb
        left_layout.addWidget(tf_group)
        
        time_group = QGroupBox("Часовий діапазон")
        time_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; margin-top: 10px; padding-top: 12px; color: #A6ADC8; }")
        time_layout = QVBoxLayout(time_group)
        row_start = QHBoxLayout()
        row_start.addWidget(QLabel("Від:"))
        self.date_start = QDateTimeEdit(QDateTime.currentDateTime().addMonths(-3))
        self.date_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        row_start.addWidget(self.date_start, stretch=1)
        time_layout.addLayout(row_start)
        
        row_end = QHBoxLayout()
        row_end.addWidget(QLabel("До:"))
        self.date_end = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        row_end.addWidget(self.date_end, stretch=1)
        time_layout.addLayout(row_end)
        
        self.quick_time_layout = QHBoxLayout()
        time_layout.addLayout(self.quick_time_layout)
        left_layout.addWidget(time_group)
        
        self.btn_start = QPushButton("🚀 РОЗПОЧАТИ ЗАВАНТАЖЕННЯ")
        self.btn_start.setStyleSheet("QPushButton { background-color: #A6E3A1; color: #11111B; font-size: 14px; font-weight: bold; padding: 12px; border-radius: 6px; margin-top: 15px; }")
        left_layout.addWidget(self.btn_start)
        left_layout.addStretch()
        
        # Права панель
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.addWidget(QLabel("📊 МОНІТОРИНГ ТА ЖИВИЙ ВИВІД МОДУЛІВ"))
        
        stats_layout = QHBoxLayout()
        self.card_db = StatsCard("ЦІЛЬОВА БД", "trading_data_massive.duckdb", "#89B4FA")
        self.card_candles = StatsCard("ЗАГАЛОМ СВІЧОК", "0", "#A6E3A1")
        self.card_status = StatsCard("СТАТУС АКТИВНОСТІ", "IDLE (Очікування)", "#CDD6F4")
        stats_layout.addWidget(self.card_db)
        stats_layout.addWidget(self.card_candles)
        stats_layout.addWidget(self.card_status)
        right_layout.addLayout(stats_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #313244; background-color: #181825; height: 18px; text-align: center; border-radius: 4px; color: #CDD6F4; font-weight: bold; } QProgressBar::chunk { background-color: #89B4FA; border-radius: 3px; }")
        right_layout.addWidget(self.progress_bar)
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("QTextEdit { background-color: #11111B; color: #A6ADC8; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; border: 1px solid #313244; border-radius: 6px; padding: 10px; }")
        right_layout.addWidget(self.log_console)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)
