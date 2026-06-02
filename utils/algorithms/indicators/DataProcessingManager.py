import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE
from utils.algorithms.indicators.AlgorithmProcessor import AlgorithmProcessor
from utils.algorithms.indicators.PatternDetector import PatternDetector
from utils.algorithms.indicators.IndicatorProcessor import IndicatorProcessor

class DataProcessingManager:
    """Головний менеджер для оркестрації обробки даних"""
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, data: pd.DataFrame, indicators_params=None, pattern_params=None, algorithm_params=None, algorithm_processor_class=AlgorithmProcessor):
        """Ініціалізація"""
        self.data = data
        self.processed_data = data.copy()

        self.indicator_processor = IndicatorProcessor(
            self.data, self.processed_data, indicators_params
        )
        self.pattern_detector = PatternDetector(
            self.data, self.processed_data, pattern_params
        )
        # Use the specified algorithm_processor_class
        self.algorithm_processor = algorithm_processor_class(
            self.data, self.processed_data, algorithm_params
        )

    # ----------------------------------
    # Метод process_all
    # ----------------------------------

    def process_all(self):
        """Головний процес обробки: індикатори -> патерни -> алгоритми."""
        self.indicator_processor.process_data()
        self.pattern_detector.process_data()
        self.algorithm_processor.process_data()
        return self.processed_data