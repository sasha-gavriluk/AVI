import pyqtgraph as pg
import pandas as pd

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

class OpenGraphicsView(QMainWindow):

    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, db_manager=None):
        super().__init__()

        self.db_manager = db_manager

        self.wce_data = self.db_manager.get_data_as_dataframe("EURUSD_minute")["WCE"].tolist()

        # Завжди в самому кінці конструктора викликаємо ініціалізацію всіх віджетів
        self._init_all_widgets()

    #-----------------------------------
    # Ініціалізація всіх віджетів
    #-----------------------------------

    def _init_all_widgets(self):
        """Метод для ініціалізації всіх віджетів та налаштування графіка"""

        self.setWindowTitle("Open Graphics View")
        self.showMaximized()

        self.graph_widget = pg.GraphicsLayoutWidget()
        self.setCentralWidget(self.graph_widget)

        self.plots = self.graph_widget.addPlot(title="Графік")
        self.plots.showGrid(x=True, y=True)
        x, y_body, y_shadow, y_price = self._parse_coordinate_for_list(self.wce_data)

        self.plots.addLegend(offset=(30, 30))

        pen_body = pg.mkPen(color='#FF3333', width=3)
        pen_shadow = pg.mkPen(color='g', width=0.5)
        pen_price = pg.mkPen(color=(0, 100, 255, 150), width=2, style=Qt.PenStyle.DashLine)

        # Малюємо графіки, використовуючи наші пензлики та додаючи легенду
        self.plots.plot(x, y_body, pen=pen_body, name="Тіло (Body)")
        self.plots.plot(x, y_shadow, pen=pen_shadow, name="Тінь (Shadow)")
        self.plots.plot(x, y_price, pen=pen_price, name="Масштаб (Scale)")

        # -----------------------------------------
        # НАЛАШТУВАННЯ КАМЕРИ (ZOOM та PAN)
        # -----------------------------------------
        
        if x:
            last_indax = x[-1]
            window_size = 15

            self.plots.setXRange(last_indax - window_size, last_indax, padding=0)
            self.plots.setYRange(0, 10, padding=0)
            self.plots.setMouseEnabled(x=True, y=False)
            self.plots.setLimits(
                xMin=0, xMax=last_indax + 3,
                yMin=0, yMax=10,
                minXRange=window_size, maxXRange=window_size)

    #--------------------------------
    # Метод для парсингу координат з DataFrame
    #--------------------------------

    def _parse_coordinate_for_list(self, df):
        """Метод для парсингу координат з DataFrame та підготовки даних для графіка"""
        
        x = []
        y_body = []
        y_shadow = []
        y_price = []

        for index, token in enumerate(df):

            if pd.isna(token) or len(str(token)) < 4:
                continue

            token = str(token)

            x.append(index)

            y_body.append(int(token[1]))
            y_shadow.append(int(token[2]))
            y_price.append(int(token[3]))

        return x, y_body, y_shadow, y_price