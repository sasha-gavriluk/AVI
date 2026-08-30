import pandas as pd
from utils.FinancialAdvisor import FinancialAdvisor
from utils.OtherUtils import _handle_error

#------------------------------
# Управління відкритою позицією
#------------------------------

class PositionManager:
    "Моніторинг відкритої позиції: чи жива ще теза, за якою заходили"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self):
        self.advisor = FinancialAdvisor()

    #------------------------------
    # Перевірка тези входу
    #------------------------------

    @_handle_error
    def monitor_thesis(self, active_trade: dict, current_candle: pd.Series) -> str:
        "Перевіряє, чи не скасувалась причина входу ще до спрацювання стопа"
        close_price = current_candle.get('close', 0.0)   # колонка саме 'close' (з малої)
        direction = active_trade.get('direction')

        # 1. Правило інвалідації виду "CLOSE < 1.2345" (задається у Блоці C)
        invalidation_rule = active_trade.get('invalidation_rule')
        if invalidation_rule:
            try:
                parts = invalidation_rule.split()
                if len(parts) == 3 and parts[0] == 'CLOSE':
                    operator = parts[1]
                    threshold = float(parts[2])

                    if operator == '<' and close_price < threshold:
                        return "MARKET_CLOSE_THESIS_DEAD"
                    elif operator == '>' and close_price > threshold:
                        return "MARKET_CLOSE_THESIS_DEAD"
            except Exception:
                pass   # Не змогли розібрати правило — просто тримаємо позицію

        # 2. Зворотний злам структури (CHoCH проти нашого напрямку).
        # Напрямок зламу беремо зі структури ринку: HH/HL — бичача, LH/LL — ведмежа.
        # Раніше читались неіснуючі smc_choch_down/up, тож перевірка не працювала.
        if current_candle.get('CHoCH', False):
            struct = current_candle.get('Market_Structure_Type', None)
            if direction == 'BUY' and struct in ('LH', 'LL'):
                return "MARKET_CLOSE_TREND_REVERSED"
            if direction == 'SELL' and struct in ('HH', 'HL'):
                return "MARKET_CLOSE_TREND_REVERSED"

        return "HOLD"

    #------------------------------
    # Перевід стопа в беззбиток
    #------------------------------

    @_handle_error
    def check_breakeven(self, active_trade: dict, current_price: float) -> str:
        "Каже, чи час пересунути стоп у беззбиток (коли прибуток досяг 1R)"
        entry = active_trade.get('entry_price')
        stop = active_trade.get('stop_price')
        direction = active_trade.get('direction')

        if not entry or not stop or direction not in ('BUY', 'SELL'):
            return "HOLD"
        if active_trade.get('breakeven_done'):
            return "HOLD"

        trigger = self.advisor.calculate_breakeven_trigger_price(
            entry_price=entry,
            stop_loss_price=stop,
            direction='buy' if direction == 'BUY' else 'sell',
            profit_factor_for_breakeven=1.0
        )
        trigger_price = trigger.get('breakeven_trigger_price')
        if trigger_price is None:
            return "HOLD"

        reached = (direction == 'BUY' and current_price >= trigger_price) or \
                  (direction == 'SELL' and current_price <= trigger_price)
        if reached:
            active_trade['stop_price'] = entry
            active_trade['breakeven_done'] = True
            return "MOVE_SL_TO_BREAKEVEN"

        return "HOLD"

    #------------------------------
    # Реакція на зміну режиму
    #------------------------------

    @_handle_error
    def monitor_regime(self, active_trade: dict, current_regime: str) -> None:
        "Підлаштовує режим управління позицією, коли макро-режим змінився"
        original_regime = active_trade.get('entry_regime')

        if original_regime == 'TREND' and current_regime == 'FLAT':
            # Тренд зупинився — агресивніший трейлінг або часткова фіксація
            active_trade['management_mode'] = 'AGGRESSIVE_TRAILING'

        elif original_regime == 'FLAT' and current_regime == 'TREND':
            # Був флет, стався імпульс — можна тягнути тейк-профіт далі
            active_trade['management_mode'] = 'TREND_FOLLOWING'
