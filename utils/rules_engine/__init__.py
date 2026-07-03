# ==================================================================
# ВІДКЛЮЧЕНО (RULES_ENGINE): робота з класичними стратегіями тимчасово
# заморожена. core.py/registry.py/strategy.py загорнуті у рядкові
# літерали і більше не визначають жодного класу — тому й тут імпорти
# закоментовано, інакше застосунок впаде при старті (ImportError).
# Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
# ==================================================================
# from .core import Indicator, Pattern, Algorithm, Constant, Expression, CrossOver, CrossUnder
# from .registry import IndicatorRegistry
# from .strategy import Strategy

# __all__ = ['Indicator', 'Pattern', 'Algorithm', 'Constant', 'Expression', 'CrossOver', 'CrossUnder', 'IndicatorRegistry', 'Strategy']
