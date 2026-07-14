import os
import sys
import torch
import numpy as np
import pandas as pd
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

# Шляхи для імпортів
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Code'))
from utils.PathManager import PathManager
from utils.algorithms.indicators.PatternDetector import PatternDetector

sys.path.insert(0, os.path.dirname(__file__))
from ArchitectureNN import ArchitectureNN

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from unified_dataset import UnifiedDatasetFactory, ChunkedUnifiedDataset

TARGET_COLS = [
    'target_Hammer', 'target_Inverted_Hammer', 'target_Shooting_Star', 
    'target_Bullish_Engulfing', 'target_Bearish_Engulfing', 'target_Morning_Star', 
    'target_Evening_Star', 'target_Piercing_Pattern', 'target_Dark_Cloud_Cover', 
    'target_Three_White_Soldiers', 'target_Three_Black_Crows', 'target_Hanging_Man'
]

def label_pt_dataset(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Запуск PatternDetector
    detector = PatternDetector(data=df, processed_data=df)
    df = detector.process_data()
    
    # 2. Створюємо нові цільові колонки, ініціалізуємо нулями
    for col in TARGET_COLS:
        df[col] = 0.0
        
    # 3. Визначаємо успішність наступної свічки
    # Якщо наступна свічка закривається вище - це підтвердження для бичачого патерну
    next_close_higher = (df['close'].shift(-1) > df['close'])
    next_close_lower = (df['close'].shift(-1) < df['close'])
    
    # 4. Заповнюємо цілі (Target) лише якщо патерн алгоритмічно знайдено І він підтвердився
    
    # Бичачі патерни
    df.loc[(df.get('Hammer', 0) == 1) & next_close_higher, 'target_Hammer'] = 1.0
    df.loc[(df.get('Inverted_Hammer', 0) == 1) & next_close_higher, 'target_Inverted_Hammer'] = 1.0
    df.loc[(df.get('Engulfing', 0) == 1) & next_close_higher, 'target_Bullish_Engulfing'] = 1.0
    df.loc[(df.get('Morning_Star', 0) == 1) & next_close_higher, 'target_Morning_Star'] = 1.0
    df.loc[(df.get('Piercing_Pattern', 0) == 1) & next_close_higher, 'target_Piercing_Pattern'] = 1.0
    df.loc[(df.get('Three_White_Soldiers', 0) == 1) & next_close_higher, 'target_Three_White_Soldiers'] = 1.0
    
    # Ведмежі патерни
    df.loc[(df.get('Shooting_Star', 0) == 1) & next_close_lower, 'target_Shooting_Star'] = 1.0
    df.loc[(df.get('Engulfing', 0) == -1) & next_close_lower, 'target_Bearish_Engulfing'] = 1.0
    df.loc[(df.get('Evening_Star', 0) == 1) & next_close_lower, 'target_Evening_Star'] = 1.0
    df.loc[(df.get('Dark_Cloud_Cover', 0) == 1) & next_close_lower, 'target_Dark_Cloud_Cover'] = 1.0
    df.loc[(df.get('Three_Black_Crows', 0) == 1) & next_close_lower, 'target_Three_Black_Crows'] = 1.0
    df.loc[(df.get('Hanging_Man', 0) == 1) & next_close_lower, 'target_Hanging_Man'] = 1.0
    
    # Заповнюємо NaN на випадок відсутніх даних
    for col in TARGET_COLS:
        df[col] = df[col].fillna(0)
        
    return df

def train():
    db_path = PathManager.get_db_path()
    
    print(f"🚀 Ініціалізація Chunked Unified Dataset для PT (DuckDB: {db_path})")
    tables = UnifiedDatasetFactory.get_valid_tables(db_path, timeframes=['15m', '30m', '1h'])
    print(f"📚 Знайдено таблиць для навчання: {len(tables)}")
    
    if not tables:
        print("❌ Не знайдено підходящих таблиць!")
        return

    train_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=label_pt_dataset,
        target_cols=TARGET_COLS,
        split="train",
        seq_len=1000,
        augment_inversion=True,
        task_type="PT"
    )
    
    val_dataset = ChunkedUnifiedDataset(
        db_path=db_path,
        tables=tables,
        label_fn=label_pt_dataset,
        target_cols=TARGET_COLS,
        split="val",
        seq_len=1000,
        augment_inversion=True,
        task_type="PT"
    )

    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=False)
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"💻 Навчання на пристрої: {device}")
    
    model = ArchitectureNN(seq_len=1000).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    
    epochs = 15
    model_save_path = os.path.join(os.path.dirname(__file__), 'pt_weights.pth')
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
