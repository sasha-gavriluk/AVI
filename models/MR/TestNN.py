import os
import sys
import torch
import numpy as np
import pandas as pd
import pandas_ta as ta
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Code'))
from utils.PathManager import PathManager

sys.path.insert(0, os.path.dirname(__file__))
from ArchitectureNN import ArchitectureNN

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from UnifiedDataset import UnifiedDatasetFactory, ChunkedUnifiedDataset

def label_mr_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df.ta.adx(length=14, append=True)
    df.ta.ema(length=20, append=True)
    df.ta.bbands(length=20, append=True)
    df.ta.atr(length=14, append=True)
    
    df.bfill(inplace=True)
    df.fillna(0, inplace=True)
    
    adx_col = [c for c in df.columns if c.startswith('ADX_')][0]
    bbb_col = [c for c in df.columns if c.startswith('BBB_')][0]
    atr_col = [c for c in df.columns if c.startswith('ATR')][0]
    
    adx = np.nan_to_num(df[adx_col].values)
    bbb = np.nan_to_num(df[bbb_col].values)
    atr = np.nan_to_num(df[atr_col].values)
    
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    
    n = len(df)
    target_trend = np.zeros(n)
    target_flat = np.zeros(n)
    target_explosion = np.zeros(n)
    
    for i in range(30, n - 15):
        if np.mean(adx[i-20:i]) > 25 and adx[i] > 30:
            target_trend[i] = 1.0
            
        if np.mean(adx[i-30:i]) < 20 and adx[i] < 15:
            target_flat[i] = 1.0
            
        is_squeezing = bbb[i] < bbb[i-5] and bbb[i-5] < bbb[i-10] and atr[i] < atr[i-10]
        if is_squeezing:
            future_high = np.max(high[i+1 : i+16])
            future_low = np.min(low[i+1 : i+16])
            future_range = future_high - future_low
            
            if future_range > 2.5 * atr[i]:
                target_explosion[i] = 1.0
                
    df['target_trend'] = target_trend
    df['target_flat'] = target_flat
    df['target_explosion'] = target_explosion
    return df

def train():
    db_path = PathManager.get_db_path()
    
    print(f"🚀 Ініціалізація Chunked Unified Dataset для MR (DuckDB: {db_path})")
    tables = UnifiedDatasetFactory.get_valid_tables(db_path, timeframes=['15m', '30m', '1h'])
    print(f"📚 Знайдено таблиць для навчання: {len(tables)}")
    
    if not tables:
        print("❌ Не знайдено підходящих таблиць!")
        return

    train_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=label_mr_dataset,
        target_cols=['target_trend', 'target_flat', 'target_explosion'],
        split="train",
        seq_len=1000,
        augment_inversion=True,
        task_type="MR"
    )
    
    val_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=label_mr_dataset,
        target_cols=['target_trend', 'target_flat', 'target_explosion'],
        split="val",
        seq_len=1000,
        augment_inversion=True,
        task_type="MR"
    )

    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=False)
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"💻 Навчання на пристрої: {device}")
    
    model = ArchitectureNN(seq_len=1000).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    
    epochs = 15
    model_save_path = os.path.join(os.path.dirname(__file__), 'mr_weights.pth')
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
