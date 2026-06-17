import sys
import os

# Обхід блокування в бібліотеці finplot для певних локалей (російська/українська)
os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"

import locale
# Жорстка підміна (monkey-patch) функції для Windows, де os.environ ігнорується модулем locale
locale.getdefaultlocale = lambda *args, **kwargs: ('en_US', 'UTF-8')

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
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)
    
    app = QApplication(sys.argv)
    
    # Примусово встановлюємо стиль "Fusion", щоб зміни теми ОС (світла/темна) не ламали наші кольори
    app.setStyle("Fusion")
    
    # Жорстко фіксуємо темну палітру, оскільки деякі Linux-дистрибутиви 
    # та Windows примусово перезаписують кольори навіть з Fusion
    from PyQt6.QtGui import QPalette, QColor
    
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor("#1E1E2E"))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor("#CDD6F4"))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor("#181825"))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1E1E2E"))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#313244"))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#CDD6F4"))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor("#CDD6F4"))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor("#313244"))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor("#CDD6F4"))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor("#F38BA8"))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor("#89B4FA"))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor("#89B4FA"))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#11111B"))
    app.setPalette(dark_palette)
    
    # Застосовуємо стилізацію
    load_stylesheet(app)
    
    from utils.PathManager import PathManager
    
    # Назва вашої бази даних (DataBaseManager сам знайде її)
    test_db_name = PathManager.get_db_path()
    
    window = MainAppWindow(default_db_path=test_db_name)
    window.show()
    
    # Запускаємо внутрішні таймери finplot
    fplt.show(qt_exec=False)
    
    sys.exit(app.exec())

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()


# РОЗШИФРОВКА СЛОВА AVI: Adaptive Vector Investment
# ============================================================

# Adaptive - Адаптивні, тому що система адаптується до ринкових умов.
# Vector - Векторні, тому що ми використовуємо багатофакторний аналіз.
# Investment - Інвестиції, тому що ми інвестуємо в майбутнє.

# ============================================================
