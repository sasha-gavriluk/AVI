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
                v = int(token[4]) if len(token) > 4 else 5 # Зворотна сумісність
                anomaly = abs(b - 5) + abs(s - 5) + abs(sc - 5) + abs(v - 5)
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

class WCETrendExhaustionDetector:
    """
    Алгоритм для відстеження 'параболічного виснаження' на базі WCE.
    Накопичує аномальність поспіль йдучих свічок одного напрямку, якщо їхня аномальність > norm_threshold.
    
    Вхід (Сигнал): 
    - Кумулятивна аномальність зростала і досягла піку >= peak_threshold
    - У перший момент переривання серії (зміна напрямку або падіння аномальності) генерується сигнал:
      - 1 (BUY), якщо парабола була на S-токенах (ведмежа серія)
      - -1 (SELL), якщо парабола була на B-токенах (бичача серія)
      
    Вихід (Зняття сигналу):
    - Кумулятивна аномальність падає до <= norm_threshold (сигнал стає 0).
    """
    
    def __init__(self, df: pd.DataFrame, wce_col: str, peak_threshold: int = 15, norm_threshold: int = 3):
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
                v = int(token[4]) if len(token) > 4 else 5
                anomaly = abs(b - 5) + abs(s - 5) + abs(sc - 5) + abs(v - 5)
                anomalies.append(anomaly)
                token_types.append(ttype)
            except:
                anomalies.append(0)
                token_types.append('N')
                
        anomalies = np.array(anomalies)
        token_types = np.array(token_types)
        
        # Обчислення кумулятивної аномалії
        cum_anomalies = np.zeros_like(anomalies)
        for i in range(len(anomalies)):
            if anomalies[i] <= self.norm_threshold:
                cum_anomalies[i] = anomalies[i]
            elif i > 0 and token_types[i] == token_types[i-1] and anomalies[i-1] > self.norm_threshold:
                cum_anomalies[i] = cum_anomalies[i-1] + anomalies[i]
            else:
                cum_anomalies[i] = anomalies[i]
        
        current_state = 0
        current_peak = 0
        peak_ttype = 'N'
        
        for i in range(1, len(cum_anomalies)):
            cum_anomaly = cum_anomalies[i]
            prev_cum_anomaly = cum_anomalies[i-1]
            ttype = token_types[i]
            prev_ttype = token_types[i-1]
            
            if current_state == 0:
                if cum_anomaly > prev_cum_anomaly:
                    if cum_anomaly >= self.peak_threshold and current_peak < self.peak_threshold:
                        peak_ttype = ttype
                    current_peak = cum_anomaly
                elif cum_anomaly < prev_cum_anomaly or ttype != prev_ttype:
                    if current_peak >= self.peak_threshold:
                        if peak_ttype == 'S':
                            current_state = 1
                        elif peak_ttype == 'B':
                            current_state = -1
                    else:
                        current_peak = cum_anomaly
                        peak_ttype = 'N'
            
            elif current_state != 0:
                if cum_anomaly <= self.norm_threshold:
                    current_state = 0
                    current_peak = 0
                    peak_ttype = 'N'
                    
            signals[i] = current_state
            
        return pd.Series(signals, index=self.df.index)
