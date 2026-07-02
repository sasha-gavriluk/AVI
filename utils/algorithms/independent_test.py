import os
import sys
import shutil
import duckdb
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from CopilotAlgorithmicLogic import CopilotAlgorithmicLogic
from indicators.IndicatorProcessor import IndicatorProcessor

DB_PATH = os.path.expanduser("~/.config/AviTradingSystem/main.duckdb")
TEMP_DB_PATH = "/tmp/main_copy_for_test.duckdb"
TEMP_WAL_PATH = "/tmp/main_copy_for_test.duckdb.wal"

# Копіюємо БД, щоб не заважати працюючому main.py
try:
    shutil.copy2(DB_PATH, TEMP_DB_PATH)
    if os.path.exists(DB_PATH + ".wal"):
        shutil.copy2(DB_PATH + ".wal", TEMP_WAL_PATH)
except Exception as e:
    print(f"Помилка копіювання БД: {e}")
    sys.exit(1)

def simulate_trades(df, asset_name):
    # Використовуємо нову логіку
    logic = CopilotAlgorithmicLogic(use_context_rules=True)
    trades = []
    
    # Потрібно мінімум 1000 свічок для нейромереж
    start_idx = 1000
    if len(df) <= start_idx:
        return []

    print(f"[{asset_name}] Симуляція {len(df) - start_idx} свічок...")
    
    for i in tqdm(range(start_idx, len(df) - 1)):
        window = df.iloc[i-1000:i+1]
        
        # Отримуємо сигнал
        result = logic.analyze_window(window)
        signal = result.get('signal')
        
        if signal in ['BUY', 'SELL']:
            next_candle = df.iloc[i+1]
            open_p = next_candle['open']
            close_p = next_candle['close']
            
            outcome = 'LOSS'
            if signal == 'BUY' and close_p > open_p:
                outcome = 'WIN'
            elif signal == 'SELL' and close_p < open_p:
                outcome = 'WIN'
                
            trades.append({
                'time': next_candle.get('timestamp', i),
                'asset': asset_name,
                'signal': signal,
                'result': outcome,
                'confidence': result.get('confidence', 0),
                'market_state': result.get('market_state', 'UNKNOWN')
            })
            
    return trades

def print_stats(trades_list, start_time, end_time):
    df = pd.DataFrame(trades_list)
    
    # Розрахунок торгового часу
    trading_time = "Невідомо"
    if start_time and end_time:
        try:
            duration = pd.to_datetime(end_time, unit='ms') - pd.to_datetime(start_time, unit='ms')
            trading_time = str(duration)
        except:
            pass
            
    print(f"Торговий час (вікно даних): {trading_time}")
    
    if df.empty:
        print("Жодної угоди не знайдено.")
        return
        
    wins = len(df[df['result'] == 'WIN'])
    losses = len(df[df['result'] == 'LOSS'])
    total = wins + losses
    wr = (wins / total * 100) if total > 0 else 0
    profit = wins * 8.20 - losses * 10.0
    pf = (wins * 8.20) / (losses * 10.0) if losses > 0 else float('inf')
    
    # Розрахунок просадки (Drawdown)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in df['result']:
        equity += 8.20 if r == 'WIN' else -10.0
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    
    print(f"Угод: {total} (W: {wins}, L: {losses})")
    print(f"Win Rate: {wr:.1f}%")
    print(f"Профіт: ${profit:.2f}")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Макс. Просадка: ${max_dd:.2f}")

try:
    con = duckdb.connect(TEMP_DB_PATH, read_only=True)
    tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
    
    target_assets = ['EURUSD_15m', 'EURGBP_15m', 'USDJPY_15m', 'AUDUSD_15m', 'USDCAD_15m', 'USDCHF_15m', 'NZDUSD_15m']
    all_trades = []
    
    global_start_t = None
    global_end_t = None
    
    for asset in target_assets:
        if asset in tables:
            print(f"\n--- Завантаження {asset} ---")
            # 3000 свічок = 1000 для контексту + 2000 для самого тесту
            df = con.execute(f'SELECT * FROM "{asset}" ORDER BY timestamp DESC LIMIT 1500').df()
            df = df.iloc[::-1].reset_index(drop=True)
            
            if 'open' not in df.columns or 'close' not in df.columns:
                print(f"У таблиці {asset} немає колонок open/close. Пропуск.")
                continue
                
            # РОЗРАХУНОК ІНДИКАТОРІВ
            print(f"[{asset}] Розрахунок індикаторів...")
            processed_df = df.copy()
            processor = IndicatorProcessor(data=df, processed_data=processed_df)
            df_with_indicators = processor.process_data()
                
            start_t = df_with_indicators.iloc[1000]['timestamp'] if len(df_with_indicators) > 1000 and 'timestamp' in df_with_indicators.columns else None
            end_t = df_with_indicators.iloc[-1]['timestamp'] if not df_with_indicators.empty and 'timestamp' in df_with_indicators.columns else None
            
            global_start_t = start_t
            global_end_t = end_t
                
            asset_trades = simulate_trades(df_with_indicators, asset)
            all_trades.extend(asset_trades)
            
            print(f"\nРезультат для {asset}:")
            print_stats(asset_trades, start_t, end_t)
        else:
            print(f"Таблицю {asset} не знайдено в БД.")
            
    print("\n====================================")
    print("ЗАГАЛЬНИЙ РЕЗУЛЬТАТ ПО 3 АКТИВАХ:")
    print("====================================")
    print_stats(all_trades, global_start_t, global_end_t)
    
finally:
    con.close()
    if os.path.exists(TEMP_DB_PATH):
        os.remove(TEMP_DB_PATH)
    if os.path.exists(TEMP_WAL_PATH):
        os.remove(TEMP_WAL_PATH)
