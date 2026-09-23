import pandas as pd
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
        pass

    #------------------------------
    # Перевірка тези входу
    #------------------------------

    @_handle_error
    def monitor_thesis(self, active_trade: dict, current_candle: pd.Series) -> str:
        "Перевіряє, чи не скасувалась причина входу ще до спрацювання стопа"
        close_price = current_candle.get('close', 0.0)   # колонка саме 'close' (з малої)
        direction = active_trade.get('direction')

        # 1. Теза мертва, якщо свічка ЗАКРИЛАСЬ за стопом. Це не те саме, що
        # спрацювання стопа: ціна могла проколоти рівень і повернутись — тоді
        # тримаємо. А от закриття за ним означає, що ринок передумав.
        #
        # Раніше умова приходила рядком "CLOSE < 1.2345" з класу InvalidationRules.
        # Той клас прибрано 01.09.2026: рядок доводилось складати, передавати
        # й розбирати назад, хоча вся потрібна інформація вже лежить в active_trade.
        stop_price = active_trade.get('stop_price')
        if stop_price and close_price:
            if direction == 'BUY' and close_price < stop_price:
                return "MARKET_CLOSE_THESIS_DEAD"
            if direction == 'SELL' and close_price > stop_price:
                return "MARKET_CLOSE_THESIS_DEAD"

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

        # Поріг беззбитку — один розмір ризику в наш бік. Раніше рахувалось
        # у FinancialAdvisor, перенесено сюди 01.09.2026: модуль на ремонті.
        risk = abs(entry - stop)
        if risk <= 0:
            return "HOLD"
        trigger_price = entry + risk if direction == 'BUY' else entry - risk

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
