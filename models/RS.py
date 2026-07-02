import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from ArchitectureRS import ArchitectureNN
import torch
import numpy as np
import pandas as pd

WINDOW_SIZES = ArchitectureNN.WINDOW_SIZES  # [1000, 500, 200, 100, 50]


def _compute_atr(df: pd.DataFrame, period=14) -> np.ndarray:
    """ATR(period), та сама формула, що й IndicatorProcessor.add_atr / TestNN.py."""
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    return pd.Series(tr).rolling(window=period).mean().values


class RS:
    """
    Мультивіконний модуль рівнів (Фаза Б). Приймає сирий датасет, для кожної
    свічки будує 5 вікон (1000/500/200/100/50) і повертає датасет з колонками
    Resistance/Support (горизонтальні) та TrendResistance/TrendSupport (трендові).
    """
    def __init__(self):
        self.seq_len = max(WINDOW_SIZES)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = ArchitectureNN().to(self.device)

        model_path = os.path.join(os.path.dirname(__file__), 'rs_weights.pth')
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))

        self.model.eval()

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Аналізує датасет і додає колонки Resistance/Support/TrendResistance/TrendSupport (0..1)."""
        df['Resistance'] = 0.0
        df['Support'] = 0.0
        df['TrendResistance'] = 0.0
        df['TrendSupport'] = 0.0

        if len(df) < self.seq_len:
            return df

        prices = df[['open', 'high', 'low', 'close']].values
        volumes = df[['volume']].values
        atr = _compute_atr(df, period=14)

        indices = []
        windows_by_size = {w: [] for w in WINDOW_SIZES}

        for i in range(self.seq_len, len(df) + 1):
            base_price = prices[i - 1, 3]
            atr_val = atr[i - 1]
            if base_price == 0 or not np.isfinite(atr_val) or atr_val <= 0:
                continue

            for w in WINDOW_SIZES:
                wp = prices[i - w: i]
                wv = volumes[i - w: i]
                norm_p = (wp - base_price) / atr_val
                max_vol = np.max(wv)
                norm_v = wv / max_vol if max_vol > 0 else np.zeros_like(wv)
                windows_by_size[w].append(np.concatenate([norm_p, norm_v], axis=1))

            indices.append(i - 1)

        if not indices:
            return df

        outputs_list = []
        batch_size = 64
        with torch.no_grad():
            for start in range(0, len(indices), batch_size):
                end = min(start + batch_size, len(indices))
                batch_windows = [
                    torch.tensor(np.array(windows_by_size[w][start:end]), dtype=torch.float32).to(self.device)
                    for w in WINDOW_SIZES
                ]
                batch_out = self.model(batch_windows).cpu().numpy()
                outputs_list.append(batch_out)

        outputs = np.concatenate(outputs_list, axis=0)

        for idx, out in zip(indices, outputs):
            h_res, h_sup, t_res, t_sup = (round(float(v), 3) for v in out)
            df.iloc[idx, df.columns.get_loc('Resistance')] = h_res if h_res > 0.1 else 0.0
            df.iloc[idx, df.columns.get_loc('Support')] = h_sup if h_sup > 0.1 else 0.0
            df.iloc[idx, df.columns.get_loc('TrendResistance')] = t_res if t_res > 0.1 else 0.0
            df.iloc[idx, df.columns.get_loc('TrendSupport')] = t_sup if t_sup > 0.1 else 0.0

        return df
