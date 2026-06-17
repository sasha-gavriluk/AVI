import os
import requests
from dotenv import load_dotenv

class TelegramNotifier:
    def __init__(self):
        # Determine paths
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.env_path = os.path.join(self.base_dir, '.env')
        
    def send_message(self, message: str, silent: bool = False) -> bool:
        load_dotenv(self.env_path, override=True)
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        if not token or not chat_id:
            print("Telegram сповіщення не надіслано: відсутній токен або chat ID.")
            return False
            
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        if silent:
            data["disable_notification"] = True
        
        try:
            response = requests.post(url, data=data, timeout=5)
            if response.status_code != 200:
                print(f"Telegram API помилка: {response.text}")
            return response.status_code == 200
        except Exception as e:
            print(f"Помилка відправки Telegram сповіщення: {e}")
            return False
