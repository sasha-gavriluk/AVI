import os
import pandas as pd
import sys

# Додаємо корінь проекту в PYTHONPATH, щоб імпорти працювали
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from utils.DataBaseManager import DataBaseManager

# ==================================
# Сервіс DuckDB
# ==================================

class DuckDBService:
    """Сервіс для взаємодії між GUI та базою даних DuckDB"""
    
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------
    
    def __init__(self):
        """Метод для ініціалізації сервісу бази даних"""
        self.db_manager = None
        self.current_db_path = None
        
    # ----------------------------------
    # Підключення до бази
    # ----------------------------------
        
    def connect(self, db_path: str):
        """Метод для підключення до бази даних за вказаним шляхом"""
        self.current_db_path = db_path
        self.db_manager = DataBaseManager(db_path)
        
    # ----------------------------------
    # Отримання списку таблиць
    # ----------------------------------
        
    def get_tables(self) -> list:
        """Метод для повернення списку таблиць у підключеній базі"""
        if not self.db_manager:
            return []
        try:
            return self.db_manager.get_all_tables()
        except Exception as e:
            print(f"Помилка отримання таблиць: {e}")
            return []
            
    # ----------------------------------
    # Отримання даних з таблиці
    # ----------------------------------
            
    def get_table_data(self, table_name: str, limit: int = 1000, offset: int = 0) -> pd.DataFrame:
        """Метод для отримання даних з таблиці (з підтримкою пагінації)"""
        if not self.db_manager:
            return pd.DataFrame()
            
        query = f"SELECT * FROM {table_name} LIMIT {limit} OFFSET {offset}"
        try:
            return self.db_manager.conn.execute(query).fetchdf()
        except Exception as e:
            print(f"Помилка виконання запиту: {e}")
            return pd.DataFrame()
            
    # ----------------------------------
    # Отримання загальної кількості рядків
    # ----------------------------------
            
    def get_table_count(self, table_name: str) -> int:
        """Метод для отримання загальної кількості рядків у таблиці"""
        if not self.db_manager:
            return 0
            
        query = f"SELECT COUNT(*) FROM {table_name}"
        try:
            df = self.db_manager.conn.execute(query).fetchdf()
            return int(df.iloc[0, 0])
        except Exception as e:
            print(f"Помилка отримання кількості: {e}")
            return 0
