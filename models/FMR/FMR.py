import os
import torch
import pandas as pd
import numpy as np
from .ArchitectureNN import ArchitectureNN
from utils.OtherUtils import _handle_error

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
# Головний клас-класифікатор MR
#------------------------------

class FMR:
    "Класифікатор Ринкового Режиму (Market Regime)"

    #------------------------------
    # Ініціалізація класу
    #------------------------------
    def __init__(self):
        self.seq_len = 1000
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = ArchitectureNN(seq_len=self.seq_len).to(self.device)
        
        model_path = os.path.join(os.path.dirname(__file__), 'fmr_weights.pth')
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))
            self.model.eval()
        else:
            print("Попередження: Ваги MR моделі не знайдені.")

    #------------------------------
    # Обробка датасету
    #------------------------------

    @_handle_error
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        "Додає колонки ринкового режиму"
        if len(df) < self.seq_len:
            df['FMR_Trend'] = 0.0
            df['FMR_Flat'] = 0.0
            df['FMR_Explosion'] = 0.0
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

        df['FMR_Trend'] = 0.0
        df['FMR_Flat'] = 0.0
        df['FMR_Explosion'] = 0.0

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
            df.iloc[idx, df.columns.get_loc('FMR_Trend')] = round(float(out[0]), 3)
            df.iloc[idx, df.columns.get_loc('FMR_Flat')] = round(float(out[1]), 3)
            df.iloc[idx, df.columns.get_loc('FMR_Explosion')] = round(float(out[2]), 3)

        return df
