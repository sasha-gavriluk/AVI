from utils.FinancialAdvisor import FinancialAdvisor
from utils.OtherUtils import _handle_error

#------------------------------
# Мета-захист рахунку
#------------------------------

class AccountGuard:
    "Захист від тільту та вигорання депозиту (денний ліміт + сукупний ризик портфеля)"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, max_daily_loss_pct: float = 5.0):
        self.advisor = FinancialAdvisor()
        self.max_daily_loss_pct = max_daily_loss_pct

    #------------------------------
    # Дозвіл на торгівлю
    #------------------------------

    @_handle_error
    def can_trade(self, account_state: dict) -> bool:
        "Вирішує, чи дозволено відкривати нові угоди з огляду на стан рахунку"
        # 1. Денний ліміт збитків
        if account_state.get('daily_loss_pct', 0.0) >= self.max_daily_loss_pct:
            return False

        # 2. Сукупний ризик по вже відкритих позиціях (рахує FinancialAdvisor).
        # Якщо портфель уже в зоні високого ризику — нових угод не беремо.
        capital = account_state.get('total_capital', 0.0)
        open_trades = account_state.get('active_positions', [])
        if capital > 0 and open_trades:
            portfolio = self.advisor.evaluate_portfolio_risk(
                total_capital=capital,
                open_trades=open_trades
            )
            if portfolio.get('risk_level') == 'high':
                return False

        return True

#------------------------------
# Контроль корельованих позицій
#------------------------------

class CorrelationGuard:
    "Ріже розмір нової позиції, якщо вже є відкриті в тому ж напрямку"

    #------------------------------
    # Коригування розміру
    #------------------------------

    @_handle_error
    def adjust_size(self, new_asset: str, new_direction: str, active_positions: list) -> float:
        "Повертає множник розміру. Крипто-активи вважаємо скорельованими між собою"
        multiplier = 1.0

        for pos in active_positions:
            if pos.get('direction') == new_direction:
                multiplier *= 0.5   # Уже є угода в цей бік — ріжемо сайз навпіл

        return multiplier

#------------------------------
# Захист від новин
#------------------------------

class EventGuard:
    "Скасовує технічні сигнали біля важливих макро-подій (CPI, NFP тощо)"

    #------------------------------
    # Перевірка безпеки часу
    #------------------------------

    @_handle_error
    def is_safe_to_trade(self, current_time, news_calendar=None) -> bool:
        "Заглушка: без підключеного календаря новин завжди дозволяє торгівлю"
        if news_calendar is None:
            return True

        # TODO: Підключити реальний API календаря новин
        # if news_calendar.has_high_impact_event_soon(current_time, window_minutes=15):
        #     return False

        return True

#------------------------------
# Розрахунок розміру позиції
#------------------------------

class PositionSizer:
    "Рахує розмір ф'ючерсної позиції та перевіряє, що стоп не за ціною ліквідації"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self):
        self.advisor = FinancialAdvisor()

    #------------------------------
    # Розмір і перевірка ліквідації
    #------------------------------

    @_handle_error
    def calculate(self, account_state: dict, entry_price: float, stop_price: float,
                  direction: str, size_multiplier: float = 1.0) -> dict:
        "Повертає розмір позиції, маржу, ціну ліквідації та прапорець валідності"
        capital = account_state.get('total_capital', 0.0)
        risk_pct = account_state.get('risk_per_trade_pct', 1.0) * size_multiplier
        leverage = account_state.get('leverage', 10)

        if capital <= 0 or entry_price <= 0 or entry_price == stop_price:
            return {'valid': False, 'reason': 'Некоректні вхідні дані для сайзингу'}

        side = 'buy' if direction == 'BUY' else 'sell'

        position = self.advisor.calculate_futures_position_size(
            capital=capital,
            risk_per_trade_pct=risk_pct,
            entry_price=entry_price,
            stop_loss_price=stop_price,
            leverage=leverage
        )
        if 'error' in position:
            return {'valid': False, 'reason': position['error']}

        liquidation = self.advisor.calculate_liquidation_price(
            entry_price=entry_price,
            leverage=leverage,
            direction=side
        )
        liq_price = liquidation.get('liquidation_price')

        # Ключова перевірка для плеча: стоп МАЄ спрацювати раніше за ліквідацію
        if liq_price:
            is_safe = (side == 'buy' and stop_price > liq_price) or \
                      (side == 'sell' and stop_price < liq_price)
            if not is_safe:
                return {'valid': False, 'reason': f'Стоп ({stop_price}) за ціною ліквідації ({liq_price})'}

        return {
            'valid': True,
            'liquidation_price': liq_price,
            **position
        }
