from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy

# Згенерована ШІ стратегія. Напрямок: BUY
# Основний сигнал: Three_White_Soldiers
# Фільтри: CCI

three_sig = Pattern("Three_White_Soldiers")
cci_fil_0 = Indicator("CCI_15")

entry = (three_sig == 1) & (cci_fil_0 < -104)
exit = (cci_fil_0 > 104)

strategy = Strategy(entry_rule=entry, exit_rule=exit)