import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from gui.logic.DuckDbService import DuckDbService

class DbLoaderThread(QThread):
    result_signal = pyqtSignal(dict)
    def __init__(self, logic, is_locked_callback):
        super().__init__()
        self.logic = logic
        self.is_locked_callback = is_locked_callback
    def run(self):
        dbs = self.logic._get_databases_dict_sync(self.is_locked_callback)
        self.result_signal.emit(dbs)

class TableLoaderThread(QThread):
    result_signal = pyqtSignal(object) # df
    def __init__(self, logic):
        super().__init__()
        self.logic = logic
    def run(self):
        data = self.logic._get_current_page_data_sync()
        self.result_signal.emit(data)

#==================================
# ExplorerLogic
#==================================
class ExplorerLogic(QObject):
    db_loaded = pyqtSignal(dict)
    table_loaded = pyqtSignal(object, int) # df, total_rows
    
    # ----------------------------------
    # __init__, ініціалізація логіки провідника БД
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        super().__init__()
        self.db_service = DuckDbService()
        self.current_table_name = None
        self.current_offset = 0
        self.limit = 1000
        self.current_total_rows = 0

    # ----------------------------------
    # request_databases_async, асинхронне сканування папки data/db
    # ----------------------------------
    def request_databases_async(self, is_locked_callback=None):
        self._db_thread = DbLoaderThread(self, is_locked_callback)
        self._db_thread.result_signal.connect(self.db_loaded.emit)
        self._db_thread.start()

    def _get_databases_dict_sync(self, is_locked_callback=None) -> dict:
        active_db_path = self.db_service.current_db_path
        
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        db_dir = os.path.join(base_dir, 'data', 'db')
        
        if not os.path.exists(db_dir):
            return {}
            
        dbs = [f for f in os.listdir(db_dir) if f.endswith('.duckdb')]
        databases_dict = {}
        
        for db in dbs:
            db_path = os.path.join(db_dir, db)
            
            if is_locked_callback and is_locked_callback(db_path):
                databases_dict[db] = {
                    "path": db_path,
                    "tables": ["(Завантажується...)"]
                }
                continue

            try:
                self.db_service.connect(db_path)
                tables = self.db_service.get_tables()
                self.db_service.disconnect()
                
                databases_dict[db] = {
                    "path": db_path,
                    "tables": tables
                }
            except Exception as e:
                print(f"Не вдалося завантажити таблиці для {db}: {e}")
                
        if active_db_path and os.path.exists(active_db_path):
            self.db_service.connect(active_db_path)
            
        return databases_dict

    # ----------------------------------
    # request_table_data_async, асинхронне підключення і завантаження даних
    # ----------------------------------
    def request_table_data_async(self, db_path: str, table_name: str, reset_offset: bool = True):
        if self.db_service.current_db_path != db_path:
            self.db_service.connect(db_path)
        self.current_table_name = table_name
        if reset_offset:
            self.current_offset = 0
            
        # Запускаємо в потоці
        def _on_table_ready(df):
            self.table_loaded.emit(df, self.current_total_rows)
            
        self._tbl_thread = TableLoaderThread(self)
        self._tbl_thread.result_signal.connect(_on_table_ready)
        self._tbl_thread.start()

    def _get_current_page_data_sync(self):
        if not self.current_table_name:
            return None
        # Рахуємо завжди перед завантаженням, якщо offset 0 (оптимізація)
        if self.current_offset == 0:
            self.current_total_rows = self.db_service.get_table_count(self.current_table_name)
        return self.db_service.get_table_data(self.current_table_name, limit=self.limit, offset=self.current_offset)

    # ----------------------------------
    # delete_table, видалення таблиці
    # ----------------------------------
    # Параметри:
    # table_name (str): Назва таблиці
    def delete_table(self, table_name: str):
        self.db_service.execute_query(f'DROP TABLE "{table_name}"')
        
    # ----------------------------------
    # clean_tests, очищення від тестів
    # ----------------------------------
    # Параметри: немає
    def clean_tests(self) -> int:
        tables = self.db_service.get_tables()
        drop_count = 0
        for t in tables:
            t_lower = t.lower()
            if "backtest" in t_lower or "auto_learn" in t_lower:
                self.db_service.execute_query(f'DROP TABLE "{t}"')
                drop_count += 1
        return drop_count
