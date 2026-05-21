from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTextEdit, QLabel, QGroupBox, QSplitter, QRadioButton, 
                             QComboBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt

from core.services.trading_service import TradingService

class LiveTradingView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.trading_service = TradingService()
        self.trading_service.log_update.connect(self.append_log)
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- HEADER ---
        header_layout = QHBoxLayout()
        title = QLabel("📡 LIVE TRADING CENTER")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F9E2AF;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # --- SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ==========================================
        # LEFT PANEL
        # ==========================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # 1. Mode
        mode_group = QGroupBox("⚙️ РЕЖИМ")
        mode_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        mode_layout = QVBoxLayout(mode_group)
        
        self.rb_demo = QRadioButton("Demo (Симуляція)")
        self.rb_paper = QRadioButton("Paper (Паперова)")
        self.rb_real = QRadioButton("Real (CCXT)")
        self.rb_signal = QRadioButton("Signal (Massive)")
        
        self.rb_paper.setChecked(True)
        
        for rb in [self.rb_demo, self.rb_paper, self.rb_real, self.rb_signal]:
            rb.setStyleSheet("color: #CDD6F4;")
            mode_layout.addWidget(rb)
            
        left_layout.addWidget(mode_group)
        
        # 2. Strategy Setup
        strat_group = QGroupBox("📋 СТРАТЕГІЯ")
        strat_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        strat_layout = QVBoxLayout(strat_group)
        
        self.combo_strat = QComboBox()
        self.combo_strat.addItems(["[Обрати...]", "TrendFollowing_v1", "MeanReversion_AI"])
        strat_layout.addWidget(self.combo_strat)
        
        strat_layout.addWidget(QLabel("Актив: EURUSD ▼"))
        strat_layout.addWidget(QLabel("Таймфрейм: 15m ▼"))
        
        left_layout.addWidget(strat_group)
        
        # 3. Controls
        self.btn_start = QPushButton("▶ ЗАПУСТИТИ")
        self.btn_start.setStyleSheet("padding: 10px; background-color: #A6E3A1; color: #11111B; font-weight: bold;")
        self.btn_start.clicked.connect(self.start_trading)
        left_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("■ ЗУПИНИТИ")
        self.btn_stop.setStyleSheet("padding: 10px; background-color: #F38BA8; color: #11111B; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_trading)
        self.btn_stop.setEnabled(False)
        left_layout.addWidget(self.btn_stop)
        
        left_layout.addStretch()
        
        # ==========================================
        # RIGHT PANEL
        # ==========================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # 4. Open Positions
        pos_group = QGroupBox("📊 ВІДКРИТІ ПОЗИЦІЇ")
        pos_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        pos_layout = QVBoxLayout(pos_group)
        
        pos_list = QListWidget()
        pos_list.setStyleSheet("background: transparent; border: none; color: #CDD6F4; font-family: monospace;")
        pos_list.addItem("EURUSD  BUY   1.08521  +22пп  ✅ [✗]")
        pos_list.addItem("BTC/USDT SELL 67500.0  -5пп   ❌ [✗]")
        pos_layout.addWidget(pos_list)
        right_layout.addWidget(pos_group)
        
        # 5. Stats
        stats_group = QGroupBox("📈 СТАТИСТИКА СЕСІЇ")
        stats_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        stats_layout = QVBoxLayout(stats_group)
        
        stats_layout.addWidget(QLabel("Відкрито угод: 2"))
        stats_layout.addWidget(QLabel("Профіт: <span style='color:#A6E3A1'>+17.0 пп</span>"))
        stats_layout.addWidget(QLabel("Баланс: $10,170.00"))
        stats_layout.addWidget(QLabel("Max Drawdown: <span style='color:#F38BA8'>-2.3%</span>"))
        right_layout.addWidget(stats_group)
        
        # 6. Log
        log_group = QGroupBox("📜 ЛОГ")
        log_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        log_layout = QVBoxLayout(log_group)
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("background-color: #11111B; color: #CDD6F4; font-family: 'Consolas'; border: none;")
        self.log_console.append("[00:00:00] Live Trading ініціалізовано.")
        log_layout.addWidget(self.log_console)
        right_layout.addWidget(log_group)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 650])
        main_layout.addWidget(splitter)
        
    def start_trading(self):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        if self.rb_demo.isChecked(): mode = "demo"
        elif self.rb_paper.isChecked(): mode = "paper"
        elif self.rb_real.isChecked(): mode = "real"
        else: mode = "signal"
            
        self.trading_service.set_mode(mode)
        self.trading_service.start()
        
    def stop_trading(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.trading_service.stop()

    def append_log(self, text):
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_console.append(f"[{now}] {text}")
