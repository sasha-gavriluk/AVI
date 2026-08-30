#------------------------------
# Базовий клас конфігурації
#------------------------------

class BaseSettings:
    "Зберігає налаштування для запуску бектестів (комісії, спреди, бази даних)"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, 
                 look_ahead: bool = False,
                 commission: float = 0.0,
                 spread: float = 0.0,
                 initial_balance: float = 10000.0,
                 db_table_path: str = None,
                 close_on_next_candle: bool = False):
        "Ініціалізує параметри симуляції ринку"
        self.look_ahead = look_ahead
        self.commission = commission
        self.spread = spread
        self.initial_balance = initial_balance
        self.db_table_path = db_table_path
        self.close_on_next_candle = close_on_next_candle
