import sys
import os

from PyQt6.QtWidgets import QApplication
from gui.engine import engine
from gui.logic.main_logic import AppLogic

# Додаємо корінь проекту в PYTHONPATH, щоб імпорти працювали
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

#==================================
# main, точка входу
#==================================
# UI переписується з нуля (графіка / движок графіки / логіка в папці gui).
# Старий запуск (QApplication, MainAppWindow, finplot) видалено —
# історія в git-коміті 3a53209.

def main():
    app = QApplication(sys.argv)
    
    # Використовуємо стиль Fusion, щоб ОС (Linux/Windows) не перебивала кольори
    app.setStyle('Fusion')

    # Ініціалізуємо логіку (вона прив'яже свої методи до подій engine)
    app_logic = AppLogic()

    base = os.path.join(os.path.dirname(__file__), 'gui', 'visual')
    
    # Завантажуємо преміальну глобальну тему
    theme_path = os.path.join(base, 'theme.qss')
    if os.path.exists(theme_path):
        with open(theme_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())

    root = engine.build(
        os.path.join(base, 'main.json'),
        styles_path=os.path.join(base, 'styles.json'),
    )
    
    # Ініціалізуємо стан UI (заповнюємо комбобокси)
    app_logic.init_ui()

    root.resize(600, 400)
    root.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()


# РОЗШИФРОВКА СЛОВА AVI: Adaptive Vector Investment
# ============================================================

# Adaptive - Адаптивні, тому що система адаптується до ринкових умов.
# Vector - Векторні, тому що ми використовуємо багатофакторний аналіз.
# Investment - Інвестиції, тому що ми інвестуємо в майбутнє.

# ============================================================
