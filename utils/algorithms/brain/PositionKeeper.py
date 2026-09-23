import uuid

from utils.OtherUtils import _handle_error

#==============================
# Ведення відкритих позицій
#==============================
#
# Мережа каже, коли ЗАЙТИ, і на цьому замовкає. Хтось мусить далі стежити за
# угодою: чи не спрацював стоп, чи не пора в беззбиток, чи не померла теза.
# Раніше цього не робив ніхто — PositionManager існував, але його не викликав
# жоден рядок коду.
#
# Цей клас і є той хтось. Він тримає відкриті угоди, на кожній свічці питає
# PositionManager, що з ними робити, і веде розрахунок із AccountState.
#
# ЧОМУ ВІН САМ ПЕРЕВІРЯЄ СТОП І ТЕЙК. У живій торгівлі це робить біржа, і тоді
# перевірка тут просто не спрацює першою. Але в паперовому режимі й у бектесті
# біржі немає, тож рахуємо самі — за тими самими правилами, що й у симуляторі
# лабораторії: спершу ліквідація, потім стоп, потім тейк. Усередині свічки ми
# не знаємо, що ціна зачепила раніше, тож беремо гірший для себе випадок.
#==============================


class PositionKeeper:
    "Тримає відкриті позиції й доводить кожну до закриття"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, account, engine, journal=None, fee_pct: float = 0.04):
        """
        :param account: AccountState — хто веде гроші
        :param engine: DecisionEngine — у нього питаємо про ведення позиції
        :param journal: TradeJournal — пише кожну угоду в базу одразу
        :param fee_pct: комісія біржі на ОДИН бік, у відсотках
        """
        self.account = account
        self.engine = engine
        self.journal = journal
        self.fee_pct = fee_pct

    #------------------------------
    # Відкриття
    #------------------------------

    @_handle_error
    def open(self, decision: dict, pair: str, opened_at) -> dict:
        """
        Заводить нову угоду з рішення, яке пройшло шар ризику.

        :param decision: те, що повернув DecisionEngine.evaluate
        """
        trade = {
            'id': str(uuid.uuid4())[:8],
            'pair': pair,
            'direction': decision['direction'],
            'entry_price': decision['entry_price'],
            'stop_price': decision['stop_price'],
            'target_price': decision.get('target_price'),
            'liquidation_price': decision.get('liquidation_price'),
            'confidence': decision.get('confidence', 0.0),
            'position_size': decision.get('position_size_usd'),
            'margin': decision.get('margin_required_usd'),
            'opened_at': opened_at,
            'bars_held': 0,
            'breakeven_done': False,
        }
        self.account.open_position(trade)
        if self.journal:
            self.journal.on_open(trade, horizon=decision.get('horizon'),
                                 leverage=self.account.LEVERAGE,
                                 balance=self.account.balance)
        return trade

    #------------------------------
    # Скільки грошей дала угода
    #------------------------------

    def _pnl(self, trade: dict, exit_price: float) -> float:
        "Переводить рух ціни в долари з урахуванням плеча й комісії в обидва боки"
        entry = trade['entry_price']
        move = ((exit_price - entry) / entry if trade['direction'] == 'BUY'
                else (entry - exit_price) / entry)

        margin = trade.get('margin') or 0.0
        notional = margin * self.account.LEVERAGE
        fee = notional * (self.fee_pct * 2 / 100.0)
        return notional * move - fee

    #------------------------------
    # Перевірка рівнів на свічці
    #------------------------------

    @_handle_error
    def _exit_hit(self, trade: dict, candle) -> tuple:
        """
        Дивиться, чи зачепила свічка ліквідацію, стоп або тейк.

        Порядок навмисний: спершу найгірше. Усередині 15-хвилинної свічки
        невідомо, що сталось раніше, тож рахуємо НЕ на свою користь.

        :return: (ціна виходу, причина) або (None, None)
        """
        high, low = float(candle.get('high')), float(candle.get('low'))
        is_long = trade['direction'] == 'BUY'

        liq = trade.get('liquidation_price')
        if liq and ((is_long and low <= liq) or (not is_long and high >= liq)):
            return liq, 'ліквідація'

        stop = trade['stop_price']
        if (is_long and low <= stop) or (not is_long and high >= stop):
            return stop, 'стоп'

        target = trade.get('target_price')
        if target and ((is_long and high >= target) or (not is_long and low <= target)):
            return target, 'тейк'

        return None, None

    #------------------------------
    # Головний метод: крок на новій свічці
    #------------------------------

    @_handle_error
    def on_candle(self, candle, pair: str = None) -> list:
        """
        Проводить усі відкриті позиції через нову свічку.

        :return: список подій — що сталося з кожною угодою
        """
        events = []

        for trade in list(self.account.positions):
            if pair and trade['pair'] != pair:
                continue
            trade['bars_held'] += 1

            # 1. Чи зачепила свічка рівні
            exit_price, reason = self._exit_hit(trade, candle)
            if exit_price is not None:
                pnl = self._pnl(trade, exit_price)
                self.account.close_position(trade, pnl)
                if self.journal:
                    self.journal.on_close(trade, exit_price, reason, pnl,
                                          self.account.balance, candle.get('timestamp'))
                events.append({'trade': trade['id'], 'action': reason,
                               'price': exit_price, 'pnl': pnl})
                continue

            # 2. Чи не померла теза й чи не пора в беззбиток
            action = self.engine.manage_position(trade, candle)
            if action and action.startswith('MARKET_CLOSE'):
                price = float(candle.get('close'))
                pnl = self._pnl(trade, price)
                self.account.close_position(trade, pnl)
                if self.journal:
                    self.journal.on_close(trade, price, action, pnl,
                                          self.account.balance, candle.get('timestamp'))
                events.append({'trade': trade['id'], 'action': action,
                               'price': price, 'pnl': pnl})
            elif action == 'MOVE_SL_TO_BREAKEVEN':
                events.append({'trade': trade['id'], 'action': action,
                               'price': trade['stop_price'], 'pnl': 0.0})

        return events

    #------------------------------
    # Чи можна відкривати нову
    #------------------------------

    def has_room(self, max_positions: int = 1, pair: str = None) -> bool:
        """
        Чи є місце під нову позицію.

        :param max_positions: стеля на весь рахунок
        :param pair: якщо вказана — ще й вимога, щоб на цій монеті було порожньо

        ЩО ЗМІНИЛОСЬ 02.09.2026. Раніше метод рахував тільки загальну кількість,
        бо доглядач був свій у кожної монети й іншого способу не було.
        Відколи TradeRunner роздає ОДНОГО доглядача на всі монети, самої лише
        загальної стелі мало: при стелі 3 на одному SOL могло відкритись
        три позиції поспіль. Тому додано перевірку по монеті.

        Було:
            def has_room(self, max_positions: int = 1) -> bool:
                return (not self.account.check_kill_switch()
                        and len(self.account.positions) < max_positions)
        """
        if self.account.check_kill_switch():
            return False
        if len(self.account.positions) >= max_positions:
            return False
        if pair is not None:
            return not any(p.get('pair') == pair for p in self.account.positions)
        return True
