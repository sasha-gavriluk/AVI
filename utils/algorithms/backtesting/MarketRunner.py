import pandas as pd

from utils.algorithms.backtesting.BaseSettings import BaseSettings
from utils.DataBaseManager import DataBaseManager
from utils.LaboratoryBacktesterDealWriter import LaboratoryBacktesterDealWriter
from utils.rules_engine import Strategy, IndicatorRegistry

#==================================
# Двигун Ринку (Market Runner)
#==================================

class MarketRunner(BaseSettings):

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, 
                 strategy,
                 db_path: str = 'main.db',
                 look_ahead: bool = False,
                 commission: float = 0.0,
                 spread: float = 0.0,
                 initial_balance: float = 10000.0,
                 db_table_path: str = None,
                 close_on_next_candle: bool = False,
                 trade_direction: str = 'BUY'):
        """
        Параметри: 
        strategy: екземпляр класу Strategy (з rules_engine)
        db_path: шлях до файлу бази даних DuckDB
        close_on_next_candle: автоматично закривати позицію перед наступною свічкою
        trade_direction: 'BUY' або 'SELL' - тип угод, які відкриватиме стратегія
        """

        # Ініціалізуємо базові налаштування
        super().__init__(look_ahead, commission, spread, initial_balance, db_table_path, close_on_next_candle)
        
        self.strategy = strategy
        self.db_path = db_path
        self.trade_direction = trade_direction.upper()
        
    #------------------------------
    # Запуск двигуна бэктесту
    #------------------------------

    def run(self, result_table_name: str = 'backtest_results'):
        """Запуск бэктесту: ініціалізація БД, генерація сигналів та виконання."""

        print("Запуск бэктесту через Rules Engine...")
        
        with DataBaseManager(self.db_path) as db:

            if self.db_table_path is None:
                print("Помилка: Не вказано таблицю з даними (db_table_path).")
                return
                
            # Отримуємо дані для бэктесту
            df = db.get_data_as_dataframe(self.db_table_path)
            
            if df is None or df.empty:
                print(f"Помилка: Дані в таблиці {self.db_table_path} відсутні.")
                return
                
            print(f"Завантажено {len(df)} рядків з таблиці {self.db_table_path}.")
            
            # Сортуємо по часу для впевненості
            if 'timestamp' in df.columns:
                df = df.sort_values('timestamp').reset_index(drop=True)

            # 1. Запускаємо рушій правил (векторизовано)
            from utils.rules_engine import IndicatorRegistry
            registry = IndicatorRegistry(df)
            
            print("Обчислення сигналів стратегії...")
            signals_df = self.strategy.execute(registry)
            
            # Оновлюємо df новими індикаторами, які створив реєстр
            df = registry.data
                
            # 2. Ініціалізуємо Deal Writer
            deal_writer = LaboratoryBacktesterDealWriter(db_manager=db, df=df, table_name=self.db_table_path, settings=self)
            
            # 3. Виконуємо ітерацію по розрахованих сигналах
            return self._process_signals(df, signals_df, deal_writer, result_table_name=result_table_name)

    #------------------------------
    # Процес ітерації по сигналах
    #------------------------------

    def _process_signals(self, df: pd.DataFrame, signals_df: pd.DataFrame, deal_writer: LaboratoryBacktesterDealWriter, result_table_name: str = 'backtest_results'):
        """Метод для переведення булевих сигналів у реальні угоди"""

        current_position = None  # None, 'BUY' або 'SELL'
        current_trade_id = None
        
        print("Виконання угод...")
        for i in range(len(df)):
            current_timestamp = float(df.iloc[i]['timestamp']) if 'timestamp' in df.columns else float(i)
            
            # Отримуємо розраховані рушієм сигнали
            is_entry = bool(signals_df.iloc[i]['entry'])
            is_exit = bool(signals_df.iloc[i]['exit'])

            # Автоматичне закриття угоди перед обробкою нової (якщо включено)
            if self.close_on_next_candle and current_position is not None:
                deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                current_position = None
                current_trade_id = None
            
            # 1. Обробка ВИХОДУ
            if is_exit and current_position is not None:
                deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                current_position = None
                current_trade_id = None

            # 2. Обробка ВХОДУ
            if is_entry and current_position is None:
                trade_type = 'buy' if self.trade_direction == 'BUY' else 'sell'
                deal_writer._add_trade_entry(trade_type=trade_type, timestamp=current_timestamp)
                latest_trade = deal_writer.id_trade_info.iloc[-1]
                current_trade_id = latest_trade['TradeNumber']
                current_position = self.trade_direction
        
        # Закриваємо позицію в кінці бэктесту, якщо вона залишилась відкритою
        if current_position is not None:
            last_timestamp = float(df.iloc[-1]['timestamp']) if 'timestamp' in df.columns else float(len(df)-1)
            deal_writer._add_trade_exit(timestamp=last_timestamp, id_trade=current_trade_id)
            
        # Зберігаємо результати у базу даних
        try:
            db.conn.execute(f"DROP TABLE IF EXISTS {result_table_name}")
        except Exception:
            pass
        deal_writer.save_results_to_db(table_name=result_table_name)
        print("Бэктест завершено.")
        return deal_writer.id_trade_info
