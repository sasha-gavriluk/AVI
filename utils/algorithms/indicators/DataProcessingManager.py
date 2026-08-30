import numpy as np
import pandas as pd
from utils.algorithms.WrapCandleEngine import WCE
from utils.algorithms.indicators.AlgorithmProcessor import AlgorithmProcessor
from utils.algorithms.indicators.PatternDetector import PatternDetector
from utils.algorithms.indicators.IndicatorProcessor import IndicatorProcessor
from utils.algorithms.indicators.BacktestAlgorithmProcessor import BacktestAlgorithmProcessor
import sys
import os

from utils.OtherUtils import _handle_error

ai_lab_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../AI_Lab'))
if ai_lab_dir not in sys.path:
    sys.path.insert(0, ai_lab_dir)

class DataProcessingManager:
    "Головний менеджер для оркестрації обробки даних (індикатори, патерни, алгоритми)"
    
    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, data: pd.DataFrame, indicators_params=None, pattern_params=None, algorithm_params=None, algorithm_processor_class=BacktestAlgorithmProcessor):
        self.data = data
        self.processed_data = data.copy()

        self.indicator_processor = IndicatorProcessor(
            self.data, self.processed_data, indicators_params
        )
        self.pattern_detector = PatternDetector(
            self.data, self.processed_data, pattern_params
        )
        self.algorithm_processor = algorithm_processor_class(
            self.data, self.processed_data, algorithm_params
        )

    #------------------------------
    # Головний оркестратор
    #------------------------------

    @_handle_error
    def process_all(self):
        "Головний процес послідовної обробки: індикатори -> патерни -> алгоритми"
        self.indicator_processor.process_data()
        self.pattern_detector.process_data()
        self.algorithm_processor.process_data()
        return self.processed_data