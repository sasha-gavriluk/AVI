from utils.rules_engine.core import Indicator, Pattern, Algorithm
from utils.rules_engine.strategy import Strategy

# Згенерована ШІ стратегія. Напрямок: BUY
# Основний сигнал: RSI Frequency Test

rsi = Indicator("RSI_2")

# RSI завжди менше 110, тому ця умова спрацьовуватиме практично на кожній свічці.
entry = (rsi < 110)

# Вихід також миттєвий.
exit = (rsi > -10)

strategy = Strategy(entry_rule=entry, exit_rule=exit)
