import duckdb
import os
import pandas as pd
import threading

from utils.other_utils import _handle_error

_db_lock = threading.Lock()
_connections = {}

class DataBaseManager:

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, db_path=None, use_default=False):

        from utils.PathManager import PathManager
        
        # Рубильник: якщо передано use_default=True або не вказано шлях взагалі,
        # використовуємо стандартну єдину базу даних.
        if use_default or not db_path:
            self.db_path = PathManager.get_db_path()
        else:
            if os.path.isabs(db_path):
                self.db_path = db_path
            else:
                # Якщо просто ім'я, зберігаємо в папку користувача
                self.db_path = os.path.join(PathManager.get_user_data_dir(), db_path)

        if not os.path.exists(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.connect()

    #------------------------------
    # Підключення та відключення
    #------------------------------

    @_handle_error
    def connect(self):
        with _db_lock:
            if self.db_path not in _connections:
                _connections[self.db_path] = {"conn": duckdb.connect(self.db_path), "ref_count": 0}
            self.conn = _connections[self.db_path]["conn"]
            _connections[self.db_path]["ref_count"] += 1

    @_handle_error
    def disconnect(self):
        with _db_lock:
            if hasattr(self, 'conn') and self.conn:
                if self.db_path in _connections:
                    _connections[self.db_path]["ref_count"] -= 1
                    if _connections[self.db_path]["ref_count"] <= 0:
                        self.conn.close()
                        del _connections[self.db_path]
                self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    #------------------------------
    # Валідація
    #------------------------------
    
    def _validate_table_name(self, table_name: str):
        """Перевіряє чи назва таблиці безпечна (проти SQL Injection)"""
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
            raise ValueError(f"Недійсна назва таблиці: {table_name}. Дозволені лише літери, цифри та підкреслення.")

    #------------------------------
    # Створення таблиці
    #------------------------------
    
    @_handle_error
    def create_table(self, table_name, schema):
        "Параметри: table_name - назва таблиці, schema - рядок з описом стовпців (наприклад: 'id INTEGER, name TEXT')"
        self._validate_table_name(table_name)
        query = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({schema})'
        self.conn.execute(query)

    @_handle_error
    def create_index(self, table_name: str, column: str):
        """Створює індекс якщо не існує"""
        self._validate_table_name(table_name)
        index_name = f"idx_{table_name}_{column}"
        self.conn.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}"("{column}")')

    #------------------------------
    # Вставка даних з pandas DataFrame в таблицю новостворенную
    #------------------------------

    @_handle_error
    def insert_data_from_pandas(self, table_name, df: pd.DataFrame):
        "Параметри: table_name - назва таблиці, df - pandas DataFrame"
        self._validate_table_name(table_name)
        if 'timestamp' in df.columns:
            df = df.drop_duplicates(subset='timestamp', keep='last')

        self.conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" AS SELECT * FROM df')
        
        if 'timestamp' in df.columns:
            self.create_index(table_name, 'timestamp')

    #-----------------------------------
    # Вставка даних з pandas DataFrame в існуючу таблицю
    #-----------------------------------

    @_handle_error
    def insert_data_from_pandas_append(self, table_name, df: pd.DataFrame):
        "Параметри: table_name - назва таблиці, df - pandas DataFrame"
        self._validate_table_name(table_name)

        if 'timestamp' not in df.columns:
            # Для таблиць без timestamp (наприклад, результатів бектесту) 
            # просто додаємо всі нові рядки
            print(f"Записано нових рядків (без перевірки timestamp): {len(df)}")
            self.conn.execute(f'INSERT INTO "{table_name}" SELECT * FROM df')
            return

        df_to_insert = df.drop_duplicates(subset='timestamp', keep='last')
        df_to_insert = self.conn.execute(f"""
            SELECT incoming.*
            FROM df_to_insert AS incoming
            WHERE NOT EXISTS (
                SELECT 1
                FROM "{table_name}" AS existing
                WHERE existing.timestamp = incoming.timestamp
            )
        """).fetchdf()

        if not df_to_insert.empty:
            print(f"Записано нових рядків: {len(df_to_insert)}")
            self.conn.execute(f'INSERT INTO "{table_name}" SELECT * FROM df_to_insert')
        else:
            print("Нових даних для запису немає")

    #------------------------------
    # Автоматичний вибрір між створення та вставкою даних
    #------------------------------

    @_handle_error
    def insert_data_from_pandas_auto(self, table_name, df: pd.DataFrame):
        "Параметри: table_name - назва таблиці, df - pandas DataFrame"
        self._validate_table_name(table_name)

        if self.conn.execute(f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}'").fetchone() is None:
            self.insert_data_from_pandas(table_name, df)
        else:
            self.insert_data_from_pandas_append(table_name, df)
            
        if table_name == "copilot_memory":
            self.create_index("copilot_memory", "timestamp")
            self.create_index("copilot_memory", "asset")
        elif table_name == "rules_changelog":
            self.create_index("rules_changelog", "element")

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
        self._validate_table_name(table_name)
        df = self.conn.execute(f'SELECT * FROM "{table_name}"').fetchdf()
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
        self._validate_table_name(table_name)
        df = self.conn.execute(f'SELECT * FROM "{table_name}" WHERE timestamp = (SELECT MAX(timestamp) FROM "{table_name}")').fetchdf()
        return df
    
    #------------------------------
    # Метод для виводу певного діапазону даних з кінця таблиці в pandas DataFrame
    #------------------------------

    @_handle_error
    def get_data_by_number_range(self, table_name, number):
        "Параметри: table_name - назва таблиці, number - кількість рядків для отримання"
        self._validate_table_name(table_name)
        try:
            df = self.conn.execute(f'SELECT * FROM "{table_name}" ORDER BY timestamp DESC LIMIT {number}').fetchdf()
            if df is not None and not df.empty and 'timestamp' in df.columns:
                df = df.sort_values('timestamp').reset_index(drop=True)
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
        self._validate_table_name(table_name)
        
        query = f"""
            WITH TimeCheck AS (
                SELECT 
                    CAST(timestamp AS BIGINT) AS current_time,
                    LAG(CAST(timestamp AS BIGINT)) OVER (ORDER BY CAST(timestamp AS BIGINT)) AS prev_time
                FROM "{table_name}"
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
