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
    sim_trades_updated = pyqtSignal(list)
    sim_trade_event = pyqtSignal(str, object, str)
    
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
        self.no_more_data = False
        
        self.sim_df = None
        self.sim_current_idx = 0
        self.is_simulating = False
        
        from PyQt6.QtCore import QTimer
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self._on_sim_tick)
        self.sim_start_time_idx = None
        self.sim_end_time_idx = None

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
                with DataBaseManager(db_path) as dbm:
                    tables = dbm.get_all_tables()
                
                for t in tables:
                    t_lower = t.lower()
                    if "backtest" not in t_lower and "auto_learn" not in t_lower and not t.startswith("sqlite_"):
                        if t_lower not in ["copilot_memory", "rules_changelog"]:
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
        self.no_more_data = False
        
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
        if self.df is None or self.df.empty or not self.current_db or self.no_more_data:
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
            self.no_more_data = True
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
    # Simulation logic
    # ----------------------------------
    def start_simulation(self, db_path, table_name, range_val, multiplier, strategy_name=None, auto_delete=True):
        if self.is_simulating:
            return False
            
        self.auto_delete = auto_delete
            
        self.current_db = db_path
        self.current_table = table_name
        self.strategy_name = strategy_name
        
        # Розрахунок часу однієї свічки (1x = реальний час)
        tf_str = table_name.split('_')[-1]
        try:
            val = int(tf_str[:-1])
            unit = tf_str[-1].lower()
            if unit == 'm':
                real_ms = val * 60 * 1000
            elif unit == 'h':
                real_ms = val * 60 * 60 * 1000
            elif unit == 'd':
                real_ms = val * 24 * 60 * 60 * 1000
            else:
                real_ms = 60 * 1000
        except Exception:
            real_ms = 60 * 1000
            
        speed_ms = max(20, int(real_ms / multiplier))
        self.trades_df = None
        self.current_trades_table = None
        
        dbm = DataBaseManager(self.current_db)
        
        # Get max timestamp
        max_ts_df = dbm.conn.execute(f"SELECT MAX(timestamp) as max_ts FROM {table_name}").fetchdf()
        if max_ts_df.empty or pd.isna(max_ts_df.iloc[0]['max_ts']):
            dbm.disconnect()
            return False
            
        max_ts = int(max_ts_df.iloc[0]['max_ts'])
        
        start_ts = 0
        if range_val == "1d":
            start_ts = max_ts - (1 * 24 * 60 * 60 * 1000)
        elif range_val == "1w":
            start_ts = max_ts - (7 * 24 * 60 * 60 * 1000)
        elif range_val == "1m":
            start_ts = max_ts - (30 * 24 * 60 * 60 * 1000)
        elif range_val == "1y":
            start_ts = max_ts - (365 * 24 * 60 * 60 * 1000)
            
        query = f"SELECT * FROM {table_name} WHERE timestamp >= {start_ts} ORDER BY timestamp ASC"
        self.sim_df = dbm.conn.execute(query).fetchdf()
        dbm.disconnect()
        
        if self.sim_df.empty:
            return False
            
        self.sim_df['time'] = pd.to_datetime(self.sim_df['timestamp'], unit='ms')
        self.sim_df.set_index('time', inplace=True)
        
        # Take 150 candles as initial history (or 10% of sim if very small)
        history_size = min(150, max(1, len(self.sim_df) // 10))
        
        self.df = self.sim_df.iloc[:history_size].copy()
        self.sim_current_idx = history_size
        
        self.sim_trades_df = None
        self.active_sim_trades = {}
        self.completed_sim_trades = []
        
        if strategy_name and strategy_name != "Без стратегії":
            self._preload_simulation_strategy(strategy_name, table_name)
        
        self.is_simulating = True
        self.sim_timer.start(speed_ms)
        self.chart_loaded.emit(True)
        
        self.sim_start_time_idx = self.df.index[-1] if not self.df.empty else None
        
        return True
        
    def stop_simulation(self):
        if not self.is_simulating: return
        self.sim_timer.stop()
        self.is_simulating = False
        self.sim_end_time_idx = self.df.index[-1] if self.df is not None and not self.df.empty else None
        
        # Log to file
        log_dir = os.path.join(db_dir, '..', 'simulation_logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'log.txt')
        with open(log_path, 'a', encoding='utf-8') as f:
            start_str = str(self.sim_start_time_idx) if self.sim_start_time_idx else "Unknown"
            end_str = str(self.sim_end_time_idx) if self.sim_end_time_idx else "Unknown"
        if getattr(self, "auto_delete", True) and hasattr(self, "current_sim_table") and self.current_sim_table:
            try:
                dbm = DataBaseManager(self.current_db)
                dbm.conn.execute(f"DROP TABLE IF EXISTS {self.current_sim_table}")
                dbm.disconnect()
            except Exception as e:
                print(f"Помилка видалення тимчасової таблиці: {e}")
                
    def clear_temp_sim_tables(self):
        import os
        from utils.config import db_dir
        deleted_count = 0
        if not os.path.exists(db_dir): return 0
        
        dbs = [f for f in os.listdir(db_dir) if f.endswith('.duckdb')]
        for db in dbs:
            db_path = os.path.join(db_dir, db)
            try:
                dbm = DataBaseManager(db_path)
                tables = dbm.get_all_tables()
                for t in tables:
                    if t.startswith("temp_sim_"):
                        try:
                            dbm.conn.execute(f"DROP TABLE IF EXISTS {t}")
                            deleted_count += 1
                        except Exception:
                            pass
                dbm.disconnect()
            except Exception:
                pass
        return deleted_count            
    def _on_sim_tick(self):
        if not self.is_simulating or self.sim_df is None:
            self.sim_timer.stop()
            return
            
        if self.sim_current_idx >= len(self.sim_df):
            self.stop_simulation()
            return
            
        # Add next candle
        new_row = self.sim_df.iloc[self.sim_current_idx]
        self.df = pd.concat([self.df, self.sim_df.iloc[[self.sim_current_idx]]])
        self.sim_current_idx += 1
        
        # Check strategy trades
        if hasattr(self, 'sim_trades_df') and self.sim_trades_df is not None:
            current_time = new_row.name
            current_close = new_row['close']
            
            # Check for new open trades
            opens = self.sim_trades_df[self.sim_trades_df['entry_time'] == current_time]
            for _, trade in opens.iterrows():
                trade_id = str(trade['entry_time'])
                self.active_sim_trades[trade_id] = {
                    'entry_time': trade['entry_time'],
                    'type': trade['type'],
                    'entry_price': trade['entry_price'],
                    'status': 'OPEN',
                    'pnl': 0.0
                }
                if hasattr(self, 'sim_trade_event'):
                    self.sim_trade_event.emit("OPEN", trade['entry_time'], trade['type'])
                
            # Check for closed trades
            closes = self.sim_trades_df[self.sim_trades_df['exit_time'] == current_time]
            for _, trade in closes.iterrows():
                trade_id = str(trade['entry_time'])
                if trade_id in self.active_sim_trades:
                    self.active_sim_trades[trade_id]['status'] = 'CLOSED'
                    self.active_sim_trades[trade_id]['exit_price'] = trade['exit_price']
                    self.active_sim_trades[trade_id]['pnl'] = trade['profit']
                    self.completed_sim_trades.append(self.active_sim_trades.pop(trade_id))
                    if hasattr(self, 'sim_trade_event'):
                        self.sim_trade_event.emit("CLOSE", trade['exit_time'], trade['type'])
                    
            # Update floating PnL for open trades
            for t_id, t_info in self.active_sim_trades.items():
                if t_info['type'] == 'BUY':
                    t_info['pnl'] = current_close - t_info['entry_price']
                else:
                    t_info['pnl'] = t_info['entry_price'] - current_close
                    
            # Emit active trades for UI
            all_trades = list(self.active_sim_trades.values()) + self.completed_sim_trades[-10:] # send open and last 10 closed
            
            # We need a new signal `sim_trades_updated` for this, let's just trigger it dynamically if it exists
            if hasattr(self, 'sim_trades_updated'):
                self.sim_trades_updated.emit(all_trades)
                
        # Emit signal to update UI
        self.chart_more_loaded.emit(1)
        
    def _preload_simulation_strategy(self, strategy_name, table_name):
        import os, sys
        from io import StringIO
        from utils.PathManager import PathManager
        strat_path = os.path.join(PathManager.get_strategies_dir(), strategy_name)
        if not os.path.exists(strat_path):
            return
            
        try:
            with open(strat_path, "r", encoding="utf-8") as f:
                code = f.read()
                
            local_env = {}
            from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy
            local_env['Indicator'] = Indicator
            local_env['Pattern'] = Pattern
            local_env['Algorithm'] = Algorithm
            local_env['Strategy'] = Strategy
            
            compiled_code = compile(code, '<string>', 'exec')
            exec(compiled_code, local_env)
            
            strategy = local_env.get('strategy')
            if not strategy: return
            
            from utils.algorithms.backtesting.MarketRunner import MarketRunner
            runner = MarketRunner(strategy=strategy, db_path=self.current_db, db_table_path=table_name)
            
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            self.current_sim_table = f"temp_sim_{int(pd.Timestamp.now().timestamp())}"
            trades_df = runner.run(self.current_sim_table)
            sys.stdout = old_stdout
            
            if trades_df is not None and not trades_df.empty:
                trades_df = trades_df.rename(columns={
                    'TradeType': 'type',
                    'EntryPrice': 'entry_price',
                    'ExitPrice': 'exit_price',
                    'Profit': 'profit',
                })
                trades_df['entry_time'] = pd.to_datetime(trades_df['EntryTimestamp'], unit='ms')
                
                # Check if exit timestamp is valid before converting
                mask_exit = pd.notna(trades_df['ExitTimestamp']) & (trades_df['ExitTimestamp'] > 0)
                trades_df.loc[mask_exit, 'exit_time'] = pd.to_datetime(trades_df.loc[mask_exit, 'ExitTimestamp'], unit='ms')
                trades_df['type'] = trades_df['type'].str.upper()
                
                # Filter out trades that happened before our simulation visible start
                sim_start_time = self.df.index[-1]
                self.sim_trades_df = trades_df[trades_df['entry_time'] >= sim_start_time].copy()
                
        except Exception as e:
            print(f"Помилка завантаження стратегії для симуляції: {e}")

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
        if tables is None:
            return []
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
