from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy

# Згенерована ШІ стратегія. Напрямок: SELL
# Основний сигнал: Shooting_Star
# Фільтри: Market_State_Linear, ADX, RSI_14

shooting_sig = Pattern("Shooting_Star")
market_fil_0 = Algorithm("MARKET_STATE_LINEAR")
adx_fil_1 = Indicator("ADX_6")
rsi_fil_2 = Indicator("RSI_6")

entry = (shooting_sig == 1) & (market_fil_0 == -1) & (adx_fil_1 > 25) & (rsi_fil_2 > 68)
exit = (market_fil_0 == 1)

strategy = Strategy(entry_rule=entry, exit_rule=exit)