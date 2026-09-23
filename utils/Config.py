import os
import shutil
from dotenv import load_dotenv

from utils.PathManager import PathManager
from utils.OtherUtils import _handle_error

#------------------------------
# Завантаження змінних середовища
#------------------------------

load_dotenv(PathManager.get_env_path())

bybit_key = os.getenv("BYBIT_KEY")
bybit_secret_key = os.getenv("BYBIT_SECRET_KEY")
massive_key = os.getenv("MASSIVE_KEY")

#==============================
# Правка ключів із інтерфейсу
#==============================
#
# Ключі лежать в ОДНОМУ екземплярі й іншої копії немає. Тому запис зроблено
# так, щоб файл не можна було зіпсувати навіть випадково:
#
#   1. читаємо всі рядки й міняємо ТІЛЬКИ потрібні — MASSIVE_KEY,
#      TELEGRAM_* і решта лишаються недоторканими;
#   2. перед першим записом кладемо поруч .env.backup;
#   3. пишемо в тимчасовий файл і аж тоді підміняємо — обрив живлення
#      посеред запису лишить старий файл цілим, а не порожній.
#
# Порожнє значення НЕ записується: якщо поле в інтерфейсі лишили порожнім,
# це «не чіпати», а не «стерти ключ».
#==============================


@_handle_error
def _read_env_lines() -> list:
    "Рядки .env як вони є. Немає файлу — порожній список"
    path = PathManager.get_env_path()
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().splitlines()


@_handle_error
def _write_env_values(values: dict) -> bool:
    """
    Переписує лише названі ключі, решту рядків лишає як були.

    :param values: {'BYBIT_KEY': '...'} — порожні значення пропускаються
    :return: True, якщо файл змінено
    """
    values = {k: v for k, v in (values or {}).items() if v}
    if not values:
        return False

    path = PathManager.get_env_path()

    # Копія до першої ж правки. Робиться один раз і більше не чіпається,
    # щоб друге збереження не затерло резерв уже новими ключами
    backup = path + '.backup'
    if os.path.exists(path) and not os.path.exists(backup):
        shutil.copy2(path, backup)

    lines = _read_env_lines()
    written = set()

    for i, line in enumerate(lines):
        name = line.split('=', 1)[0].strip()
        if name in values:
            lines[i] = f"{name}='{values[name]}'"
            written.add(name)

    for name, value in values.items():
        if name not in written:
            lines.append(f"{name}='{value}'")

    # Спершу тимчасовий файл, потім підміна — щоб не лишитись без ключів
    temp = path + '.tmp'
    with open(temp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    os.replace(temp, path)

    reload()
    return True


@_handle_error
def save_bybit_keys(key: str, secret: str) -> bool:
    """
    Зберігає ключі Bybit і одразу підхоплює їх у пам'ять.

    :return: True, якщо щось справді записано
    """
    return _write_env_values({
        'BYBIT_KEY': (key or '').strip(),
        'BYBIT_SECRET_KEY': (secret or '').strip(),
    })


@_handle_error
def reload() -> None:
    "Перечитує .env у змінні модуля. Потрібно після правки ключів з інтерфейсу"
    global bybit_key, bybit_secret_key, massive_key

    load_dotenv(PathManager.get_env_path(), override=True)
    bybit_key = os.getenv("BYBIT_KEY")
    bybit_secret_key = os.getenv("BYBIT_SECRET_KEY")
    massive_key = os.getenv("MASSIVE_KEY")


@_handle_error
def has_bybit_keys() -> bool:
    "Чи є що показувати біржі. Інтерфейс питає це перед стартом"
    return bool(bybit_key and bybit_secret_key)

#------------------------------
# Шляхи до системних директорій
#------------------------------

root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_dir = PathManager.get_user_data_dir()
gui_dir = os.path.join(root_path, "gui")
path_to_json_predictions_dir = os.path.join(PathManager.get_user_data_dir(), "data", "predictions")

#------------------------------
# Допоміжні функції
#------------------------------

@_handle_error
def ensure_predictions_dir_exists():
    "Перевіряє та створює директорію для прогнозів за потреби"
    if not os.path.exists(path_to_json_predictions_dir):
        os.makedirs(path_to_json_predictions_dir, exist_ok=True)

    return path_to_json_predictions_dir