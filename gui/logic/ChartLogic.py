import os
import pandas as pd
from utils.DataBaseManager import DataBaseManager
from utils.config import db_dir

from PyQt6.QtCore import QObject, QThread, pyqtSignal

class ChartLoaderThread(QThread):
    result_signal = pyqtSignal(bool, object) # success, df
    def __init__(self, logic, db_path, table_name, load_more=False):
        super().__init__()
        self.logic = logic
        self.db_path = db_path
        self.table_name = table_name
        self.load_more = load_more
        
    def run(self):
        if not self.load_more:
            success, df = self.logic._load_initial_data_sync(self.db_path, self.table_name)
        else:
            success, df = self.logic._load_more_data_sync()
        self.result_signal.emit(success, df)

#==================================
# ChartLogic
#==================================
class ChartLogic(QObject):
    chart_loaded = pyqtSignal(bool)
    chart_more_loaded = pyqtSignal(int)
    
    # ----------------------------------
    # __init__, ініціалізація логіки графіка
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        super().__init__()
        self.current_db = None
        self.current_table = None
        self.df = None
        self.trades_df = None
        self.current_trades_table = None
        self.is_loading = False

    # ----------------------------------
    # get_available_assets, зчитування баз та таблиць
    # ----------------------------------
    # Параметри: немає
    def get_available_assets(self) -> list:
        available = []
        if not os.path.exists(db_dir):
            return available
            
        dbs = [f for f in os.listdir(db_dir) if f.endswith('.duckdb')]
        for db in dbs:
            try:
                db_path = os.path.join(db_dir, db)
                dbm = DataBaseManager(db_path)
                tables = dbm.get_all_tables()
                dbm.disconnect()
                
                for t in tables:
                    if "backtest" not in t.lower() and "auto_learn" not in t.lower() and not t.startswith("sqlite_"):
                        available.append((db_path, t))
            except Exception as e:
                print(f"Помилка зчитування БД {db}: {e}")
        return available

    # ----------------------------------
    # request_initial_data_async, асинхронне завантаження свічок
    # ----------------------------------
    def request_initial_data_async(self, db_path: str, table_name: str):
        if table_name == "backtest_results" or table_name.startswith("backtest_"):
            self.chart_loaded.emit(False)
            return
            
        self.current_db = db_path
        self.current_table = table_name
        self.trades_df = None
        self.current_trades_table = None
        
        self._load_thread = ChartLoaderThread(self, db_path, table_name, load_more=False)
        self._load_thread.result_signal.connect(self._on_initial_data_loaded)
        self._load_thread.start()
        
    def _on_initial_data_loaded(self, success, df):
        if success:
            self.df = df
        else:
            self.df = None
        self.chart_loaded.emit(success)

    def _load_initial_data_sync(self, db_path: str, table_name: str):
        dbm = DataBaseManager(db_path)
        df = dbm.get_data_by_number_range(table_name, 1000)
        dbm.disconnect()
        
        if df is None or df.empty:
            return False, None
            
        df = df.sort_values('timestamp')
        df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('time', inplace=True)
        return True, df

    # ----------------------------------
    # request_more_data_async, асинхронне дозавантаження свічок
    # ----------------------------------
    def request_more_data_async(self):
        if self.df is None or self.df.empty or not self.current_db:
            self.chart_more_loaded.emit(0)
            return
            
        self.is_loading = True
        self._load_more_thread = ChartLoaderThread(self, self.current_db, self.current_table, load_more=True)
        self._load_more_thread.result_signal.connect(self._on_more_data_loaded)
        self._load_more_thread.start()
        
    def _on_more_data_loaded(self, success, new_df):
        if success and not new_df.empty:
            added_count = len(new_df)
            self.df = pd.concat([new_df, self.df])
            self.chart_more_loaded.emit(added_count)
        else:
            self.chart_more_loaded.emit(0)
        self.is_loading = False

    def _load_more_data_sync(self):
        dbm = DataBaseManager(self.current_db)
        earliest_timestamp = int(self.df['timestamp'].iloc[0])
        query = f"SELECT * FROM {self.current_table} WHERE timestamp < {earliest_timestamp} ORDER BY timestamp DESC LIMIT 1000"
        new_df = dbm.conn.execute(query).fetchdf()
        dbm.disconnect()
        
        if new_df.empty:
            return False, pd.DataFrame()
            
        new_df = new_df.sort_values('timestamp')
        new_df['time'] = pd.to_datetime(new_df['timestamp'], unit='ms')
        new_df.set_index('time', inplace=True)
        return True, new_df

    # ----------------------------------
    # get_backtest_tables, отримання таблиць бектестів для активу
    # ----------------------------------
    # Параметри: немає
    def get_backtest_tables(self) -> list:
        if not self.current_db or not self.current_table:
            return []
            
        dbm = DataBaseManager(self.current_db)
        tables = dbm.get_all_tables()
        dbm.disconnect()
        
        prefix = f"backtest_{self.current_table}_"
        return [t for t in tables if t.startswith(prefix)]

    # ----------------------------------
    # load_trades, завантаження угод з таблиці
    # ----------------------------------
    # Параметри:
    # trades_table (str): Назва таблиці угод
    def load_trades(self, trades_table: str) -> bool:
        if not self.current_db:
            return False
            
        self.current_trades_table = trades_table
        dbm = DataBaseManager(self.current_db)
        trades_df = dbm.get_data_as_dataframe(trades_table)
        dbm.disconnect()
        
        if trades_df.empty:
            self.trades_df = None
            return False
            
        self.trades_df = trades_df
        return True

    # ----------------------------------
    # find_nearest_trade, пошук найближчої угоди за часом
    # ----------------------------------
    # Параметри:
    # click_time_idx (datetime): Час кліку по осі X
    def find_nearest_trade(self, click_time_idx):
        if self.trades_df is None or self.df is None or self.trades_df.empty:
            return None
            
        click_ms = click_time_idx.timestamp() * 1000
        
        tf_ms = 15 * 60000
        if len(self.df) > 1:
            tf_ms = (self.df.index[1] - self.df.index[0]).total_seconds() * 1000
            
        threshold = tf_ms * 3
        
        closest_trade = None
        min_dist = float('inf')
        
        for _, trade in self.trades_df.iterrows():
            entry_ms = trade['EntryTimestamp']
            exit_ms = trade['ExitTimestamp']
            
            dist_entry = abs(entry_ms - click_ms)
            dist_exit = abs(exit_ms - click_ms)
            
            if dist_entry < min_dist and dist_entry <= threshold:
                min_dist = dist_entry
                closest_trade = trade
            if dist_exit < min_dist and dist_exit <= threshold:
                min_dist = dist_exit
                closest_trade = trade
                
        return closest_trade
