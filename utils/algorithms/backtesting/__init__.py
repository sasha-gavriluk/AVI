# Initialization of backtesting module
from .BaseSettings import BaseSettings
from .SignalProvider import Analyzer
# ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ): MarketRunner.py заморожений (весь
# код обгорнутий у рядковий літерал, клас більше не визначений) — цей
# імпорт на рівні пакету інакше валив би ImportError КОЖЕН імпорт будь-чого
# з utils.algorithms.backtesting.*, включно з живим TradingCopilot.
# Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
# from .MarketRunner import MarketRunner
# from .NGramAnalyzer import NGramAnalyzer
