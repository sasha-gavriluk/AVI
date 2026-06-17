import os
import pandas as pd
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QMenuBar, QSplitter, 
                               QDialog, QRadioButton, QDialogButtonBox, QGroupBox, QButtonGroup, QComboBox, QCheckBox, QPushButton)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal

os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"

from gui.visual.UiElements import TradeDetailPanel, SimTradesPanel
from gui.visual.CustomChart import NativeChartWidget

#==================================
# TabChartVisual
#==================================
class TabChartVisual(QWidget):
    chart_clicked = pyqtSignal(object) # Залишаємо для сумісності з GuiBinder
    x_range_changed = pyqtSignal(object, object)
    reset_camera_requested = pyqtSignal()
    clear_temp_sim_requested = pyqtSignal()
    screenshot_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ax = None # Пустишка, щоб не крашився GuiBinder
        self.chart = None
        self.trades_drawn = False
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.menubar = QMenuBar(self)
        self.layout.setMenuBar(self.menubar)
        self.asset_menu = self.menubar.addMenu("Актив")
        
        self.tf_menu = self.menubar.addMenu("Таймфрейм")
        tf_action = QAction("15m", self)
        tf_action.setCheckable(True)
        tf_action.setChecked(True)
        self.tf_menu.addAction(tf_action)
        
        self.show_menu = self.menubar.addMenu("Вигляд")
        self.show_trades_menu = self.show_menu.addMenu("Відобразити угоди з тесту...")
        
        self.reset_cam_action = QAction("Скинути камеру", self)
        self.reset_cam_action.triggered.connect(self.reset_camera_requested.emit)
        self.show_menu.addAction(self.reset_cam_action)
        
        self.lock_cam_action = QAction("🔒 Заблокувати камеру", self)
        self.lock_cam_action.setCheckable(True)
        self.lock_cam_action.setChecked(True)
        self.show_menu.addAction(self.lock_cam_action)
        
        self.appearance_action = QAction("🎨 Налаштування вигляду...", self)
        self.show_menu.addAction(self.appearance_action)
        
        self.sim_menu = self.menubar.addMenu("Live Симуляція")
        self.sim_toggle_action = QAction("▶ Запустити симуляцію", self)
        self.sim_settings_action = QAction("⚙️ Налаштування...", self)
        self.sim_menu.addAction(self.sim_toggle_action)
        self.sim_menu.addAction(self.sim_settings_action)
        
        self.corner_widget = QWidget()
        corner_layout = QHBoxLayout(self.corner_widget)
        corner_layout.setContentsMargins(0, 2, 5, 2)
        
        self.btn_toggle_panel = QPushButton("📋 Панель угод")
        self.btn_toggle_panel.setStyleSheet("background-color: #313244; color: #CDD6F4; font-weight: bold; padding: 4px 15px; border-radius: 4px;")
        self.btn_toggle_panel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_panel.clicked.connect(self.toggle_right_panel)
        corner_layout.addWidget(self.btn_toggle_panel)
        
        self.btn_screenshot = QPushButton("📸 Скріншот")
        self.btn_screenshot.setStyleSheet("background-color: #8E24AA; color: white; font-weight: bold; padding: 4px 15px; border-radius: 4px;")
        self.btn_screenshot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_screenshot.clicked.connect(self.screenshot_requested.emit)
        corner_layout.addWidget(self.btn_screenshot)
        
        self.menubar.setCornerWidget(self.corner_widget, Qt.Corner.TopRightCorner)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.chart_container)
        
        self.detail_panel = TradeDetailPanel()
        self.detail_panel.hide()
        
        self.sim_panel = SimTradesPanel()
        self.sim_panel.hide()
        
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0,0,0,0)
        
        # Додаємо верхню панель з кнопкою закриття
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5, 5, 5, 5)
        self.btn_close_panel = QPushButton("✖ Закрити")
        self.btn_close_panel.setStyleSheet("QPushButton { background-color: transparent; color: #CDD6F4; border: none; font-weight: bold; } QPushButton:hover { color: #F38BA8; }")
        self.btn_close_panel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_panel.clicked.connect(self.right_panel.hide)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close_panel)
        right_layout.addLayout(header_layout)
        
        right_layout.addWidget(self.detail_panel)
        right_layout.addWidget(self.sim_panel)
        self.right_panel.hide()
        
        self.splitter.addWidget(self.right_panel)
        self.splitter.setSizes([800, 200])

    def toggle_right_panel(self):
        self.right_panel.setVisible(not self.right_panel.isVisible())

    def setup_chart(self, df: pd.DataFrame):
        if self.chart is None:
            self.chart = NativeChartWidget(self.chart_container)
            self.chart_layout.addWidget(self.chart)
            self.chart.chart_clicked.connect(self.chart_clicked.emit)
        else:
            self.right_panel.hide()
            self.detail_panel.hide()
            self.sim_panel.hide()
            self.chart.clear_markers()
            
        self.trades_drawn = False
        
        df_chart = self._format_df(df)
        if not df_chart.empty:
            self.chart.set_data(df_chart)

    def update_chart_data(self, df: pd.DataFrame, added_count: int, is_simulating: bool = False):
        if self.chart is None or df.empty: return
        
        if is_simulating:
            # Отримуємо тільки останній ряд і додаємо його як тік
            last_row = df.iloc[-1:]
            df_chart = self._format_df(last_row)
            if not df_chart.empty:
                self.chart.update_data(df_chart.iloc[0].to_dict())
        else:
            df_chart = self._format_df(df)
            if not df_chart.empty:
                self.chart.set_data(df_chart, maintain_view_for_added=added_count)

    def draw_trades(self, entries: pd.Series, exits: pd.Series):
        if self.chart is None: return
        
        self.chart.clear_markers()
        
        for time_val, price in entries.dropna().items():
            self.chart.add_marker(time_val=time_val, position='belowBar', shape='arrowUp', color='#26a69a', text='BUY')
            
        for time_val, price in exits.dropna().items():
            self.chart.add_marker(time_val=time_val, position='aboveBar', shape='arrowDown', color='#ef5350', text='SELL')
            
        self.trades_drawn = True

    def _format_df(self, df: pd.DataFrame) -> pd.DataFrame:
        df_chart = df.copy()
        if 'time' not in df_chart.columns:
            df_chart.reset_index(inplace=True)
            if 'index' in df_chart.columns:
                df_chart.rename(columns={'index': 'time'}, inplace=True)
                
        if 'time' not in df_chart.columns:
            return pd.DataFrame()
            
        df_chart = df_chart[['time', 'open', 'high', 'low', 'close']]
        df_chart.dropna(inplace=True)
        
        if not df_chart.empty:
            df_chart['time'] = pd.to_datetime(df_chart['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
        return df_chart
        return df_chart

#==================================
# AppearanceSettingsDialog
#==================================
from PyQt6.QtWidgets import QColorDialog, QPushButton, QHBoxLayout, QLabel
class AppearanceSettingsDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Налаштування вигляду")
        self.setModal(True)
        self.config = current_config.copy()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        def add_color_picker(label_text, key):
            row = QHBoxLayout()
            row.addWidget(QLabel(label_text))
            btn = QPushButton()
            btn.setStyleSheet(f"background-color: {self.config.get(key, '#000')}")
            def pick_color():
                col = QColorDialog.getColor()
                if col.isValid():
                    self.config[key] = col.name()
                    btn.setStyleSheet(f"background-color: {col.name()}")
            btn.clicked.connect(pick_color)
            row.addWidget(btn)
            layout.addLayout(row)
            
        add_color_picker("Зростаюча свічка (Up):", "up_color")
        add_color_picker("Спадаюча свічка (Down):", "down_color")
        add_color_picker("Фон графіка (Background):", "bg_color")
        add_color_picker("Колір сітки (Grid):", "grid_color")
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

#==================================
# SimulationSettingsDialog
#==================================
class SimulationSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Налаштування Симуляції")
        self.setModal(True)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Strategy selection
        strat_group = QGroupBox("Стратегія (Опціонально)")
        strat_layout = QVBoxLayout()
        self.combo_strat = QComboBox()
        self.combo_strat.addItem("Без стратегії")
        
        strat_layout.addWidget(self.combo_strat)
        strat_group.setLayout(strat_layout)
        layout.addWidget(strat_group)
        
        speed_group = QGroupBox("Швидкість (відносно таймфрейму)")
        speed_layout = QVBoxLayout()
        self.speed_bg = QButtonGroup(self)
        
        speeds = [
            ("1x", 1), 
            ("2x", 2), 
            ("5x", 5), 
            ("10x", 10), 
            ("50x", 50),
            ("100x", 100),
            ("500x", 500),
            ("1000x", 1000),
            ("5000x", 5000)
        ]
        self.speed_buttons = {}
        for text, val in speeds:
            rb = QRadioButton(text)
            self.speed_bg.addButton(rb)
            self.speed_buttons[val] = rb
            speed_layout.addWidget(rb)
        self.speed_buttons[500].setChecked(True)
        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)
        
        range_group = QGroupBox("Кількість прокрутки (від кінця бази)")
        range_layout = QVBoxLayout()
        self.range_bg = QButtonGroup(self)
        
        ranges = [("1 День", "1d"), ("1 Тиждень", "1w"), ("1 Місяць", "1m"), ("1 Рік", "1y"), ("Весь запис", "all")]
        self.range_buttons = {}
        for text, val in ranges:
            rb = QRadioButton(text)
            self.range_bg.addButton(rb)
            self.range_buttons[val] = rb
            range_layout.addWidget(rb)
        self.range_buttons["1w"].setChecked(True)
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)
        
        # New options for temporary tests
        test_group = QGroupBox("Тимчасові таблиці тестів")
        test_layout = QVBoxLayout()
        self.auto_delete_cb = QCheckBox("Автоматично видаляти тест після зупинки")
        self.auto_delete_cb.setChecked(True)
        test_layout.addWidget(self.auto_delete_cb)
        
        self.btn_clear_tests = QPushButton("🗑️ Очистити від усіх тестів (temp_sim_...)")
        self.btn_clear_tests.setStyleSheet("background-color: #F38BA8; color: #11111B; font-weight: bold; padding: 5px; border-radius: 4px;")
        test_layout.addWidget(self.btn_clear_tests)
        
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def showEvent(self, event):
        self.update_strategies()
        super().showEvent(event)

    def update_strategies(self):
        current = self.combo_strat.currentText()
        self.combo_strat.clear()
        self.combo_strat.addItem("Без стратегії")
        
        from utils.PathManager import PathManager
        import os
        strat_dir = PathManager.get_strategies_dir()
        if os.path.exists(strat_dir):
            strats = [f for f in os.listdir(strat_dir) if f.endswith('.py')]
            self.combo_strat.addItems(strats)
            
        if current in [self.combo_strat.itemText(i) for i in range(self.combo_strat.count())]:
            self.combo_strat.setCurrentText(current)

    def get_settings(self):
        multiplier = 10
        for val, rb in self.speed_buttons.items():
            if rb.isChecked(): multiplier = val
            
        rng = "1w"
        for val, rb in self.range_buttons.items():
            if rb.isChecked(): rng = val
            
        return {"multiplier": multiplier, "range": rng, "strategy": self.combo_strat.currentText(), "auto_delete": self.auto_delete_cb.isChecked()}
