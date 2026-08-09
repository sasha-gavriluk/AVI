import pandas as pd
import sys
import os

# Додаємо корінь проєкту
sys.path.append(os.path.abspath('.'))

from utils.algorithms.FCryptoLogic import FCryptoLogic
from utils.DataBaseManager import DataBaseManager

def main():
    db = DataBaseManager(use_default=True)
    df = db.get_data_as_dataframe('BTCUSDT_15m')
    if df is None or df.empty:
        print("No data for BTCUSDT_15m")
        return
    
    # Беремо останні 2000 свічок
    df = df.tail(2000).copy().reset_index(drop=True)
    
    logic = FCryptoLogic(df)
    logic.df_processed = logic._enrich_data()
    
    results = logic.engine.process_dataframe(logic.df_processed)
    
    df['signal'] = results['signal']
    df['block_reason'] = results['block_reason']
    
    print("\nSummary of Block Reasons:")
    print(df['block_reason'].value_counts())
    
    print("\nTotal Signals:")
    print(df['signal'].value_counts())

if __name__ == '__main__':
    main()
