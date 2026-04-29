import sys
import os

# Додаємо корінь проекту в PYTHONPATH, щоб імпорти працювали
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication
from gui.duckdb_explorer.views.main_window import DuckDBExplorerWindow

def load_stylesheet(app):
    """Завантажує файл стилів QSS"""
    qss_path = os.path.join(os.path.dirname(__file__), 'gui', 'duckdb_explorer', 'styles', 'main_theme.qss')
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
    test_db_name = "trading_data_massive.duckdb"
    
    window = DuckDBExplorerWindow(default_db_path=test_db_name)
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
