from utils.rules_engine.core import Indicator, Pattern, Algorithm, Expression, Constant
from utils.rules_engine.strategy import Strategy

# Отримуємо алгоритм аномалій WCE. 
# Дефолтні параметри: peak_threshold=6, norm_threshold=3
anomaly = Algorithm("WCE_ANOMALY_6_3")

# Логіка WCEAnomalyDetector повертає:
#  1 -> сигнал BUY (пік аномалії був на ведмежій свічці, очікується відскок вгору)
# -1 -> сигнал SELL (пік аномалії був на бичачій свічці, очікується відскок вниз)
#  0 -> сигнал знято (аномалія впала до норми)

# Вхід у позицію (Buy) коли з'являється сигнал 1
entry = (anomaly == 1)

# Вихід з позиції (Sell) коли аномалія спадає до норми (0) або з'являється зворотній сигнал
exit = (anomaly == 0) | (anomaly == -1)

# Створення об'єкта стратегії, який очікує бектестер
strategy = Strategy(entry_rule=entry, exit_rule=exit)
