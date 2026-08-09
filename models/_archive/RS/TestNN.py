import os
import sys
import gc
import torch
import numpy as np
import pandas as pd
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from scipy.signal import argrelextrema

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Code'))
from utils.PathManager import PathManager

sys.path.insert(0, os.path.dirname(__file__))
from ArchitectureNN import ArchitectureNN

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from UnifiedDataset import UnifiedDatasetFactory, ChunkedUnifiedDataset

WINDOW_SIZES = ArchitectureNN.WINDOW_SIZES  # [1000, 500, 200, 100, 50]

def compute_atr(df: pd.DataFrame, period=14) -> np.ndarray:
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    return pd.Series(tr).rolling(window=period).mean().values

def label_dataset(df: pd.DataFrame, order=5, fuzzy_n=20) -> pd.DataFrame:
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    open_ = df['open'].values
    n = len(df)

    local_max_idx = argrelextrema(high, np.greater, order=order)[0]
    local_min_idx = argrelextrema(low, np.less, order=order)[0]

    target_h_res = np.zeros(n)
    target_h_sup = np.zeros(n)

    for idx in local_max_idx:
        if idx + order < n:
            level_price = high[idx]
            if level_price <= 0:
                continue
            drop = level_price - np.min(low[idx: idx + order])
            target_h_res[idx] = drop / level_price

    for idx in local_min_idx:
        if idx + order < n:
            level_price = low[idx]
            if level_price <= 0:
                continue
            rise = np.max(high[idx: idx + order]) - level_price
            target_h_sup[idx] = rise / level_price

    max_res = np.max(target_h_res) if np.max(target_h_res) > 0 else 1.0
    max_sup = np.max(target_h_sup) if np.max(target_h_sup) > 0 else 1.0
    target_h_res = np.where(target_h_res > 0, (target_h_res / max_res) * 0.8 + 0.2, 0)
    target_h_sup = np.where(target_h_sup > 0, (target_h_sup / max_sup) * 0.8 + 0.2, 0)

    ema20 = pd.Series(close).ewm(span=20, adjust=False).mean().values
    ema_slope = pd.Series(ema20).diff(20).values
    atr14 = compute_atr(df, period=14)
    body_tol = pd.Series(np.abs(close - open_)).rolling(window=fuzzy_n).mean().fillna(0).values

    target_t_res = np.zeros(n)
    target_t_sup = np.zeros(n)

    for i in range(30, n - order):
        atr_val = atr14[i]
        if not np.isfinite(atr_val) or atr_val <= 0:
            continue
        tol = max(body_tol[i], 1e-9)

        if ema_slope[i] > 0 and abs(low[i] - ema20[i]) <= tol and close[i] > open_[i]:
            rise = np.max(high[i + 1: i + 1 + order]) - close[i]
            if rise > 0:
                target_t_sup[i] = rise / atr_val

        if ema_slope[i] < 0 and abs(high[i] - ema20[i]) <= tol and close[i] < open_[i]:
            drop = close[i] - np.min(low[i + 1: i + 1 + order])
            if drop > 0:
                target_t_res[i] = drop / atr_val

    max_t_res = np.max(target_t_res) if np.max(target_t_res) > 0 else 1.0
    max_t_sup = np.max(target_t_sup) if np.max(target_t_sup) > 0 else 1.0
    target_t_res = np.where(target_t_res > 0, (target_t_res / max_t_res) * 0.8 + 0.2, 0)
    target_t_sup = np.where(target_t_sup > 0, (target_t_sup / max_t_sup) * 0.8 + 0.2, 0)

    df['target_h_res'] = target_h_res
    df['target_h_sup'] = target_h_sup
    df['target_t_res'] = target_t_res
    df['target_t_sup'] = target_t_sup
    return df

def train():
    db_path = PathManager.get_db_path()
    
    print(f"🚀 Ініціалізація Chunked Unified Dataset для RS (DuckDB: {db_path})")
    tables = UnifiedDatasetFactory.get_valid_tables(db_path, timeframes=['15m', '30m', '1h'])
    print(f"📚 Знайдено таблиць для навчання: {len(tables)}")
    
    if not tables:
        print("❌ Не знайдено підходящих таблиць!")
        return

    train_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=lambda df: label_dataset(df, order=5, fuzzy_n=20),
        target_cols=['target_h_res', 'target_h_sup', 'target_t_res', 'target_t_sup'],
        split="train",
        seq_len=1000,
        augment_inversion=True,
        task_type="RS"
    )
    
    val_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=lambda df: label_dataset(df, order=5, fuzzy_n=20),
        target_cols=['target_h_res', 'target_h_sup', 'target_t_res', 'target_t_sup'],
        split="val",
        seq_len=1000,
        augment_inversion=True,
        task_type="RS"
    )

    train_loader = DataLoader(train_dataset, batch_size=128, shuffle=False)
    val_loader = DataLoader(val_dataset, batch_size=128, shuffle=False)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"💻 Навчання на пристрої: {device}")
    
    model = ArchitectureNN().to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    
    epochs = 20
    model_save_path = os.path.join(os.path.dirname(__file__), 'rs_weights.pth')
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
            # Dynamic slicing for RS architecture
            batch_windows = [batch_X[:, -w:, :].to(device) for w in WINDOW_SIZES]
            batch_y = batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_windows)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            total_train_loss += loss.item()
            train_batches += 1
            
            if train_batches % 100 == 0:
                print(f"  Батч {train_batches} | Поточний Loss: {loss.item():.5f}")
                
        if train_batches == 0:
            print("❌ Жодного батчу не було завантажено. Перевірте датасет.")
            break
            
        train_loss = total_train_loss / train_batches
        
        model.eval()
        total_val_loss = 0.0
        val_batches = 0
        
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_windows = [batch_X[:, -w:, :].to(device) for w in WINDOW_SIZES]
                batch_y = batch_y.to(device)
                
                val_outputs = model(batch_windows)
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
