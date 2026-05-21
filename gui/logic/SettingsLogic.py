import os
import json
from dotenv import set_key, load_dotenv

#==================================
# SettingsLogic
#==================================
class SettingsLogic:
    # ----------------------------------
    # __init__, ініціалізація логіки налаштувань
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.config_path = os.path.join(base_dir, 'data', 'config', 'settings.json')
        self.env_path = os.path.join(base_dir, '.env')
        
        self.default_data = {
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
        
    # ----------------------------------
    # load_settings, завантаження конфігурації
    # ----------------------------------
    # Параметри: немає
    def load_settings(self) -> dict:
        data = self.default_data.copy()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    for section, values in saved_data.items():
                        if section in data:
                            data[section].update(values)
            except Exception as e:
                print(f"Помилка завантаження налаштувань: {e}")
        return data

    # ----------------------------------
    # save_settings, збереження конфігурації
    # ----------------------------------
    # Параметри: 
    # new_data (dict): Нові налаштування для збереження у форматі словника
    def save_settings(self, new_data: dict):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        full_data = self.default_data.copy()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    for k, v in file_data.items():
                        full_data[k] = v
            except Exception:
                pass

        for section, values in new_data.items():
            if section not in full_data:
                full_data[section] = {}
            full_data[section].update(values)

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=4)
        except Exception as e:
            print(f"Не вдалося зберегти налаштування: {e}")

    # ----------------------------------
    # load_api_keys, завантаження API ключів
    # ----------------------------------
    # Параметри: немає
    def load_api_keys(self) -> dict:
        load_dotenv(self.env_path)
        return {
            "BYBIT_KEY": os.getenv("BYBIT_KEY", ""),
            "BYBIT_SECRET_KEY": os.getenv("BYBIT_SECRET_KEY", ""),
            "BINANCE_KEY": os.getenv("BINANCE_KEY", ""),
            "BINANCE_SECRET_KEY": os.getenv("BINANCE_SECRET_KEY", ""),
            "MASSIVE_KEY": os.getenv("MASSIVE_KEY", "")
        }

    # ----------------------------------
    # save_api_keys, збереження API ключів
    # ----------------------------------
    # Параметри: 
    # keys (dict): Словник з ключами та їх значеннями для збереження
    def save_api_keys(self, keys: dict):
        if not os.path.exists(self.env_path):
            open(self.env_path, 'w').close()
            
        for key, value in keys.items():
            set_key(self.env_path, key, value)
