import pandas as pd

from utils.algorithms.backtesting.BaseSettings import BaseSettings
from utils.algorithms.backtesting.SignalProvider import Analyzer
from utils.DataBaseManager import DataBaseManager
from utils.LaboratoryBacktesterDealWriter import LaboratoryBacktesterDealWriter

#==================================
# Двигун Ринку (Market Runner)
#==================================

class MarketRunner(BaseSettings):

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, 
                 analyzer: Analyzer,
                 db_path: str = 'main.db',
                 look_ahead: bool = False,
                 commission: float = 0.0,
                 spread: float = 0.0,
                 initial_balance: float = 10000.0,
                 db_table_path: str = None,
                 close_on_next_candle: bool = False):
        """
        Параметри: 
        analyzer: екземпляр класу Analyzer (SignalProvider)
        db_path: шлях до файлу бази даних DuckDB
        close_on_next_candle: автоматично закривати позицію перед наступною свічкою
        """

        # Ініціалізуємо базові налаштування
        super().__init__(look_ahead, commission, spread, initial_balance, db_table_path, close_on_next_candle)
        
        self.analyzer = analyzer
        self.db_path = db_path
        
    #------------------------------
    # Запуск двигуна бэктесту
    #------------------------------

    def run(self):
        """Запуск бэктесту: ініціалізація БД та підготовка даних."""

        print("Запуск бэктесту...")
        
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
                
            # Ініціалізуємо Deal Writer
            deal_writer = LaboratoryBacktesterDealWriter(db_manager=db, df=df, table_name=self.db_table_path, settings=self)
            
            # Передаємо управління процесу ітерації
            self._process_data(df, deal_writer)

    #------------------------------
    # Процес ітерації по даних
    #------------------------------

    def _process_data(self, df: pd.DataFrame, deal_writer: LaboratoryBacktesterDealWriter):
        """Метод для ітерації по DataFrame свічка за свічкою та генерації/виконання угод"""

        current_position = None  # None, 'BUY' або 'SELL'
        current_trade_id = None
        window_size = self.analyzer.window_size
        
        for i in range(len(df)):
            if i < window_size - 1:
                continue # Чекаємо поки набереться достатньо даних для вікна
                
            # Отримуємо зріз даних (window)
            window = df.iloc[i - window_size + 1 : i + 1]
                
            # Отримуємо сигнал від незалежного аналізатора
            signal = self.analyzer.check_signal(window)
            
            current_timestamp = float(df.iloc[i]['timestamp']) if 'timestamp' in df.columns else float(i)

            # Автоматичне закриття угоди перед обробкою нової (якщо включено)
            if self.close_on_next_candle and current_position is not None:
                deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                current_position = None
                current_trade_id = None
            
            # Обробка отриманого сигналу
            current_position, current_trade_id = self._execute_signal(
                signal=signal, 
                deal_writer=deal_writer, 
                current_position=current_position, 
                current_trade_id=current_trade_id, 
                current_timestamp=current_timestamp
            )
        
        # Закриваємо позицію в кінці бэктесту, якщо вона залишилась відкритою
        if current_position is not None:
            last_timestamp = float(df.iloc[-1]['timestamp']) if 'timestamp' in df.columns else float(len(df)-1)
            deal_writer._add_trade_exit(timestamp=last_timestamp, id_trade=current_trade_id)
            
        # Зберігаємо результати у базу даних (Step 0)
        deal_writer.save_results_to_db(table_name='backtest_results')
        print("Бэктест завершено.")

    #------------------------------
    # Логіка виконання сигналів
    #------------------------------

    def _execute_signal(self, signal: str, deal_writer: LaboratoryBacktesterDealWriter, current_position: str, current_trade_id: int, current_timestamp: float) -> tuple:
        """Метод для виконання торгових сигналів через Deal Writer"""

        if signal == 'BUY' and current_position != 'BUY':
            # Якщо є відкрита позиція SELL, закриваємо її
            if current_position == 'SELL':
                deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                
            # Відкриваємо нову позицію BUY
            deal_writer._add_trade_entry(trade_type='buy', timestamp=current_timestamp)
            latest_trade = deal_writer.id_trade_info.iloc[-1]
            current_trade_id = latest_trade['TradeNumber']
            current_position = 'BUY'
            
        elif signal == 'SELL' and current_position != 'SELL':
            # Якщо є відкрита позиція BUY, закриваємо її
            if current_position == 'BUY':
                deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                
            # Відкриваємо нову позицію SELL
            deal_writer._add_trade_entry(trade_type='sell', timestamp=current_timestamp)
            latest_trade = deal_writer.id_trade_info.iloc[-1]
            current_trade_id = latest_trade['TradeNumber']
            current_position = 'SELL'
            
        elif signal == 'CLOSE' and current_position is not None:
            # Закриваємо поточну позицію без відкриття нової
            deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
            current_position = None
            current_trade_id = None

        return current_position, current_trade_id
