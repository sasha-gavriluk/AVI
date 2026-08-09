import os
import gc
import duckdb
import numpy as np
import pandas as pd
import torch
from torch.utils.data import IterableDataset

class UnifiedDatasetFactory:
    """Фабрика для отримання списку таблиць з DuckDB."""
    @staticmethod
    def get_valid_tables(db_path, timeframes=None):
        con = duckdb.connect(db_path, read_only=True)
        tables_query = con.execute("SHOW TABLES;").df()
        all_tables = tables_query['name'].tolist()
        con.close()
        
        valid_tables = []
        for t in all_tables:
            if t in ['copilot_memory'] or t.startswith('sqlite_'):
                continue
            if t.startswith('BTC') or t.startswith('ETH'):
                continue
            if timeframes:
                if not any(t.endswith(f"_{tf}") for tf in timeframes):
                    continue
            valid_tables.append(t)
        return valid_tables

class ChunkedUnifiedDataset(IterableDataset):
    """
    Датасет, який зчитує дані таблиця-за-таблицею (Chunked), 
    зберігаючи RAM. Успадковує IterableDataset.
    """
    def __init__(self, db_path, tables, label_fn, target_cols, split="train", seq_len=1000, augment_inversion=True, task_type="FB"):
        super().__init__()
        self.db_path = db_path
        self.tables = tables
        self.label_fn = label_fn
        self.target_cols = target_cols
        self.split = split
        self.seq_len = seq_len
        self.augment_inversion = augment_inversion
        self.task_type = task_type

    def compute_atr(self, df: pd.DataFrame, period=14) -> np.ndarray:
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
        return pd.Series(tr).rolling(window=period).mean().values

    def __iter__(self):
        worker_info = torch.utils.data.get_worker_info()
        # Якщо використовується num_workers > 0 в DataLoader
        if worker_info is not None:
            per_worker = int(np.ceil(len(self.tables) / float(worker_info.num_workers)))
            worker_id = worker_info.id
            iter_tables = self.tables[worker_id * per_worker : (worker_id + 1) * per_worker]
        else:
            iter_tables = self.tables.copy()

        # Випадковий порядок таблиць для тренування на кожній епосі
        if self.split == "train":
            np.random.shuffle(iter_tables)

        con = duckdb.connect(self.db_path, read_only=True)

        for table in iter_tables:
            query = f'SELECT open, high, low, close, volume FROM "{table}" ORDER BY timestamp ASC'
            try:
                df = con.execute(query).df()
            except Exception as e:
                continue
                
            if len(df) < self.seq_len * 2:
                continue
                
            df = self.label_fn(df)
            if not all(col in df.columns for col in self.target_cols):
                continue

            prices = df[['open', 'high', 'low', 'close']].values
            volumes = df[['volume']].values
            atr = self.compute_atr(df, period=14)
            targets = df[self.target_cols].values 
            
            is_positive = np.any(targets > 0, axis=1)
            pos_indices = np.where(is_positive)[0]
            pos_indices = pos_indices[pos_indices >= self.seq_len]
            neg_indices = np.where(~is_positive)[0]
            neg_indices = neg_indices[neg_indices >= self.seq_len]
            
            # --- ВАЖЛИВО: Жорсткий хронологічний спліт (Data Leakage Prevention) ---
            # Тренування тільки на перших 80% часу, валідація - тільки на останніх 20%
            split_idx = int(len(df) * 0.8)
            
            if self.split == "train":
                pos_indices = pos_indices[pos_indices < split_idx]
                neg_indices = neg_indices[neg_indices < split_idx]
            else:
                pos_indices = pos_indices[pos_indices >= split_idx]
                neg_indices = neg_indices[neg_indices >= split_idx]
                
            state = np.random.get_state()
            np.random.seed(int(abs(hash(table)) % (2**32 - 1))) 
            
            if len(pos_indices) > 0:
                np.random.shuffle(neg_indices)
                neg_indices = neg_indices[:len(pos_indices) * 3]
                
            indices_to_use = np.concatenate([pos_indices, neg_indices])
                
            # Повертаємо стан генератора для подальшого незалежного шафлу
            np.random.set_state(state)
            
            if self.split == "train":
                np.random.shuffle(indices_to_use)
            
            for i in indices_to_use:
                start_idx = i - self.seq_len + 1
                if start_idx < 0:
                    continue
                    
                window_prices = prices[start_idx : i + 1]
                base_price = window_prices[-1, 3] 
                atr_val = atr[i]
                
                if base_price == 0 or not np.isfinite(atr_val) or atr_val <= 0:
                    continue
                    
                norm_prices = (window_prices - base_price) / atr_val
                window_vols = volumes[start_idx : i + 1]
                max_vol = np.max(window_vols)
                norm_vols = window_vols / max_vol if max_vol > 0 else np.zeros_like(window_vols)
                
                window_X = np.concatenate([norm_prices, norm_vols], axis=1)
                window_y = targets[i]
                
                yield torch.tensor(window_X, dtype=torch.float32), torch.tensor(window_y, dtype=torch.float32)
                
                if self.augment_inversion:
                    inv_prices = -norm_prices
                    inv_prices[:, [1, 2]] = inv_prices[:, [2, 1]]
                    inv_window_X = np.concatenate([inv_prices, norm_vols], axis=1)
                    
                    inv_window_y = window_y.copy()
                    if self.task_type == "FB" and len(self.target_cols) >= 2:
                        inv_window_y[0], inv_window_y[1] = inv_window_y[1], inv_window_y[0]

                    elif self.task_type == "PT" and len(self.target_cols) == 12:
                        inv_window_y[0], inv_window_y[2] = inv_window_y[2], inv_window_y[0]
                        inv_window_y[1], inv_window_y[11] = inv_window_y[11], inv_window_y[1]
                        inv_window_y[3], inv_window_y[4] = inv_window_y[4], inv_window_y[3]
                        inv_window_y[5], inv_window_y[6] = inv_window_y[6], inv_window_y[5]
                        inv_window_y[7], inv_window_y[8] = inv_window_y[8], inv_window_y[7]
                        inv_window_y[9], inv_window_y[10] = inv_window_y[10], inv_window_y[9]
                        
                    yield torch.tensor(inv_window_X, dtype=torch.float32), torch.tensor(inv_window_y, dtype=torch.float32)

            del df, prices, volumes, atr, targets
            gc.collect()

        con.close()
