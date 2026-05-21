# --- AUTO-GENERATED VARIABLES (DO NOT EDIT) ---
from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy
# (Оберіть індикатори зверху)
# ----------------------------------------------

from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy

v0 = Indicator("RSI_10")
v1 = Indicator("ADX_22")
v2 = Pattern("Three_Black_Crows")
v3 = Algorithm("CHOCH")
entry = ((v0 > 0) & (v1 > 0) & (v2 == True) & (v3 == 1))
exit = ((v0 < 0) | (v1 < 0) | (v2 == False) | (v3 == -1))
strategy = Strategy(entry_rule=entry, exit_rule=exit)


# UI_STATE_META: {"copilot_time_decay": [90], "copilot_auto_learn_threshold": [15.0], "copilot_best_components_score": [0.6]}
