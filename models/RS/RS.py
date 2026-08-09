import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from utils.OtherUtils import _handle_error

class RS:
    "Детермінований індикатор зон (Контекст). Шукає зони підтримки/опору на основі минулих екстремумів."
    
    def __init__(self):
        self.order = 5
        self.max_age = 750
        
    def _compute_atr(self, df: pd.DataFrame, period=14) -> np.ndarray:
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
        return pd.Series(tr).rolling(window=period).mean().values

    @_handle_error
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Ініціалізація вихідних колонок
        df['RS_res_proximity'] = 0.0
        df['RS_res_strength'] = 0.0
        df['RS_sup_proximity'] = 0.0
        df['RS_sup_strength'] = 0.0
        
        if len(df) < self.order * 2:
            return df
            
        atr = self._compute_atr(df, period=14)
        highs = df['high'].values
        lows = df['low'].values
        
        # Знаходимо всі локальні максимуми та мінімуми заздалегідь
        # order=5: точка є екстремумом, якщо вона більша/менша за 5 сусідів з обох боків
        res_peaks = argrelextrema(highs, np.greater, order=self.order)[0]
        sup_troughs = argrelextrema(lows, np.less, order=self.order)[0]
        
        # Екстремум на індексі i підтверджується ТІЛЬКИ на свічці i + order
        confirmed_res = {}
        for p in res_peaks:
            confirmed_res[p + self.order] = highs[p]
            
        confirmed_sup = {}
        for t in sup_troughs:
            confirmed_sup[t + self.order] = lows[t]
            
        active_res_zones = []
        active_sup_zones = []
        
        res_prox_arr = np.zeros(len(df))
        res_str_arr = np.zeros(len(df))
        sup_prox_arr = np.zeros(len(df))
        sup_str_arr = np.zeros(len(df))
        
        for i in range(len(df)):
            current_atr = atr[i]
            if not np.isfinite(current_atr) or current_atr <= 0:
                continue
                
            # 1. Старіння зон
            active_res_zones = [z for z in active_res_zones if i - z['last_update'] <= self.max_age]
            active_sup_zones = [z for z in active_sup_zones if i - z['last_update'] <= self.max_age]
            
            # 2. Додавання нових екстремумів
            if i in confirmed_res:
                peak_price = confirmed_res[i]
                merged = False
                for z in active_res_zones:
                    if abs(peak_price - z['center']) < 1.0 * z['atr_creation']:
                        z['touches'] += 1
                        z['min_ext'] = min(z['min_ext'], peak_price)
                        z['max_ext'] = max(z['max_ext'], peak_price)
                        z['center'] = (z['min_ext'] + z['max_ext']) / 2.0
                        z['last_update'] = i
                        merged = True
                        break
                if not merged:
                    active_res_zones.append({
                        'center': peak_price, 'min_ext': peak_price, 'max_ext': peak_price,
                        'touches': 1, 'atr_creation': atr[i - self.order], 'last_update': i
                    })
                    
            if i in confirmed_sup:
                trough_price = confirmed_sup[i]
                merged = False
                for z in active_sup_zones:
                    if abs(trough_price - z['center']) < 1.0 * z['atr_creation']:
                        z['touches'] += 1
                        z['min_ext'] = min(z['min_ext'], trough_price)
                        z['max_ext'] = max(z['max_ext'], trough_price)
                        z['center'] = (z['min_ext'] + z['max_ext']) / 2.0
                        z['last_update'] = i
                        merged = True
                        break
                if not merged:
                    active_sup_zones.append({
                        'center': trough_price, 'min_ext': trough_price, 'max_ext': trough_price,
                        'touches': 1, 'atr_creation': atr[i - self.order], 'last_update': i
                    })
            
            # 3. Обчислення proximity та strength
            current_high = highs[i]
            current_low = lows[i]
            
            best_res_prox = 0.0
            best_res_str = 0.0
            for z in active_res_zones:
                spread = z['max_ext'] - z['min_ext']
                half_width = max(spread / 2.0, 0.3 * current_atr)
                upper = z['center'] + half_width
                lower = z['center'] - half_width
                
                if lower <= current_high <= upper:
                    d = 0.0
                else:
                    d = min(abs(current_high - upper), abs(current_high - lower))
                
                prox = np.exp(-d / (0.75 * current_atr))
                strg = (1.0 - np.exp(-z['touches'] / 4.0)) * 1.0
                
                if prox > best_res_prox:
                    best_res_prox = prox
                    best_res_str = strg
                    
            res_prox_arr[i] = round(best_res_prox, 3)
            res_str_arr[i] = round(best_res_str, 3)
            
            best_sup_prox = 0.0
            best_sup_str = 0.0
            for z in active_sup_zones:
                spread = z['max_ext'] - z['min_ext']
                half_width = max(spread / 2.0, 0.3 * current_atr)
                upper = z['center'] + half_width
                lower = z['center'] - half_width
                
                if lower <= current_low <= upper:
                    d = 0.0
                else:
                    d = min(abs(current_low - upper), abs(current_low - lower))
                
                prox = np.exp(-d / (0.75 * current_atr))
                strg = (1.0 - np.exp(-z['touches'] / 4.0)) * 1.0
                
                if prox > best_sup_prox:
                    best_sup_prox = prox
                    best_sup_str = strg
                    
            sup_prox_arr[i] = round(best_sup_prox, 3)
            sup_str_arr[i] = round(best_sup_str, 3)
            
        df['RS_res_proximity'] = res_prox_arr
        df['RS_res_strength'] = res_str_arr
        df['RS_sup_proximity'] = sup_prox_arr
        df['RS_sup_strength'] = sup_str_arr
        
        return df
