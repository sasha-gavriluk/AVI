import pandas as pd
from utils.FinancialAdvisor import FinancialAdvisor
from utils.OtherUtils import _handle_error

#------------------------------
# Перевірка тригерів входу
#------------------------------

class EntryTriggerValidator:
    "Шукає конкретну точку входу залежно від режиму та фази ринку"

    #------------------------------
    # Пошук тригера
    #------------------------------

    @_handle_error
    def check_trigger(self, row: pd.Series, current_price: float, regime: str, flat_phase: str):
        "Повертає (trigger_type, direction) або (None, None), якщо входу немає"
        if regime == 'TREND':
            # У тренді шукаємо відкати в зону попиту/пропозиції
            if row.get('FVG_Up', False): return 'FVG_TOUCH', 'BUY'
            if row.get('FVG_Down', False): return 'FVG_TOUCH', 'SELL'
            if row.get('Bullish_OB', False): return 'OB_TOUCH', 'BUY'
            if row.get('Bearish_OB', False): return 'OB_TOUCH', 'SELL'

        elif regime == 'FLAT' and flat_phase == 'TRADEABLE_RANGE':
            # У флеті шукаємо зняття ліквідності за межу діапазону
            if row.get('Sweep_High', False): return 'SWEEP_HIGH', 'SELL'
            if row.get('Sweep_Low', False): return 'SWEEP_LOW', 'BUY'

        return None, None

#------------------------------
# Розрахунок R:R
#------------------------------

class RewardRiskCalculator:
    "Рахує стоп, ціль і R:R. Стоп/ціль будує FinancialAdvisor (рівні S/R + ATR)"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, min_rr: float = 1.5):
        self.advisor = FinancialAdvisor()
        self.min_rr = min_rr

    #------------------------------
    # Оцінка угоди
    #------------------------------

    @_handle_error
    def evaluate(self, entry_price: float, trigger_type: str, risk_map: dict,
                 direction: str, row: pd.Series) -> dict:
        "Визначає стоп і ціль, обчислює R:R. Накладає вето, якщо R:R нижче мінімуму"
        atr = row.get('ATR_14', None)
        if atr is None or pd.isna(atr) or atr <= 0:
            atr = entry_price * 0.01

        side = 'buy' if direction == 'BUY' else 'sell'

        # 1. Базові стоп і ціль від FinancialAdvisor: він ховає стоп за рівень S/R
        # з ATR-подушкою, а ціль ставить у протилежний рівень (або класичний R:R).
        levels = self.advisor.calculate_sl_tp_levels(
            entry_price=entry_price,
            direction=side,
            risk_reward_ratio=2.0,
            atr_value=atr,
            atr_multiplier=1.5,
            support_price=risk_map.get('target_sup'),
            resistance_price=risk_map.get('target_res')
        )
        if 'error' in levels:
            return {'valid': False, 'reason': levels['error']}

        stop_price = levels['stop_loss_price']
        target_price = levels['take_profit_price']

        # 2. Структурний стоп від самого тригера (екстремум свічки входу) — він
        # точніший за загальний, тож беремо його, якщо він валідний і тісніший.
        struct_stop = None
        if trigger_type and ('OB_TOUCH' in trigger_type or 'SWEEP' in trigger_type):
            struct_stop = row.get('low') if direction == 'BUY' else row.get('high')

        if struct_stop is not None and not pd.isna(struct_stop) and struct_stop > 0:
            is_valid_side = (direction == 'BUY' and struct_stop < entry_price) or \
                            (direction == 'SELL' and struct_stop > entry_price)
            is_tighter = abs(entry_price - struct_stop) < abs(entry_price - stop_price)
            if is_valid_side and is_tighter:
                stop_price = struct_stop

        # 3. Запобіжник: стоп не може бути з неправильного боку від входу
        if direction == 'BUY' and stop_price >= entry_price:
            stop_price = entry_price - atr
        if direction == 'SELL' and stop_price <= entry_price:
            stop_price = entry_price + atr

        # 4. Математика R:R
        risk = abs(entry_price - stop_price)
        if risk == 0:
            return {'valid': False, 'reason': 'Ризик дорівнює нулю'}

        reward = abs(target_price - entry_price)
        rr = reward / risk

        # 5. Вето за поганим співвідношенням
        if rr < self.min_rr:
            return {'valid': False, 'reason': f'Поганий R:R ({rr:.2f} < {self.min_rr})'}

        return {'valid': True, 'stop': stop_price, 'target': target_price, 'rr': rr}

#------------------------------
# Правило інвалідації ідеї
#------------------------------

class InvalidationRules:
    "Формулює умову, за якої теза входу вважається мертвою (перевіряється в Блоці E)"

    #------------------------------
    # Створення правила
    #------------------------------

    @staticmethod
    @_handle_error
    def set_rule(trigger_type: str, entry_price: float, stop_price: float, direction: str) -> str:
        "Створює правило виду 'CLOSE < 1.2345' — закриття за рівнем стопа вбиває тезу"
        operator = "<" if direction == 'BUY' else ">"
        return f"CLOSE {operator} {stop_price}"
