from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox
from gui.visual.UiElements import TitleLabel, StyledGroupBox, PasswordLineEdit

#==================================
# TabSettingsVisual
#==================================
class TabSettingsVisual(QWidget):
    # ----------------------------------
    # __init__, ініціалізація вкладки налаштувань
    # ----------------------------------
    # Параметри:
    # parent (QWidget): Батьківський віджет (за замовчуванням None)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    # ----------------------------------
    # init_ui, побудова візуальних елементів
    # ----------------------------------
    # Параметри: немає
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.addWidget(TitleLabel("⚙️ Налаштування Платформи"))

        # 1. Trading Mode Group
        trading_mode_group = StyledGroupBox("Режим Торгівлі (Бектест)")
        trading_mode_layout = QFormLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Standard", "Binary Options"])
        
        self.bo_payout_input = QDoubleSpinBox()
        self.bo_payout_input.setRange(1.0, 100.0)
        self.bo_payout_input.setSingleStep(1.0)
        self.bo_payout_input.setSuffix(" %")
        
        self.bo_bet_input = QDoubleSpinBox()
        self.bo_bet_input.setRange(1.0, 100000.0)
        self.bo_bet_input.setPrefix("$ ")
        
        self.bo_exp_input = QSpinBox()
        self.bo_exp_input.setRange(1, 1000)
        self.bo_exp_input.setSuffix(" барів")
        
        trading_mode_layout.addRow("Тип ринку:", self.mode_combo)
        trading_mode_layout.addRow("БО - Виплата (Payout):", self.bo_payout_input)
        trading_mode_layout.addRow("БО - Розмір ставки:", self.bo_bet_input)
        trading_mode_layout.addRow("БО - Експірація (барів):", self.bo_exp_input)
        trading_mode_group.setLayout(trading_mode_layout)
        main_layout.addWidget(trading_mode_group)
        
        # 2. Risk Management Group
        risk_group = StyledGroupBox("Ризик Менеджмент (Live Trading)")
        risk_layout = QFormLayout()
        
        self.stop_loss_input = QDoubleSpinBox()
        self.stop_loss_input.setRange(0.1, 100.0)
        self.stop_loss_input.setSingleStep(0.1)
        self.stop_loss_input.setSuffix(" %")
        
        self.max_drawdown_input = QDoubleSpinBox()
        self.max_drawdown_input.setRange(0.1, 100.0)
        self.max_drawdown_input.setSingleStep(0.5)
        self.max_drawdown_input.setSuffix(" %")
        
        self.daily_loss_input = QDoubleSpinBox()
        self.daily_loss_input.setRange(0.0, 100000.0)
        self.daily_loss_input.setPrefix("$ ")
        
        risk_layout.addRow("Стоп-лосс на угоду:", self.stop_loss_input)
        risk_layout.addRow("Макс. просадка за сесію:", self.max_drawdown_input)
        risk_layout.addRow("Денний ліміт втрат:", self.daily_loss_input)
        risk_group.setLayout(risk_layout)
        main_layout.addWidget(risk_group)
        
        # 3. Copilot Settings Group
        copilot_group = StyledGroupBox("Налаштування Копілота")
        copilot_layout = QFormLayout()
        
        self.half_life_input = QSpinBox()
        self.half_life_input.setRange(1, 365)
        self.half_life_input.setSuffix(" днів")
        
        self.min_score_input = QDoubleSpinBox()
        self.min_score_input.setRange(0.1, 1.0)
        self.min_score_input.setSingleStep(0.05)
        
        self.routine_interval_input = QDoubleSpinBox()
        self.routine_interval_input.setRange(0.1, 24.0)
        self.routine_interval_input.setSingleStep(0.5)
        self.routine_interval_input.setSuffix(" год")
        
        copilot_layout.addRow("Період напіврозпаду пам'яті (decay):", self.half_life_input)
        copilot_layout.addRow("Мін. score для успішної стратегії:", self.min_score_input)
        copilot_layout.addRow("Інтервал автоматичного циклу:", self.routine_interval_input)
        copilot_group.setLayout(copilot_layout)
        main_layout.addWidget(copilot_group)
        
        # 4. API Keys Group
        api_group = StyledGroupBox("🔑 API Ключі (Біржі та Дані)")
        api_layout = QFormLayout()
        
        self.bybit_key_input = PasswordLineEdit()
        self.bybit_secret_input = PasswordLineEdit()
        self.binance_key_input = PasswordLineEdit()
        self.binance_secret_input = PasswordLineEdit()
        self.massive_key_input = PasswordLineEdit()
        
        api_layout.addRow("Bybit API Key:", self.bybit_key_input)
        api_layout.addRow("Bybit Secret:", self.bybit_secret_input)
        api_layout.addRow("Binance API Key:", self.binance_key_input)
        api_layout.addRow("Binance Secret:", self.binance_secret_input)
        api_layout.addRow("Massive API Key:", self.massive_key_input)
        api_group.setLayout(api_layout)
        main_layout.addWidget(api_group)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
