import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPicture, QPainter, QPen, QBrush, QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class TimeAxisItem(pg.AxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mapping = {}

    def update_mapping(self, timestamps):
        self.mapping = dict(enumerate(timestamps))

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            val = int(v)
            if val in self.mapping:
                ts = pd.to_datetime(self.mapping[val])
                strings.append(ts.strftime('%H:%M\n%d %b'))
            else:
                strings.append("")
        return strings

class CustomViewBox(pg.ViewBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.y_auto_scale = True

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == Qt.MouseButton.LeftButton:
            # If user drags on Y axis, disable auto-scale
            pass # Standard behavior
        elif ev.button() == Qt.MouseButton.RightButton:
            # User uses right button to drag Y or X, but standard pyqtgraph scales. 
            self.y_auto_scale = False
        super().mouseDragEvent(ev, axis)
        
    def wheelEvent(self, ev, axis=None):
        # Force the scroll wheel to only zoom the X-axis (axis=0)
        # This prevents the Y-axis from manually squashing, allowing auto-scale to handle it.
        if axis is None:
            super().wheelEvent(ev, axis=0)
        else:
            super().wheelEvent(ev, axis)

class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data, up_color, down_color):
        super().__init__()
        self.data = data
        self.picture = QPicture()
        self.up_color = QColor(up_color)
        self.down_color = QColor(down_color)
        self.generate_picture()

    def set_colors(self, up_color, down_color):
        self.up_color = QColor(up_color)
        self.down_color = QColor(down_color)
        self.generate_picture()

    def set_data(self, data):
        self.data = data
        self.generate_picture()
        self.update()
        self.informViewBoundsChanged()

    def generate_picture(self):
        self.picture = QPicture()
        p = QPainter(self.picture)
        
        w = (self.data[1][0] - self.data[0][0]) / 3.0 if len(self.data) > 1 else 0.3
        
        for (x, open_val, close_val, min_val, max_val) in self.data:
            p.setPen(pg.mkPen(self.up_color if close_val > open_val else self.down_color))
            p.drawLine(QPointF(x, min_val), QPointF(x, max_val))
            
            if close_val > open_val:
                p.setBrush(QBrush(self.up_color))
                p.drawRect(QRectF(x - w, open_val, w * 2, close_val - open_val))
            else:
                p.setBrush(QBrush(self.down_color))
                p.drawRect(QRectF(x - w, close_val, w * 2, open_val - close_val))
                
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QRectF(self.picture.boundingRect())

class NativeChartWidget(QWidget):
    chart_clicked = pyqtSignal(object)
    request_more_data = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.up_color = '#26a69a'
        self.down_color = '#ef5350'
        self.bg_color = '#1e1f22'
        self.grid_color = '#404040'
        self.text_color = '#eef'
        
        pg.setConfigOptions(antialias=True)
        pg.setConfigOption('background', self.bg_color)
        pg.setConfigOption('foreground', self.text_color)
        
        self.time_axis = TimeAxisItem(orientation='bottom')
        self.view_box = CustomViewBox()
        self.plot_widget = pg.PlotWidget(viewBox=self.view_box, axisItems={'bottom': self.time_axis})
        self.layout.addWidget(self.plot_widget)
        
        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.hideButtons()
        self.plot_item.showGrid(x=True, y=True, alpha=0.5)
        self.plot_item.getAxis('left').setPen(self.grid_color)
        self.plot_item.getAxis('bottom').setPen(self.grid_color)
        
        self.candlestick = CandlestickItem([], self.up_color, self.down_color)
        self.plot_item.addItem(self.candlestick)
        
        self.markers = []
        self.df = None
        self.loading_more = False
        
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#a9a9a9', style=Qt.PenStyle.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#a9a9a9', style=Qt.PenStyle.DashLine))
        self.plot_item.addItem(self.v_line, ignoreBounds=True)
        self.plot_item.addItem(self.h_line, ignoreBounds=True)
        
        self.label = pg.TextItem(anchor=(0, 1), color=self.text_color, fill=self.bg_color)
        self.plot_item.addItem(self.label)
        self.label.setZValue(10)
        
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)
        self.plot_widget.scene().sigMouseClicked.connect(self.mouse_clicked)
        self.view_box.sigXRangeChanged.connect(self.on_x_range_changed)
        self.view_box.sigYRangeChanged.connect(self.on_y_range_changed)

    def apply_settings(self, config):
        if 'up_color' in config: self.up_color = config['up_color']
        if 'down_color' in config: self.down_color = config['down_color']
        if 'bg_color' in config: self.bg_color = config['bg_color']
        if 'grid_color' in config: self.grid_color = config['grid_color']
        
        self.plot_widget.setBackground(self.bg_color)
        self.label.fill = pg.mkBrush(self.bg_color)
        self.candlestick.set_colors(self.up_color, self.down_color)
        self.plot_item.getAxis('left').setPen(self.grid_color)
        self.plot_item.getAxis('bottom').setPen(self.grid_color)

    def on_y_range_changed(self, vb, yrange):
        if not getattr(self, '_updating_y', False) and vb.autoRangeEnabled()[1] is False:
            vb.y_auto_scale = False

    def on_x_range_changed(self, vb, xrange):
        if self.df is None or self.df.empty: return
        
        min_x, max_x = xrange
        
        # 1. Y-Axis Auto-scaling (TradingView style)
        if vb.y_auto_scale:
            idx_start = max(0, int(min_x))
            idx_end = min(len(self.df)-1, int(max_x))
            if idx_end >= idx_start and idx_end < len(self.df):
                visible_df = self.df.iloc[idx_start:idx_end+1]
                if not visible_df.empty:
                    min_y = visible_df['low'].min()
                    max_y = visible_df['high'].min()
                    max_y = visible_df['high'].max()
                    padding = (max_y - min_y) * 0.1
                    if max_y - min_y > 0:
                        self._updating_y = True
                        vb.setYRange(min_y - padding, max_y + padding, padding=0)
                        self._updating_y = False

        # 2. Adaptive Loading (Infinite Scroll)
        if min_x < 50 and not self.loading_more:
            self.loading_more = True
            self.request_more_data.emit()

    def reset_view(self):
        if self.df is None or self.df.empty: return
        self.view_box.y_auto_scale = True
        total = len(self.df)
        show_candles = min(150, total)
        self.view_box.setXRange(total - show_candles, total, padding=0.05)

    def mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            index = int(round(mouse_point.x()))
            if self.df is not None and 0 <= index < len(self.df):
                row = self.df.iloc[index]
                ts = pd.to_datetime(row['time']).strftime('%Y-%m-%d %H:%M')
                price = mouse_point.y()
                self.v_line.setPos(mouse_point.x())
                self.h_line.setPos(price)
                
                view_rect = self.plot_item.viewRect()
                label_x = mouse_point.x() + (view_rect.width() * 0.02)
                label_y = price + (view_rect.height() * 0.05)
                
                # Check bounds so label doesn't go off screen
                if label_y > view_rect.bottom() - (view_rect.height() * 0.2):
                    label_y = price - (view_rect.height() * 0.05)
                if label_x > view_rect.right() - (view_rect.width() * 0.2):
                    label_x = mouse_point.x() - (view_rect.width() * 0.02)
                    self.label.setAnchor((1, 0))
                else:
                    self.label.setAnchor((0, 1))
                
                self.label.setPos(label_x, label_y)
                self.label.setText(f"Time: {ts}\nPrice: {price:.5f}\nO:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']}")

    def mouse_clicked(self, evt):
        if evt.button() == Qt.MouseButton.LeftButton:
            if evt.double():
                self.reset_view()
                return
            pos = evt.scenePos()
            if self.plot_item.sceneBoundingRect().contains(pos):
                mouse_point = self.plot_item.vb.mapSceneToView(pos)
                index = int(round(mouse_point.x()))
                if self.df is not None and 0 <= index < len(self.df):
                    time_val = self.df.iloc[index]['time']
                    self.chart_clicked.emit(str(time_val))

    def _prepare_data(self, df):
        data = []
        for i, row in enumerate(df.itertuples()):
            data.append((i, row.open, row.close, row.low, row.high))
        return data

    def set_data(self, df: pd.DataFrame, maintain_view_for_added=0):
        self.df = df.copy()
        if self.df.empty:
            self.candlestick.set_data([])
            return
            
        if 'time' not in self.df.columns and self.df.index.name == 'time':
            self.df.reset_index(inplace=True)
        elif 'timestamp' in self.df.columns and 'time' not in self.df.columns:
            self.df['time'] = self.df['timestamp']
            
        data = self._prepare_data(self.df)
        self.time_axis.update_mapping(self.df['time'].values)
        self.candlestick.set_data(data)
        
        # Zoom Limits
        self.view_box.setLimits(xMin=-50, xMax=len(self.df)+50, minXRange=15, maxXRange=10000)
        
        if maintain_view_for_added > 0:
            old_view = self.view_box.viewRange()[0]
            self.view_box.setXRange(old_view[0] + maintain_view_for_added, old_view[1] + maintain_view_for_added, padding=0)
            self.loading_more = False
        else:
            self.reset_view()

    def update_data(self, row_dict):
        if self.df is None or self.df.empty:
            df = pd.DataFrame([row_dict])
            self.set_data(df)
            return
            
        # Check if user's view is at the very right edge (live edge)
        current_x_range = self.view_box.viewRange()[0]
        at_live_edge = current_x_range[1] >= len(self.df) - 2
        len_before = len(self.df)
            
        last_idx = len(self.df) - 1
        last_time = self.df.iloc[last_idx]['time']
        
        if row_dict.get('time') == last_time:
            for col in ['open', 'high', 'low', 'close']:
                if col in row_dict:
                    self.df.at[last_idx, col] = row_dict[col]
        else:
            new_row = pd.DataFrame([row_dict])
            self.df = pd.concat([self.df, new_row], ignore_index=True)
            self.view_box.setLimits(xMin=-50, xMax=len(self.df)+50)
            
        data = self._prepare_data(self.df)
        self.time_axis.update_mapping(self.df['time'].values)
        self.candlestick.set_data(data)
        
        if at_live_edge and len(self.df) > len_before:
            # Shift the view to follow the new candle
            self.view_box.setXRange(current_x_range[0] + 1, current_x_range[1] + 1, padding=0)
            
        # Trigger y-axis auto-scale if enabled, to adjust for the new live candle
        if self.view_box.y_auto_scale:
            self.on_x_range_changed(self.view_box, self.view_box.viewRange()[0])

    def add_marker(self, time_val, position, shape, color, text):
        if self.df is None or self.df.empty: return
        time_matches = self.df[self.df['time'] == time_val]
        if time_matches.empty:
            try:
                ts = pd.to_datetime(time_val)
                self.df['temp_time'] = pd.to_datetime(self.df['time'])
                time_matches = self.df[self.df['temp_time'] == ts]
            except Exception:
                pass
                
        if time_matches.empty: return
        idx = time_matches.index[0]
        row = self.df.iloc[idx]
        
        y_pos = row['low'] if position == 'belowBar' else row['high']
        anchor = (0.5, 0) if position == 'belowBar' else (0.5, 1)
        
        arrow = pg.ArrowItem(pos=(idx, y_pos), angle=90 if position == 'belowBar' else -90, 
                             brush=color, pen=color, headLen=15)
        text_item = pg.TextItem(text, color=color, anchor=anchor)
        text_item.setPos(idx, y_pos + (row['high'] - row['low']) * 0.1 * (1 if position == 'aboveBar' else -1))
        
        self.plot_item.addItem(arrow)
        self.plot_item.addItem(text_item)
        self.markers.extend([arrow, text_item])

    def go_to_time(self, time_val):
        if not self.df.empty and 'time' in self.df.columns:
            import pandas as pd
            try:
                dt = pd.to_datetime(time_val)
                # self.df['time'] is string, so we convert it to datetime for comparison
                df_time = pd.to_datetime(self.df['time'])
                idx_series = self.df[df_time <= dt]
                if not idx_series.empty:
                    x_val = idx_series.index[-1]
                    # Get current visible width
                    view_range = self.plot_item.viewRange()
                    current_width = view_range[0][1] - view_range[0][0]
                    self.plot_item.setXRange(x_val - current_width * 0.2, x_val + current_width * 0.8)
            except Exception as e:
                print(f"Помилка скролінгу до часу: {e}")

    def clear_markers(self):
        for marker in self.markers:
            self.plot_item.removeItem(marker)
        self.markers.clear()
