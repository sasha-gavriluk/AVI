import os
import sys
import torch
import numpy as np
import pandas as pd
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from scipy.signal import argrelextrema

# Add Code to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Code'))
from utils.PathManager import PathManager

# Add current dir (FB) to path
sys.path.insert(0, os.path.dirname(__file__))
from ArchitectureNN import ArchitectureNN

# Add AI_Lab to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from unified_dataset import UnifiedDatasetFactory, ChunkedUnifiedDataset

def label_fb_dataset(df: pd.DataFrame, order=5) -> pd.DataFrame:
    prices_high = df['high'].values
    prices_low = df['low'].values
    prices_close = df['close'].values
    
    target_bull = np.zeros(len(df))
    target_bear = np.zeros(len(df))
    
    local_min_idx = argrelextrema(prices_low, np.less, order=order)[0]
    local_max_idx = argrelextrema(prices_high, np.greater, order=order)[0]
    
    for i in range(order, len(df) - 1): # -1 to have the next candle
        past_mins = local_min_idx[local_min_idx < i - 5]
        if len(past_mins) > 0:
            last_min_idx = past_mins[-1]
            support_level = prices_low[last_min_idx]
            if prices_low[i] < support_level and prices_close[i] > support_level:
                # BO expiration: next candle must close higher
                if prices_close[i+1] > prices_close[i]:
                    target_bull[i] = 1.0
                    
        past_maxs = local_max_idx[local_max_idx < i - 5]
        if len(past_maxs) > 0:
            last_max_idx = past_maxs[-1]
            resistance_level = prices_high[last_max_idx]
            if prices_high[i] > resistance_level and prices_close[i] < resistance_level:
                # BO expiration: next candle must close lower
                if prices_close[i+1] < prices_close[i]:
                    target_bear[i] = 1.0
    
    df['target_bull'] = target_bull
    df['target_bear'] = target_bear
    return df

def train():
    db_path = PathManager.get_db_path()
    
    print(f"🚀 Ініціалізація Chunked Unified Dataset (DuckDB: {db_path})")
    tables = UnifiedDatasetFactory.get_valid_tables(db_path, timeframes=['15m', '30m', '1h'])
    print(f"📚 Знайдено таблиць для навчання: {len(tables)}")
    
    if not tables:
        print("❌ Не знайдено підходящих таблиць!")
        return

    # Ініціалізація IterableDataset для Train та Val
    train_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=lambda df: label_fb_dataset(df, order=5),
        target_cols=['target_bull', 'target_bear'],
        split="train",
        seq_len=1000,
        augment_inversion=True,
        task_type="FB"
    )
    
    val_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=lambda df: label_fb_dataset(df, order=5),
        target_cols=['target_bull', 'target_bear'],
        split="val",
        seq_len=1000,
        augment_inversion=True,
        task_type="FB"
    )

    # IterableDataset НЕ підтримує shuffle=True у DataLoader
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=False)
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"💻 Навчання на пристрої: {device}")
    
    model = ArchitectureNN(seq_len=1000).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    
    epochs = 15
    model_save_path = os.path.join(os.path.dirname(__file__), 'fb_weights.pth')
    criterion = nn.BCELoss()
    
    best_val_loss = float('inf')
    patience = 5
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        total_train_loss = 0.0
        train_batches = 0
        
        print(f"\n--- Епоха [{epoch+1}/{epochs}] ---")
        
        for batch_idx, (batch_X, batch_y) in enumerate(train_loader):
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            total_train_loss += loss.item()
            train_batches += 1
            
            # Лог кожні 100 батчів
            if train_batches % 100 == 0:
                print(f"  Батч {train_batches} | Поточний Loss: {loss.item():.5f}")
                
        if train_batches == 0:
            print("❌ Жодного батчу не було завантажено. Перевірте датасет.")
            break
            
        train_loss = total_train_loss / train_batches
        
        # Validation
        model.eval()
        total_val_loss = 0.0
        val_batches = 0
        
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                val_outputs = model(batch_X)
                v_loss = criterion(val_outputs, batch_y)
                total_val_loss += v_loss.item()
                val_batches += 1
                
        val_loss = total_val_loss / max(1, val_batches)
            
        print(f"Підсумок Епохи [{epoch+1}/{epochs}] | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Батчів Train: {train_batches}, Val: {val_batches}")
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), model_save_path)
            print(f"  🌟 Збережено нову найкращу модель!")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"⏹️ Early Stopping на епосі {epoch+1}")
                break

    print(f"🎉 Навчання завершено. Найкраща валідаційна помилка: {best_val_loss:.5f}")

if __name__ == "__main__":
    train()
