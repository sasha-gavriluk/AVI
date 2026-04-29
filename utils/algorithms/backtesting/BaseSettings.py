#==================================
# Базовий клас конфігурації
#==================================

class BaseSettings:

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, 
                 look_ahead: bool = False,
                 commission: float = 0.0,
                 spread: float = 0.0,
                 initial_balance: float = 10000.0,
                 db_table_path: str = None,
                 close_on_next_candle: bool = False):
        """
        Параметри:
        look_ahead: чи бачить алгоритм майбутні свічки
        commission: комісія за угоду
        spread: розмір спреду
        initial_balance: початковий баланс для бэктесту
        db_table_path: назва таблиці/шлях до даних у DuckDB
        close_on_next_candle: автоматично закривати угоду перед обробкою наступної свічки
        """
        
        self.look_ahead = look_ahead
        self.commission = commission
        self.spread = spread
        self.initial_balance = initial_balance
        self.db_table_path = db_table_path
        self.close_on_next_candle = close_on_next_candle
