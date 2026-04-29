import duckdb
import os
import pandas as pd

from utils.other_utils import _handle_error

class DataBaseManager:

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, db_path):

        abspath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', "data", 'db'))
        self.db_path = os.path.join(abspath, db_path)

        if not os.path.exists(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.connect()

    #------------------------------
    # Підключення та відключення
    #------------------------------

    @_handle_error
    def connect(self):
        self.conn = duckdb.connect(self.db_path)

    @_handle_error
    def disconnect(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    #------------------------------
    # Створення таблиці
    #------------------------------
    
    @_handle_error
    def create_table(self, table_name, schema):
        "Параметри: table_name - назва таблиці, schema - рядок з описом стовпців (наприклад: 'id INTEGER, name TEXT')"
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
        self.conn.execute(query)

    #------------------------------
    # Вставка даних з pandas DataFrame в таблицю новостворенную
    #------------------------------

    @_handle_error
    def insert_data_from_pandas(self, table_name, df: pd.DataFrame):
        "Параметри: table_name - назва таблиці, df - pandas DataFrame"
        if 'timestamp' in df.columns:
            df = df.drop_duplicates(subset='timestamp', keep='last')

        self.conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM df")

    #-----------------------------------
    # Вставка даних з pandas DataFrame в існуючу таблицю
    #-----------------------------------

    @_handle_error
    def insert_data_from_pandas_append(self, table_name, df: pd.DataFrame):
        "Параметри: table_name - назва таблиці, df - pandas DataFrame"

        if 'timestamp' not in df.columns:
            return

        df_to_insert = df.drop_duplicates(subset='timestamp', keep='last')
        df_to_insert = self.conn.execute(f"""
            SELECT incoming.*
            FROM df_to_insert AS incoming
            WHERE NOT EXISTS (
                SELECT 1
                FROM {table_name} AS existing
                WHERE existing.timestamp = incoming.timestamp
            )
        """).fetchdf()

        if not df_to_insert.empty:
            print(f"Записано нових рядків: {len(df_to_insert)}")
            self.conn.execute(f"INSERT INTO {table_name} SELECT * FROM df_to_insert")
        else:
            print("Нових даних для запису немає")

    #------------------------------
    # Автоматичний вибрір між створення та вставкою даних
    #------------------------------

    @_handle_error
    def insert_data_from_pandas_auto(self, table_name, df: pd.DataFrame):
        "Параметри: table_name - назва таблиці, df - pandas DataFrame"

        if self.conn.execute(f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}'").fetchone() is None:
            self.insert_data_from_pandas(table_name, df)
        else:
            self.insert_data_from_pandas_append(table_name, df)

    #------------------------------
    # Вивід даних всіх таблиць з бази даних
    #------------------------------

    @_handle_error
    def get_all_tables(self):
        "Отримання списку всіх таблиць в базі даних"
        tables = self.conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
        return [table[0] for table in tables]
    
    #------------------------------
    # Вивід даних з таблиці в pandas DataFrame
    #------------------------------

    @_handle_error
    def get_data_as_dataframe(self, table_name):
        "Параметри: table_name - назва таблиці"
        df = self.conn.execute(f"SELECT * FROM {table_name}").fetchdf()
        return df

    #------------------------------
    # Методи які які використуваються в самому класі, але можуть бути корисними і зовні
    #------------------------------

    #------------------------------
    # Вивід останоого запису з таблиці в pandas DataFrame
    #------------------------------

    @_handle_error
    def _get_last_record_as_dataframe(self, table_name):
        "Параметри: table_name - назва таблиці"
        df = self.conn.execute(f"SELECT * FROM {table_name} WHERE timestamp = (SELECT MAX(timestamp) FROM {table_name})").fetchdf()
        return df
    
    #------------------------------
    # Метод для виводу певного діапазону даних з кінця таблиці в pandas DataFrame
    #------------------------------

    @_handle_error
    def get_data_by_number_range(self, table_name, number):
        "Параметри: table_name - назва таблиці, number - кількість рядків для отримання"
        try:
            df = self.conn.execute(f"SELECT * FROM {table_name} ORDER BY timestamp DESC LIMIT {number}").fetchdf()
        except Exception as e:
            print(f"Помилка при отриманні даних за діапазоном: {e} - можливо, в таблиці недостатньо даних для отримання запитуваного діапазону. Використовується лише наявні дані.")
            return None
        return df
    
    #------------------------------
    # Метод для пошуку прогалин в даних за timestamp
    #------------------------------

    @_handle_error
    def get_time_gaps(self, table_name: str, timeframe_ms: int = 60000) -> list:
        """
        Знаходить прогалини (аномалії) у часових рядах бази даних.
        timeframe_ms: очікуваний крок між свічками в мілісекундах (60000 для 1 хв).
        Повертає список словників: [{'gap_start': 1600000000, 'gap_end': 1600003600}, ...]
        """
        
        query = f"""
            WITH TimeCheck AS (
                SELECT 
                    timestamp AS current_time,
                    LAG(timestamp) OVER (ORDER BY timestamp) AS prev_time
                FROM {table_name}
            )
            SELECT 
                prev_time AS gap_start, 
                current_time AS gap_end
            FROM TimeCheck
            WHERE prev_time IS NOT NULL 
              AND (current_time - prev_time) > {timeframe_ms};
        """
        
        df = self.conn.execute(query).fetchdf()
        gaps_list = df.to_dict('records')
        
        return gaps_list
    

    #------------------------------
    # Метод для перетворяння часу в нормальний формат, для всіх прогалин в даних за timestamp
    #------------------------------

    @_handle_error
    def get_time_gaps_human_readable(self, table_name: str, timeframe_ms: int = 60000) -> list:
        """
        Знаходить прогалини (аномалії) у часових рядах бази даних та перетворює їх у людський формат.
        timeframe_ms: очікуваний крок між свічками в мілісекундах (60000 для 1 хв).
        Повертає список словників: [{'gap_start': '2020-09-13 12:00:00', 'gap_end': '2020-09-13 12:10:00'}, ...]
        """
        
        gaps_list = self.get_time_gaps(table_name, timeframe_ms)
        
        for gap in gaps_list:
            gap['gap_start'] = pd.to_datetime(gap['gap_start'], unit='ms').strftime('%Y-%m-%d %H:%M:%S')
            gap['gap_end'] = pd.to_datetime(gap['gap_end'], unit='ms').strftime('%Y-%m-%d %H:%M:%S')
        
        return gaps_list
