import sys
import os

# Обхід блокування в бібліотеці finplot для певних локалей (російська/українська)
os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"

# Додаємо корінь проекту в PYTHONPATH, щоб імпорти працювали
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication
from gui.MainWindow import MainAppWindow
import finplot as fplt

def load_stylesheet(app):
    """Завантажує файл стилів QSS"""
    qss_path = os.path.join(os.path.dirname(__file__), 'gui', 'styles', 'main_theme.qss')
    if os.path.exists(qss_path):
        with open(qss_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Попередження: Файл стилів {qss_path} не знайдено.")

def main():
    app = QApplication(sys.argv)
    
    # Застосовуємо стилізацію
    load_stylesheet(app)
    
    # Назва вашої бази даних (DataBaseManager сам знайде її в data/db)
    test_db_name = "main.duckdb"
    
    window = MainAppWindow(default_db_path=test_db_name)
    window.show()
    
    # Запускаємо внутрішні таймери finplot
    fplt.show(qt_exec=False)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
