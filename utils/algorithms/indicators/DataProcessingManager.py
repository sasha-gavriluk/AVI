import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE
from utils.algorithms.indicators.AlgorithmProcessor import AlgorithmProcessor
from utils.algorithms.indicators.PatternDetector import PatternDetector
from utils.algorithms.indicators.IndicatorProcessor import IndicatorProcessor
from utils.algorithms.indicators.BacktestAlgorithmProcessor import BacktestAlgorithmProcessor
import sys
import os

ai_lab_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../AI_Lab'))
if ai_lab_dir not in sys.path:
    sys.path.insert(0, ai_lab_dir)

try:
    from PT.PT import PT
except ImportError:
    PT = None

class DataProcessingManager:
    """Головний менеджер для оркестрації обробки даних"""
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, data: pd.DataFrame, indicators_params=None, pattern_params=None, algorithm_params=None, algorithm_processor_class=BacktestAlgorithmProcessor):
        """Ініціалізація"""
        self.data = data
        self.processed_data = data.copy()

        self.indicator_processor = IndicatorProcessor(
            self.data, self.processed_data, indicators_params
        )
        self.pattern_detector = PatternDetector(
            self.data, self.processed_data, pattern_params
        )
        self.pt_model = PT() if PT is not None else None
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
        if self.pt_model is not None:
            self.processed_data = self.pt_model.process(self.processed_data)
        self.algorithm_processor.process_data()
        return self.processed_data