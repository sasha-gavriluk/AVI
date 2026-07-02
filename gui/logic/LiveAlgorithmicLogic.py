import os
import time
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import pandas as pd

from utils.PathManager import PathManager
from utils.DataBaseManager import DataBaseManager
from utils.algorithms.indicators.IndicatorProcessor import IndicatorProcessor
from utils.algorithms.indicators.PatternDetector import PatternDetector
from utils.algorithms.indicators.BacktestAlgorithmProcessor import BacktestAlgorithmProcessor
from utils.algorithms.CopilotAlgorithmicLogic import CopilotAlgorithmicLogic

class OnDemandAnalysisThread(QThread):
    analysis_finished = pyqtSignal(list)

    def __init__(self, target_assets):
        super().__init__()
        self.target_assets = target_assets
        self.logic = CopilotAlgorithmicLogic(use_context_rules=True)

    def run(self):
        db_path = PathManager.get_db_path()
        results = []
        
        try:
            with DataBaseManager(db_path) as db:
                for asset in self.target_assets:
                    # Beремо мінімум 2000 свічок, щоб нейромережа отримала 1000 необхідних
                    df = db.get_data_by_number_range(asset, 2000)
                    if df is None or len(df) < 100:
                        continue
                        
                    # Розрахунок індикаторів на всьому датафреймі
                    processor = IndicatorProcessor(df, df.copy())
                    df = processor.process_data()
                    detector = PatternDetector(df, df)
                    df = detector.process_data()
                    algo_processor = BacktestAlgorithmProcessor(df, df, algorithm_params=['Order_Blocks', 'Fair_Value_Gaps', 'Market_Structure'])
                    df = algo_processor.process_data()
                    
                    # ВАЖЛИВО: Передаємо ВЕСЬ df, щоб _predict_nn_scores отримав >= 1000 свічок.
                    # analyze_window аналізує тільки останній рядок (last_row = df.iloc[-1]),
                    # але нейромережа потребує весь масив для контексту.
                    res = self.logic.analyze_window(df, asset=asset)
                    
                    price = float(df['close'].iloc[-1])
                    
                    # Маппінг полів: analyze_window повертає buy_score/sell_score (не probabilities)
                    results.append({
                        'asset': asset,
                        'signal': res.get('signal'),
                        'probabilities': {
                            'buy': res.get('buy_score', 0.0),
                            'sell': res.get('sell_score', 0.0),
                        },
                        'market_state': res.get('market_state', '-'),
                        'trend_strength': res.get('trend_strength', '-'),
                        'nn_support': res.get('nn_support', 0.0),
                        'nn_resistance': res.get('nn_resistance', 0.0),
                        'nn_fb_bullish': res.get('nn_fb_bullish', 0.0),
                        'nn_fb_bearish': res.get('nn_fb_bearish', 0.0),
                        'mr_trend': res.get('mr_trend', 0.0),
                        'mr_explosion': res.get('mr_explosion', 0.0),
                        'threshold': res.get('threshold', 0.65),
                        'price': price,
                        'active_signals': res.get('active_signals', []),
                        'block_reason': res.get('block_reason', ''),
                        'raw_buy': res.get('raw_buy', 0.0),
                        'raw_sell': res.get('raw_sell', 0.0),
                    })
        except Exception as e:
            import traceback
            print(f"OnDemand Analysis Error: {e}\n{traceback.format_exc()}")
            
        self.analysis_finished.emit(results)

class LiveAlgorithmicLogic(QObject):
    def __init__(self):
        super().__init__()
        self.thread = None

    def request_analysis(self, target_assets, callback):
        if self.thread and self.thread.isRunning():
            return
            
        self.thread = OnDemandAnalysisThread(target_assets)
        self.thread.analysis_finished.connect(callback)
        self.thread.start()
