import os
import pandas as pd
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMenuBar, QSplitter
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, pyqtSignal

os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"
import finplot as fplt

from gui.visual.UiElements import TradeDetailPanel

#==================================
# TabChartVisual
#==================================
class TabChartVisual(QWidget):
    chart_clicked = pyqtSignal(object) # Сигнал при кліку на графік
    x_range_changed = pyqtSignal(object, object) # Сигнал при зміні діапазону X
    reset_camera_requested = pyqtSignal()

    # ----------------------------------
    # __init__, ініціалізація візуалу графіку
    # ----------------------------------
    # Параметри:
    # parent (QWidget): Батьківський віджет
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ax = None
        self.trades_drawn = False
        self.init_ui()

    # ----------------------------------
    # init_ui, побудова інтерфейсу
    # ----------------------------------
    # Параметри: немає
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
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.chart_container)
        
        self.detail_panel = TradeDetailPanel()
        self.detail_panel.hide()
        self.splitter.addWidget(self.detail_panel)
        self.splitter.setSizes([800, 200])
        
        fplt.foreground = '#eef'
        fplt.background = '#1e1f22'
        fplt.odd_plot_background = '#25262a'
        fplt.cross_hair_color = '#fff'

    # ----------------------------------
    # setup_chart, налаштування та відображення свічок
    # ----------------------------------
    # Параметри:
    # df (pd.DataFrame): Дані OHLCV
    def setup_chart(self, df: pd.DataFrame):
        if self.ax is None:
            self.ax = fplt.create_plot()
            self.chart_layout.addWidget(self.ax.vb.win)
            self.ax.vb.sigXRangeChanged.connect(self._on_x_range_changed)
            self.ax.scene().sigMouseClicked.connect(self._on_chart_clicked)
        else:
            self.ax.clear()
            self.ax.vb.reset()
            self.detail_panel.hide()
            if hasattr(self.ax.vb, 'datasrc'):
                self.ax.vb.datasrc = None
                
        self.trades_drawn = False
        df_chart = df[['open', 'close', 'high', 'low']]
        fplt.candlestick_ochl(df_chart, ax=self.ax)
        fplt.refresh()
        
    # ----------------------------------
    # update_chart_data, дозавантаження та перемальовування
    # ----------------------------------
    # Параметри:
    # df (pd.DataFrame): Дані OHLCV
    # added_count (int): Кількість нових рядків
    def update_chart_data(self, df: pd.DataFrame, added_count: int):
        (x_min, x_max), (y_min, y_max) = self.ax.vb.viewRange()
        
        self.ax.clear()
        self.ax.vb.reset()
        if hasattr(self.ax.vb, 'datasrc'):
            self.ax.vb.datasrc = None
            
        df_chart = df[['open', 'close', 'high', 'low']]
        fplt.candlestick_ochl(df_chart, ax=self.ax)
        
        self.ax.vb.setXRange(x_min + added_count, x_max + added_count, padding=0)
        self.ax.vb.setYRange(y_min, y_max, padding=0)
        fplt.refresh()

    # ----------------------------------
    # draw_trades, малювання маркерів угод
    # ----------------------------------
    # Параметри:
    # entries (pd.Series): Точки відкриття
    # exits (pd.Series): Точки закриття
    def draw_trades(self, entries: pd.Series, exits: pd.Series):
        if self.ax is None: return
        fplt.plot(entries, style='v', color='#0000ff', legend='Відкриття')
        fplt.plot(exits, style='^', color='#ff0000', legend='Закриття')
        fplt.refresh()
        self.trades_drawn = True

    # ----------------------------------
    # _on_x_range_changed, ретрансляція сигналу
    # ----------------------------------
    def _on_x_range_changed(self, vb, xrange):
        self.x_range_changed.emit(vb, xrange)

    # ----------------------------------
    # _on_chart_clicked, ретрансляція сигналу
    # ----------------------------------
    def _on_chart_clicked(self, event):
        self.chart_clicked.emit(event)
