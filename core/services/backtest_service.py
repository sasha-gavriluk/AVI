import os
import pandas as pd
from utils.DataBaseManager import DataBaseManager
from utils.algorithms.backtesting.MarketRunner import MarketRunner

class BacktestService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_name = os.path.basename(db_path)
        
    def run_wfv(self, strategy, table_name: str, num_windows: int = 5, train_ratio: float = 0.7):
        """
        Виконує Walk-Forward Validation для заданої стратегії.
        Розбиває дані на num_windows вікон, кожне з яких має Train та Test періоди.
        Повертає список результатів для кожного вікна.
        """
        dbm = DataBaseManager(use_default=True)
        df = dbm.get_data_as_dataframe(table_name)
        
        if df.empty:
            raise ValueError("Немає даних для WFV")
            
        df = df.sort_values('timestamp')
        total_rows = len(df)
        window_size = total_rows // num_windows
        
        results = []
        
        for i in range(num_windows):
            start_idx = i * window_size
            # Для останнього вікна беремо до кінця
            end_idx = start_idx + window_size if i < num_windows - 1 else total_rows
            
            window_df = df.iloc[start_idx:end_idx]
            n_window = len(window_df)
            
            train_size = int(n_window * train_ratio)
            train_df = window_df.iloc[:train_size]
            test_df = window_df.iloc[train_size:]
            
            # Запуск на Train
            train_pf, train_wr, train_trades = self._eval_subset(strategy, train_df, dbm, f"{i}_train")
            
            # Запуск на Test
            test_pf, test_wr, test_trades = self._eval_subset(strategy, test_df, dbm, f"{i}_test")
            
            def safe_format_ts(val):
                try:
                    if pd.isna(val): return "Unknown"
                    if isinstance(val, (int, float, str)) and str(val).isdigit():
                        return pd.to_datetime(float(val), unit='ms').strftime('%Y-%m-%d')
                    return pd.to_datetime(val).strftime('%Y-%m-%d')
                except:
                    return "Unknown"

            results.append({
                "window": i + 1,
                "train_start": safe_format_ts(train_df['timestamp'].iloc[0]) if not train_df.empty else "N/A",
                "train_end": safe_format_ts(train_df['timestamp'].iloc[-1]) if not train_df.empty else "N/A",
                "test_start": safe_format_ts(test_df['timestamp'].iloc[0]) if not test_df.empty else "N/A",
                "test_end": safe_format_ts(test_df['timestamp'].iloc[-1]) if not test_df.empty else "N/A",
                "train_pf": train_pf,
                "train_wr": train_wr,
                "train_trades": train_trades,
                "test_pf": test_pf,
                "test_wr": test_wr,
                "test_trades": test_trades,
                "is_robust": (test_pf >= 1.0 and train_pf >= 1.0)
            })
            
        dbm.disconnect()
        return results

    def _eval_subset(self, strategy, subset_df, dbm, window_name):
        temp_table = f"temp_wfv_data_{window_name}"
        res_table = f"temp_wfv_res_{window_name}"
        
        # Записуємо зріз в тимчасову таблицю
        dbm.conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
        dbm.conn.execute(f"CREATE TABLE {temp_table} AS SELECT * FROM subset_df")
        
        runner = MarketRunner(strategy=strategy, db_path=self.db_name, db_table_path=temp_table)
        
        # Патчимо вивід
        import sys, io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            trades_df = runner.run(result_table_name=res_table)
        except Exception as e:
            print(f"Помилка в MarketRunner: {e}")
            trades_df = None
        finally:
            sys.stdout = old_stdout
            
        # Розрахунок метрик
        total_trades = len(trades_df) if trades_df is not None and not trades_df.empty else 0
        pf, wr = 0.0, 0.0
        
        if total_trades > 0:
            winning_trades = len(trades_df[trades_df['Profit'] > 0])
            wr = (winning_trades / total_trades) * 100.0
            
            gross_profit = trades_df[trades_df['Profit'] > 0]['Profit'].sum()
            gross_loss = abs(trades_df[trades_df['Profit'] < 0]['Profit'].sum())
            pf = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
            
        # Прибираємо тимчасові таблиці
        dbm.conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
        dbm.conn.execute(f"DROP TABLE IF EXISTS {res_table}")
        
        return pf, wr, total_trades
