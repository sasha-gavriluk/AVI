import pandas as pd
from typing import List, Dict, Optional

class TickAggregator:
    """
    Агрегатор тіків (угод) у свічки OHLCV за заданим таймфреймом.
    Дозволяє отримувати поточну (незакриту) свічку та автоматично генерує закриті свічки 
    при переході часової межі.
    """
    
    def __init__(self, timeframe_ms: int, wait_for_boundary: bool = False):
        """
        :param timeframe_ms: Таймфрейм в мілісекундах (наприклад, 60000 для 1 хвилини)
        :param wait_for_boundary: Якщо True, ігнорує поточну неповну свічку і чекає початку наступної
        """
        self.timeframe_ms = timeframe_ms
        self.current_candle = None
        self.wait_for_boundary = wait_for_boundary
        self.waiting_boundary_start = None
        
    def _get_candle_start_time(self, timestamp_ms: int) -> int:
        """Повертає час початку свічки для заданого timestamp"""
        return (timestamp_ms // self.timeframe_ms) * self.timeframe_ms

    def process_tick(self, timestamp_ms: int, price: float, volume: float) -> Optional[Dict]:
        """
        Обробляє один тік.
        :param timestamp_ms: Час тіку в мілісекундах
        :param price: Ціна
        :param volume: Об'єм
        :return: Закриту свічку у вигляді словника (якщо тік відкрив нову свічку), або None
        """
        candle_start = self._get_candle_start_time(timestamp_ms)
        
        if self.wait_for_boundary:
            if self.waiting_boundary_start is None:
                self.waiting_boundary_start = candle_start
                return None
            elif candle_start <= self.waiting_boundary_start:
                return None # Все ще ігноруємо поточну неповну свічку
            else:
                self.wait_for_boundary = False # Дочекалися нової свічки!

        closed_candle = None

        if self.current_candle is None:
            # Ініціалізація першої свічки
            self.current_candle = {
                'timestamp': candle_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
        elif candle_start > self.current_candle['timestamp']:
            # Збереження закритої свічки
            closed_candle = self.current_candle.copy()
            
            # Початок нової свічки
            self.current_candle = {
                'timestamp': candle_start,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
        else:
            # Оновлення поточної свічки
            self.current_candle['high'] = max(self.current_candle['high'], price)
            self.current_candle['low'] = min(self.current_candle['low'], price)
            self.current_candle['close'] = price
            self.current_candle['volume'] += volume

        return closed_candle

    def get_current_candle(self) -> Optional[Dict]:
        """Повертає поточну (незакриту) свічку"""
        if self.current_candle:
            return self.current_candle.copy()
        return None
        
    def process_ticks_batch(self, ticks: List[Dict]) -> List[Dict]:
        """
        Обробляє масив тіків (наприклад, з історії).
        Формат тіка: {'timestamp': 123, 'price': 1.0, 'volume': 100}
        """
        closed_candles = []
        for tick in ticks:
            res = self.process_tick(tick['timestamp'], tick['price'], tick['volume'])
            if res:
                closed_candles.append(res)
        return closed_candles
