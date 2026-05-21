from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy

# Згенерована ШІ стратегія. Напрямок: BUY
# Основний сигнал: Inverted_Hammer
# Фільтри: RSI_14

inverted_sig = Pattern("Inverted_Hammer")
rsi_fil_0 = Indicator("RSI_12")

entry = (inverted_sig == 1) & (rsi_fil_0 < 25)
exit = (rsi_fil_0 > 69)

strategy = Strategy(entry_rule=entry, exit_rule=exit)