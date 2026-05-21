import os
import json
from dotenv import set_key, load_dotenv
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QFormLayout, QGroupBox, 
                             QMessageBox, QSpinBox, QDoubleSpinBox, QComboBox)
from PyQt6.QtCore import Qt

class SettingsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'config', 'settings.json'))
        self.settings_data = {
            "trading_mode": {
                "type": "Standard",
                "bo_payout_percent": 80.0,
                "bo_bet_size": 10.0,
                "bo_expiration_bars": 1
            },
            "risk_management": {
                "stop_loss_percent": 1.5,
                "max_drawdown_session": 5.0,
                "daily_loss_limit": 100.0
            },
            "copilot": {
                "half_life_days": 90,
                "min_score_for_best": 0.6,
                "routine_interval_hours": 1.0
            }
        }
        self.env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
        load_dotenv(self.env_path)
        self._load_settings()
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("⚙️ Налаштування Платформи")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F9E2AF; margin-bottom: 10px;")
        main_layout.addWidget(title)

        trading_mode_group = QGroupBox("Режим Торгівлі (Бектест)")
        trading_mode_layout = QFormLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Standard", "Binary Options"])
        self.mode_combo.setCurrentText(self.settings_data["trading_mode"].get("type", "Standard"))
        
        self.bo_payout_input = QDoubleSpinBox()
        self.bo_payout_input.setRange(1.0, 100.0)
        self.bo_payout_input.setSingleStep(1.0)
        self.bo_payout_input.setSuffix(" %")
        self.bo_payout_input.setValue(self.settings_data["trading_mode"]["bo_payout_percent"])
        
        self.bo_bet_input = QDoubleSpinBox()
        self.bo_bet_input.setRange(1.0, 100000.0)
        self.bo_bet_input.setPrefix("$ ")
        self.bo_bet_input.setValue(self.settings_data["trading_mode"]["bo_bet_size"])
        
        self.bo_exp_input = QSpinBox()
        self.bo_exp_input.setRange(1, 1000)
        self.bo_exp_input.setSuffix(" барів")
        self.bo_exp_input.setValue(self.settings_data["trading_mode"]["bo_expiration_bars"])
        
        trading_mode_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        trading_mode_layout.addRow("Тип ринку:", self.mode_combo)
        trading_mode_layout.addRow("БО - Виплата (Payout):", self.bo_payout_input)
        trading_mode_layout.addRow("БО - Розмір ставки:", self.bo_bet_input)
        trading_mode_layout.addRow("БО - Експірація (барів):", self.bo_exp_input)
        trading_mode_group.setLayout(trading_mode_layout)
        main_layout.addWidget(trading_mode_group)
        
        # 1. Risk Management
        risk_group = QGroupBox("Ризик Менеджмент (Live Trading)")
        risk_layout = QFormLayout()
        
        self.stop_loss_input = QDoubleSpinBox()
        self.stop_loss_input.setRange(0.1, 100.0)
        self.stop_loss_input.setSingleStep(0.1)
        self.stop_loss_input.setSuffix(" %")
        self.stop_loss_input.setValue(self.settings_data["risk_management"]["stop_loss_percent"])
        
        self.max_drawdown_input = QDoubleSpinBox()
        self.max_drawdown_input.setRange(0.1, 100.0)
        self.max_drawdown_input.setSingleStep(0.5)
        self.max_drawdown_input.setSuffix(" %")
        self.max_drawdown_input.setValue(self.settings_data["risk_management"]["max_drawdown_session"])
        
        self.daily_loss_input = QDoubleSpinBox()
        self.daily_loss_input.setRange(0.0, 100000.0)
        self.daily_loss_input.setPrefix("$ ")
        self.daily_loss_input.setValue(self.settings_data["risk_management"]["daily_loss_limit"])
        
        risk_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        risk_layout.addRow("Стоп-лосс на угоду:", self.stop_loss_input)
        risk_layout.addRow("Макс. просадка за сесію:", self.max_drawdown_input)
        risk_layout.addRow("Денний ліміт втрат:", self.daily_loss_input)
        risk_group.setLayout(risk_layout)
        main_layout.addWidget(risk_group)
        
        # 2. Copilot Settings
        copilot_group = QGroupBox("Налаштування Копілота")
        copilot_layout = QFormLayout()
        
        self.half_life_input = QSpinBox()
        self.half_life_input.setRange(1, 365)
        self.half_life_input.setSuffix(" днів")
        self.half_life_input.setValue(self.settings_data["copilot"]["half_life_days"])
        
        self.min_score_input = QDoubleSpinBox()
        self.min_score_input.setRange(0.1, 1.0)
        self.min_score_input.setSingleStep(0.05)
        self.min_score_input.setValue(self.settings_data["copilot"]["min_score_for_best"])
        
        self.routine_interval_input = QDoubleSpinBox()
        self.routine_interval_input.setRange(0.1, 24.0)
        self.routine_interval_input.setSingleStep(0.5)
        self.routine_interval_input.setSuffix(" год")
        self.routine_interval_input.setValue(self.settings_data["copilot"].get("routine_interval_hours", 1.0))
        
        copilot_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        copilot_layout.addRow("Період напіврозпаду пам'яті (decay):", self.half_life_input)
        copilot_layout.addRow("Мін. score для успішної стратегії:", self.min_score_input)
        copilot_layout.addRow("Інтервал автоматичного циклу:", self.routine_interval_input)
        copilot_group.setLayout(copilot_layout)
        main_layout.addWidget(copilot_group)
        
        # 3. API Keys
        api_group = QGroupBox("🔑 API Ключі (Біржі та Дані)")
        api_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        api_layout = QFormLayout()
        
        self.bybit_key_input = QLineEdit(os.getenv("BYBIT_KEY", ""))
        self.bybit_key_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.bybit_key_input.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244; padding: 5px;")
        
        self.bybit_secret_input = QLineEdit(os.getenv("BYBIT_SECRET_KEY", ""))
        self.bybit_secret_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.bybit_secret_input.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244; padding: 5px;")
        
        self.binance_key_input = QLineEdit(os.getenv("BINANCE_KEY", ""))
        self.binance_key_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.binance_key_input.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244; padding: 5px;")
        
        self.binance_secret_input = QLineEdit(os.getenv("BINANCE_SECRET_KEY", ""))
        self.binance_secret_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.binance_secret_input.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244; padding: 5px;")
        
        self.massive_key_input = QLineEdit(os.getenv("MASSIVE_KEY", ""))
        self.massive_key_input.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.massive_key_input.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244; padding: 5px;")
        
        api_layout.addRow("Bybit API Key:", self.bybit_key_input)
        api_layout.addRow("Bybit Secret:", self.bybit_secret_input)
        api_layout.addRow("Binance API Key:", self.binance_key_input)
        api_layout.addRow("Binance Secret:", self.binance_secret_input)
        api_layout.addRow("Massive API Key:", self.massive_key_input)
        api_group.setLayout(api_layout)
        main_layout.addWidget(api_group)
        
        # Автозбереження (підключаємо сигнали)
        self.mode_combo.currentTextChanged.connect(self.save_settings)
        self.bo_payout_input.valueChanged.connect(self.save_settings)
        self.bo_bet_input.valueChanged.connect(self.save_settings)
        self.bo_exp_input.valueChanged.connect(self.save_settings)
        
        self.stop_loss_input.valueChanged.connect(self.save_settings)
        self.max_drawdown_input.valueChanged.connect(self.save_settings)
        self.daily_loss_input.valueChanged.connect(self.save_settings)
        
        self.half_life_input.valueChanged.connect(self.save_settings)
        self.min_score_input.valueChanged.connect(self.save_settings)
        self.routine_interval_input.valueChanged.connect(self.save_settings)
        
        self.bybit_key_input.textChanged.connect(self.save_settings)
        self.bybit_secret_input.textChanged.connect(self.save_settings)
        self.binance_key_input.textChanged.connect(self.save_settings)
        self.binance_secret_input.textChanged.connect(self.save_settings)
        self.massive_key_input.textChanged.connect(self.save_settings)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
        
    def _load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Merge recursively
                    for section, values in data.items():
                        if section in self.settings_data:
                            self.settings_data[section].update(values)
            except Exception as e:
                print(f"Помилка завантаження налаштувань: {e}")
                
    def save_settings(self):

        self.settings_data["trading_mode"]["type"] = self.mode_combo.currentText()
        self.settings_data["trading_mode"]["bo_payout_percent"] = self.bo_payout_input.value()
        self.settings_data["trading_mode"]["bo_bet_size"] = self.bo_bet_input.value()
        self.settings_data["trading_mode"]["bo_expiration_bars"] = self.bo_exp_input.value()

        self.settings_data["risk_management"]["stop_loss_percent"] = self.stop_loss_input.value()
        self.settings_data["risk_management"]["max_drawdown_session"] = self.max_drawdown_input.value()
        self.settings_data["risk_management"]["daily_loss_limit"] = self.daily_loss_input.value()
        
        self.settings_data["copilot"]["half_life_days"] = self.half_life_input.value()
        self.settings_data["copilot"]["min_score_for_best"] = self.min_score_input.value()
        self.settings_data["copilot"]["routine_interval_hours"] = self.routine_interval_input.value()
        
        if not os.path.exists(self.env_path):
            open(self.env_path, 'w').close()
            
        set_key(self.env_path, "BYBIT_KEY", self.bybit_key_input.text())
        set_key(self.env_path, "BYBIT_SECRET_KEY", self.bybit_secret_input.text())
        set_key(self.env_path, "BINANCE_KEY", self.binance_key_input.text())
        set_key(self.env_path, "BINANCE_SECRET_KEY", self.binance_secret_input.text())
        set_key(self.env_path, "MASSIVE_KEY", self.massive_key_input.text())
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        full_data = self.settings_data.copy()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    for k, v in file_data.items():
                        if k not in full_data:
                            full_data[k] = v
            except Exception:
                pass

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=4)
        except Exception as e:
            print(f"Не вдалося зберегти налаштування:\n{e}")
