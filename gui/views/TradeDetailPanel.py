from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QGroupBox
from PyQt6.QtCore import Qt
import pandas as pd

class TradeDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        group = QGroupBox("Деталі Угоди")
        group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                color: #A6ADC8;
                font-weight: bold;
                padding-top: 10px;
            }
        """)
        vbox = QVBoxLayout(group)
        
        self.lbl_id = QLabel("ID: -")
        self.lbl_dir = QLabel("Напрям: -")
        self.lbl_profit = QLabel("Прибуток: -")
        self.lbl_profit.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_duration = QLabel("Тривалість: -")
        
        vbox.addWidget(self.lbl_id)
        vbox.addWidget(self.lbl_dir)
        vbox.addWidget(self.lbl_profit)
        vbox.addWidget(self.lbl_duration)
        
        vbox.addWidget(QLabel("Лог (Сигнали):"))
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244;")
        vbox.addWidget(self.txt_log)
        
        layout.addWidget(group)
        
    def show_trade(self, trade_series: pd.Series):
        try:
            self.lbl_id.setText(f"ID: {trade_series.get('TradeID', '-')}")
            direction = trade_series.get('Direction', '-')
            self.lbl_dir.setText(f"Напрям: {direction}")
            
            profit = float(trade_series.get('Profit', 0))
            color = "#A6E3A1" if profit > 0 else "#F38BA8"
            self.lbl_profit.setText(f"Прибуток: {profit:.2f}")
            self.lbl_profit.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
            
            start_ts = trade_series.get('EntryTimestamp', 0)
            end_ts = trade_series.get('ExitTimestamp', 0)
            if start_ts and end_ts:
                dur_ms = end_ts - start_ts
                dur_m = int(dur_ms / 60000)
                self.lbl_duration.setText(f"Тривалість: {dur_m} хв")
            
            log_data = trade_series.get('Log', '')
            self.txt_log.setText(str(log_data))
        except Exception as e:
            self.txt_log.setText(f"Помилка відображення: {e}")
            
    def clear(self):
        self.lbl_id.setText("ID: -")
        self.lbl_dir.setText("Напрям: -")
        self.lbl_profit.setText("Прибуток: -")
        self.lbl_profit.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_duration.setText("Тривалість: -")
        self.txt_log.clear()
