import os
import torch
import pandas as pd
import numpy as np
from .ArchitectureNN import ArchitectureNN
from utils.other_utils import _handle_error

#------------------------------
# Обчислення ATR
#------------------------------

def _compute_atr(df: pd.DataFrame, period=14) -> np.ndarray:
    "ATR(period), та сама формула, що й IndicatorProcessor.add_atr / TestNN.py"
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    return pd.Series(tr).rolling(window=period).mean().values

#------------------------------
# Головний клас-класифікатор PT
#------------------------------

class FPT:
    "Класифікатор Патернів (Pattern Recognition)"

    #------------------------------
    # Ініціалізація класу
    #------------------------------
    def __init__(self):
        self.seq_len = 1000
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = ArchitectureNN(seq_len=self.seq_len).to(self.device)
        
        model_path = os.path.join(os.path.dirname(__file__), 'fpt_weights.pth')
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))
            self.model.eval()
        else:
            print("Попередження: Ваги PT моделі не знайдені.")

        self.pattern_names = [
            'FPT_Hammer', 'FPT_Inverted_Hammer', 'FPT_Shooting_Star', 
            'FPT_Engulfing_Bullish', 'FPT_Engulfing_Bearish', 'FPT_Morning_Star', 
            'FPT_Evening_Star', 'FPT_Piercing_Pattern', 'FPT_Dark_Cloud_Cover', 
            'FPT_Three_White_Soldiers', 'FPT_Three_Black_Crows', 'FPT_Hanging_Man'
        ]

    #------------------------------
    # Обробка датасету
    #------------------------------

    @_handle_error
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        "Додає колонки з ймовірностями для свічкових патернів"
        for p in self.pattern_names:
            df[p] = 0.0

        if len(df) < self.seq_len:
            return df

        prices = df[['open', 'high', 'low', 'close']].values
        
        vol_col = 'volume' if 'volume' in df.columns else 'tick_volume'
        if vol_col in df.columns:
            volumes = df[[vol_col]].values
        else:
            volumes = np.zeros((len(df), 1))

        atr = _compute_atr(df, period=14)
        windows = []
        indices = []

        for i in range(self.seq_len, len(df) + 1):
            window_prices = prices[i - self.seq_len : i]
            window_vols = volumes[i - self.seq_len : i]

            base_price = window_prices[-1, 3]
            atr_val = atr[i - 1]
            if base_price == 0 or not np.isfinite(atr_val) or atr_val <= 0:
                continue

            norm_prices = (window_prices - base_price) / atr_val
            max_vol = np.max(window_vols)
            norm_vols = window_vols / max_vol if max_vol > 0 else np.zeros_like(window_vols)
            
            window_X = np.concatenate([norm_prices, norm_vols], axis=1)
            windows.append(window_X)
            indices.append(i - 1)

        if not windows:
            return df
            
        outputs_list = []
        batch_size = 64
        with torch.no_grad():
            for i in range(0, len(windows), batch_size):
                batch_X = torch.tensor(np.array(windows[i:i+batch_size]), dtype=torch.float32).to(self.device)
                batch_out = self.model(batch_X).cpu().numpy()
                outputs_list.append(batch_out)
        
        outputs = np.concatenate(outputs_list, axis=0)
            
        for idx, out in zip(indices, outputs):
            for p_idx, p_name in enumerate(self.pattern_names):
                df.iloc[idx, df.columns.get_loc(p_name)] = round(float(out[p_idx]), 3)

        return df
