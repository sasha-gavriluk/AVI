import os
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env, який знаходиться в корені проєкту
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

bybit_key = os.getenv("BYBIT_KEY")
bybit_secret_key = os.getenv("BYBIT_SECRET_KEY")
massive_key = os.getenv("MASSIVE_KEY")

root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_dir = os.path.join(root_path, "data", "db")
gui_dir = os.path.join(root_path, "gui")
path_to_json_predictions_dir = os.path.join(root_path, "data", "predictions")

def ensure_predictions_dir_exists():
    if not os.path.exists(path_to_json_predictions_dir):
        os.makedirs(path_to_json_predictions_dir, exist_ok=True)

    return path_to_json_predictions_dir