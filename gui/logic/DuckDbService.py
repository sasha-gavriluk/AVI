import os
import pandas as pd
from utils.DataBaseManager import DataBaseManager

#==================================
# DuckDbService
#==================================
class DuckDbService:
    # ----------------------------------
    # __init__, ініціалізація сервісу бази даних
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        self.db_manager = None
        self.current_db_path = None
        
    # ----------------------------------
    # connect, підключення до бази
    # ----------------------------------
    # Параметри:
    # db_path (str): Шлях до файлу бази даних DuckDB
    def connect(self, db_path: str):
        self.disconnect()
        self.current_db_path = db_path
        self.db_manager = DataBaseManager(db_path, use_default=True)
        
    # ----------------------------------
    # disconnect, відключення від бази
    # ----------------------------------
    # Параметри: немає
    def disconnect(self):
        if self.db_manager:
            self.db_manager.disconnect()
            self.db_manager = None
            self.current_db_path = None
        
    # ----------------------------------
    # get_tables, отримання списку таблиць
    # ----------------------------------
    # Параметри: немає
    def get_tables(self) -> list:
        if not self.db_manager:
            return []
        try:
            return self.db_manager.get_all_tables()
        except Exception as e:
            print(f"Помилка отримання таблиць: {e}")
            return []
            
    # ----------------------------------
    # get_table_data, отримання даних з таблиці
    # ----------------------------------
    # Параметри:
    # table_name (str): Назва таблиці
    # limit (int): Кількість рядків для вибірки (пагінація)
    # offset (int): Зміщення для вибірки (пагінація)
    def get_table_data(self, table_name: str, limit: int = 1000, offset: int = 0) -> pd.DataFrame:
        if not self.db_manager:
            return pd.DataFrame()

        try:
            self.db_manager._validate_table_name(table_name)
            query = f'SELECT * FROM "{table_name}" LIMIT {limit} OFFSET {offset}'
            return self.db_manager.conn.execute(query).fetchdf()
        except Exception as e:
            print(f"Помилка виконання запиту для таблиці {table_name}: {e}")
            return pd.DataFrame()
            
    # ----------------------------------
    # execute_query, виконання довільного запиту
    # ----------------------------------
    # Параметри:
    # query (str): SQL запит для виконання
    def execute_query(self, query: str):
        if not self.db_manager or not self.db_manager.conn:
            raise Exception("База даних не підключена.")
        self.db_manager.conn.execute(query)

    # ----------------------------------
    # get_table_count, отримання кількості рядків
    # ----------------------------------
    # Параметри:
    # table_name (str): Назва таблиці
    def get_table_count(self, table_name: str) -> int:
        if not self.db_manager:
            return 0

        try:
            self.db_manager._validate_table_name(table_name)
            query = f'SELECT COUNT(*) FROM "{table_name}"'
            df = self.db_manager.conn.execute(query).fetchdf()
            if df is None or df.empty:
                return 0
            return int(df.iloc[0, 0])
        except Exception as e:
            print(f"Помилка отримання кількості для таблиці {table_name}: {e}")
            return 0
