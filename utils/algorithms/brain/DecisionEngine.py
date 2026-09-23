import pandas as pd

from .AccountGuard import AccountGuard
from .EventGuard import EventGuard
from .CorrelationGuard import CorrelationGuard
from .PositionSizer import PositionSizer
from .PositionManager import PositionManager
from utils.OtherUtils import _handle_error

#==============================
# Двигун прийняття рішень
#==============================
#
# ЩО ЗМІНИЛОСЬ 01.09.2026.
# Раніше двигун сам вирішував, куди і коли заходити: блоки A (режим ринку),
# B (фаза) і C (тригер входу) складали рішення з правил. Усе це прибрано —
# рішення про БІК і ВХІД тепер дає мережа ChronoSeer (Code/models/CS).
#
# Двигун лишається тим, чим він насправді цінний: шаром РИЗИКУ.
# Мережа не знає ні про баланс, ні про плече, ні про новини, ні про те,
# скільки позицій уже відкрито — усе це рахується тут.
#
# Модулі замість блоків: кожен файл відповідає за одну річ і називається
# за призначенням, а не за місцем у конвеєрі.
#     AccountGuard      — денний ліміт збитку, сукупний ризик портфеля
#     EventGuard        — новини
#     CorrelationGuard  — кілька позицій в один бік
#     PositionSizer     — розмір, маржа, перевірка ліквідації
#     PositionManager   — ведення вже відкритої позиції
#==============================


class DecisionEngine:
    "Шар ризику: приймає вердикт мережі й вирішує, чи можна й яким розміром торгувати"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self):
        self.account_guard = AccountGuard()
        self.event_guard = EventGuard()
        self.correlation_guard = CorrelationGuard()
        self.position_sizer = PositionSizer()
        self.position_manager = PositionManager()

    #------------------------------
    # Стан рахунку за замовчуванням
    #------------------------------

    def _default_account_state(self) -> dict:
        """
        Базовий стан рахунку.

        УВАГА: це заглушка для бектесту. Для реальних вето стан має вести
        викликач — бот або симулятор, — інакше денний ліміт і ризик портфеля
        не спрацюють ніколи, бо тут завжди нулі.
        """
        return {
            'daily_loss_pct': 0.0,
            'active_positions': [],
            'total_capital': 1000.0,
            'risk_per_trade_pct': 1.0,
            'leverage': 10
        }

    #------------------------------
    # Оцінка одного вердикту мережі
    #------------------------------

    @_handle_error
    def evaluate(self, verdict: dict, row: pd.Series, account_state: dict = None) -> dict:
        """
        Пропускає вердикт мережі через шар ризику.

        :param verdict: що сказала мережа — {'direction': 'BUY'/'SELL',
                        'confidence': 0.0-1.0, 'stop_price': ..., 'target_price': ...}
        :param row: свічка рішення (потрібні ціна й ATR)
        :param account_state: реальний стан рахунку від бота
        :return: рішення з розміром позиції або відмова з причиною

        ПОРЯДОК ПЕРЕВІРОК ТУТ ПОПЕРЕДНІЙ і чекає уточнення від господаря.
        """
        if account_state is None:
            account_state = self._default_account_state()

        entry_price = row.get('close', 0.0)
        direction = verdict.get('direction')
        stop_price = verdict.get('stop_price')

        # 1. Новини: якщо поруч важлива подія — не торгуємо взагалі
        if not self.event_guard.is_safe_to_trade(row.get('timestamp'),
                                                 account_state.get('news_calendar')):
            return {'allowed': False, 'reason': 'Заборона через новини'}

        # 2. Стан рахунку: денний ліміт і ризик портфеля
        if not self.account_guard.can_trade(account_state):
            return {'allowed': False, 'reason': 'Заборона захисту рахунку'}

        # 3. Кілька позицій в один бік — ріжемо розмір
        size_multiplier = self.correlation_guard.adjust_size(
            new_asset=account_state.get('asset', ''),
            new_direction=direction,
            active_positions=account_state.get('active_positions', [])
        )

        # 4. Розмір, маржа й головна перевірка плеча:
        # стоп МУСИТЬ спрацювати раніше за ліквідацію
        sizing = self.position_sizer.calculate(
            account_state=account_state,
            entry_price=entry_price,
            stop_price=stop_price,
            direction=direction,
            size_multiplier=size_multiplier
        )
        if not sizing.get('valid'):
            return {'allowed': False, 'reason': sizing.get('reason', 'Сайзинг неможливий')}

        return {
            'allowed': True,
            'direction': direction,
            'confidence': verdict.get('confidence', 0.0),
            'entry_price': entry_price,
            'stop_price': stop_price,
            'target_price': verdict.get('target_price'),
            'size_multiplier': size_multiplier,
            **sizing
        }

    #------------------------------
    # Ведення відкритої позиції
    #------------------------------

    @_handle_error
    def manage_position(self, active_trade: dict, row: pd.Series) -> str:
        "Питає в PositionManager, що робити з уже відкритою позицією"
        thesis = self.position_manager.monitor_thesis(active_trade, row)
        if thesis != "HOLD":
            return thesis

        return self.position_manager.check_breakeven(active_trade, row.get('close', 0.0))
