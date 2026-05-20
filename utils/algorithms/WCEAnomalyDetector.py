import pandas as pd
import numpy as np

class WCEAnomalyDetector:
    """
    Алгоритм для відстеження 'ефекту розтягнутої гумки' (аномалії) на базі WCE.
    Рівень аномальності: |body - 5| + |shadow - 5| + |scale - 5|
    
    Вхід (Сигнал): 
    - Аномальність зростала і досягла піку >= peak_threshold
    - У перший момент зниження аномальності генерується сигнал:
      - 1 (BUY), якщо аномалія була на S-токені (ведмежа свічка)
      - -1 (SELL), якщо аномалія була на B-токені (бичача свічка)
      
    Вихід (Зняття сигналу):
    - Аномальність падає до <= norm_threshold (сигнал стає 0).
    """
    
    def __init__(self, df: pd.DataFrame, wce_col: str, peak_threshold: int = 6, norm_threshold: int = 3):
        self.df = df
        self.wce_col = wce_col
        self.peak_threshold = peak_threshold
        self.norm_threshold = norm_threshold

    def calculate(self) -> pd.Series:
        if self.wce_col not in self.df.columns:
            return pd.Series(0, index=self.df.index)
            
        wce_tokens = self.df[self.wce_col].astype(str)
        signals = np.zeros(len(self.df), dtype=int)
        
        anomalies = []
        token_types = []
        for token in wce_tokens:
            if token == 'nan' or len(token) < 4 or token.startswith('N'):
                anomalies.append(0)
                token_types.append('N')
                continue
                
            ttype = token[0]
            try:
                b = int(token[1])
                s = int(token[2])
                sc = int(token[3])
                anomaly = abs(b - 5) + abs(s - 5) + abs(sc - 5)
                anomalies.append(anomaly)
                token_types.append(ttype)
            except:
                anomalies.append(0)
                token_types.append('N')
                
        anomalies = np.array(anomalies)
        token_types = np.array(token_types)
        
        current_state = 0
        current_peak = 0
        peak_ttype = 'N'
        
        for i in range(1, len(anomalies)):
            anomaly = anomalies[i]
            prev_anomaly = anomalies[i-1]
            ttype = token_types[i]
            
            if current_state == 0:
                if anomaly > prev_anomaly:
                    if anomaly >= self.peak_threshold and current_peak < self.peak_threshold:
                        peak_ttype = ttype
                    current_peak = anomaly
                elif anomaly < prev_anomaly:
                    if current_peak >= self.peak_threshold:
                        if peak_ttype == 'S':
                            current_state = 1
                        elif peak_ttype == 'B':
                            current_state = -1
                    else:
                        current_peak = anomaly
                        peak_ttype = 'N'
            
            elif current_state != 0:
                if anomaly <= self.norm_threshold:
                    current_state = 0
                    current_peak = 0
                    peak_ttype = 'N'
                    
            signals[i] = current_state
            
        return pd.Series(signals, index=self.df.index)
