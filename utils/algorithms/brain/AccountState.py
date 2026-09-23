import datetime

from utils.OtherUtils import _handle_error

#==============================
# Стан рахунку
#==============================
#
# Раніше стан був заглушкою просто в DecisionEngine: $1000 і нуль збитку
# назавжди. Через це жодне вето блоку ризику не могло спрацювати — воно
# щоразу дивилось на нулі й дозволяло торгувати.
#
# Тепер стан веде окремий об'єкт: він знає баланс, денний збиток, відкриті
# позиції й головне — коли пора зупинитись назовсім.
#
# ДВІ РІЗНІ МЕЖІ, і їх не варто плутати:
#   денний ліміт    — сьогодні більше не торгуємо, завтра почнемо заново;
#   повна зупинка   — рахунок просів на стільки, що система вимикається
#                     до ручного втручання. Це рубильник, а не пауза.
#==============================


class AccountState:
    "Живий стан рахунку: баланс, збитки, відкриті позиції, рубильник"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    # Повна зупинка. 15% зі $150 — це приблизно $20, як домовлено 01.09.2026.
    MAX_DRAWDOWN_PCT = 15.0

    # Денна пауза. М'якша межа: сьогодні досить, завтра спробуємо знову.
    MAX_DAILY_LOSS_PCT = 5.0

    # Плече 10, а не 20: ту саму експозицію дає частка застави, а ліквідація
    # відсувається з 5% на 10%. У стрес-тестах 31.08 це різниця між сімома
    # ліквідаціями й двома на тих самих угодах.
    LEVERAGE = 10

    # Скільки балансу йде в заставу під одну угоду
    MARGIN_PCT = 10.0

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, start_balance: float = 150.0):
        """
        :param start_balance: з чого починаємо. Від нього рахується просідання
        """
        self.start_balance = float(start_balance)
        self.balance = float(start_balance)
        self.positions = []
        self.stopped = False
        self.stop_reason = ''

        self._day = datetime.date.today()
        self._day_start_balance = self.balance

        self.history = []          # закриті угоди
        self.peak = self.balance

    #------------------------------
    # Зміна доби
    #------------------------------

    def _check_day(self) -> None:
        "Новий день — денний лічильник обнуляється, рубильник НІ"
        today = datetime.date.today()
        if today != self._day:
            self._day = today
            self._day_start_balance = self.balance

    #------------------------------
    # Поточні збитки
    #------------------------------

    @property
    def daily_loss_pct(self) -> float:
        "Скільки відсотків втрачено від балансу на початок доби"
        self._check_day()
        if self._day_start_balance <= 0:
            return 0.0
        loss = self._day_start_balance - self.balance
        return max(0.0, loss / self._day_start_balance * 100.0)

    @property
    def drawdown_pct(self) -> float:
        "Скільки відсотків втрачено від СТАРТОВОГО балансу"
        if self.start_balance <= 0:
            return 0.0
        return max(0.0, (self.start_balance - self.balance) / self.start_balance * 100.0)

    #------------------------------
    # Рубильник
    #------------------------------

    @_handle_error
    def check_kill_switch(self) -> bool:
        """
        Головна межа: просідання від старту. Спрацювавши раз, не скидається —
        далі потрібне ручне втручання.

        :return: True, якщо торгівля зупинена
        """
        if self.stopped:
            return True

        if self.drawdown_pct >= self.MAX_DRAWDOWN_PCT:
            self.stopped = True
            self.stop_reason = (
                f"Просідання {self.drawdown_pct:.1f}% від старту "
                f"(${self.start_balance - self.balance:.2f}) — межа {self.MAX_DRAWDOWN_PCT}%"
            )
        return self.stopped

    #------------------------------
    # Облік угод
    #------------------------------

    @_handle_error
    def open_position(self, trade: dict) -> None:
        "Записує нову позицію в список відкритих"
        self.positions.append(trade)

    @_handle_error
    def close_position(self, trade: dict, pnl: float) -> None:
        """
        Знімає позицію зі списку й оновлює баланс.

        :param pnl: у доларах, зі знаком
        """
        self.positions = [p for p in self.positions if p.get('id') != trade.get('id')]
        self.balance += pnl
        self.peak = max(self.peak, self.balance)

        trade['pnl'] = pnl
        trade['balance_after'] = self.balance
        self.history.append(trade)

        self.check_kill_switch()

    #------------------------------
    # Вигляд для шару ризику
    #------------------------------

    @_handle_error
    def as_dict(self) -> dict:
        "Те, що чекають AccountGuard і PositionSizer"
        return {
            'daily_loss_pct': self.daily_loss_pct,
            'active_positions': list(self.positions),
            'total_capital': self.balance,
            'risk_per_trade_pct': self.MARGIN_PCT,
            'leverage': self.LEVERAGE,
            'max_daily_loss_pct': self.MAX_DAILY_LOSS_PCT,
        }

    #------------------------------
    # Короткий звіт
    #------------------------------

    def report(self) -> str:
        "Один рядок про стан — для логів і GUI"
        state = f"ЗУПИНЕНО ({self.stop_reason})" if self.stopped else "працює"
        return (f"баланс ${self.balance:.2f} зі ${self.start_balance:.2f} | "
                f"просідання {self.drawdown_pct:.1f}% | "
                f"за добу {self.daily_loss_pct:.1f}% | "
                f"відкрито {len(self.positions)} | угод {len(self.history)} | {state}")
