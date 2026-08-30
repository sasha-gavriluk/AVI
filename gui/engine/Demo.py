import sys
from utils.OtherUtils import _handle_error
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PyQt6.QtWidgets import QApplication
from gui.engine import Engine as engine

#------------------------------
# Демо запуску движка: будує вікно з gui/visual/main.json і показує його.
# Запуск:  venv/bin/python gui/engine/demo.py
#------------------------------

@_handle_error
def main():

    app = QApplication(sys.argv)

    base = os.path.join(os.path.dirname(__file__), '..', 'visual')

    # приклад прив'язки події (як це робитиме місток)
    engine.bind('explorer.refresh', lambda: print('[demo] Натиснуто "Оновити"'))

    root = engine.build(
        os.path.join(base, 'main.json'),
        styles_path=os.path.join(base, 'styles.json'),
    )

    root.resize(600, 400)
    root.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
