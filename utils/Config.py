import os
from dotenv import load_dotenv

# Завантажуємо змінні з файлу .env
from utils.PathManager import PathManager
load_dotenv(os.path.join(PathManager.get_user_data_dir(), '.env'))

bybit_key = os.getenv("BYBIT_KEY")
bybit_secret_key = os.getenv("BYBIT_SECRET_KEY")
massive_key = os.getenv("MASSIVE_KEY")

root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from utils.PathManager import PathManager
db_dir = PathManager.get_user_data_dir()
gui_dir = os.path.join(root_path, "gui")
path_to_json_predictions_dir = os.path.join(PathManager.get_user_data_dir(), "data", "predictions")

def ensure_predictions_dir_exists():
    if not os.path.exists(path_to_json_predictions_dir):
        os.makedirs(path_to_json_predictions_dir, exist_ok=True)

    return path_to_json_predictions_dir