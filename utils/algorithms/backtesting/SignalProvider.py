import pandas as pd
from utils.OtherUtils import _handle_error

#------------------------------
# Модуль Аналізатора (Signal Provider)
#------------------------------

class Analyzer:
    "Простий аналізатор для генерації сигналів під час бектестування"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, window_size: int = 1):
        "Ініціалізує аналізатор із заданим розміром вікна (window_size)"
        self.window_size = window_size

    #------------------------------
    # Метод генерації сигналів
    #------------------------------

    @_handle_error
    def check_signal(self, window: pd.DataFrame) -> str:
        "Отримує зріз даних і повертає стандартизований сигнал (BUY/SELL/CLOSE/None)"
        # На даному етапі — це «болванка» (шаблон).
        return None
