import os
import json
import datetime

from utils.PathManager import PathManager
from utils.OtherUtils import _handle_error

#==============================
# Рахунок на біржі
#==============================
#
# Відрізняється від AccountState тим, ЗВІДКИ бере правду. AccountState веде
# паперовий баланс сам: відкрив — записав, закрив — порахував. Тут баланс і
# відкриті позиції питаються в біржі, бо в живій торгівлі тільки вона знає
# напевно. Наш власний підрахунок після першої ж ліквідації або часткового
# виконання розійшовся б із рахунком, і ми б цього навіть не помітили.
#
# ЗАСТАВА РАХУЄТЬСЯ ОДИН РАЗ. При старті беремо 10% від того, що лежить на
# ф'ючерсному гаманці, і далі ця сума НЕ змінюється. Без складного відсотка:
# заробили — застава та сама, втратили — теж та сама. Так розмір угоди не
# роздувається на серії виграшів і не тане на серії програшів.
#
# РУБИЛЬНИК на 20% від стартового депозиту. Спрацювавши, не скидається:
# щоб продовжити, треба зупинити й запустити заново руками.
#==============================


class ExchangeAccount:
    "Баланс і позиції з біржі, фіксована застава й рубильник просідання"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    # Скільки балансу йде в заставу під одну угоду. Рахується ОДИН раз при старті
    MARGIN_PCT = 10.0

    # Повна зупинка при просіданні від стартового депозиту
    MAX_DRAWDOWN_PCT = 20.0

    # Плече. Двадцять п'яте основне, десяте — запасне, якщо біржа не дала
    # основного на цьому активі.
    #
    # ЗМІНЕНО З 20 НА 25 02.09.2026 на прохання господаря. Що це міняє при
    # заставі $15: обсяг угоди зростає з $300 до $375, а ліквідація присувається
    # з 10% руху проти нас до 4%. Друге важливіше за перше: стоп рахується як
    # ATR × 1.5, і коли ринок розгойдало так, що стоп виходить далі за 4%,
    # сайзер угоду відхилить — краще пропустити, ніж ставити стоп за
    # ціною ліквідації.
    LEVERAGE = 25
    LEVERAGE_FALLBACK = 10

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, exchange=None):
        """
        :param exchange: CCXTModule. Без нього рахунок працює тільки в папері
        """
        self.exchange = exchange

        self.start_balance = 0.0
        self.balance = 0.0
        self.margin_usd = 0.0

        self.stopped = False
        self.stop_reason = ''
        self.ready = False

        # Коли записано депозит і чи продовжуємо раніше початий тест
        self.baseline_date = ''
        self.continued = False

        # Плече, яке біржа справді дала, окремо по кожному активу
        self._leverage = {}

    #------------------------------
    # Старт: заміряти депозит і зафіксувати заставу
    #------------------------------

    @_handle_error
    def start(self, paper_balance: float = None, new_test: bool = False) -> bool:
        """
        Заміряє рахунок і фіксує заставу. Робиться ОДИН раз за запуск.

        :param paper_balance: чим підмінити баланс, коли біржі немає
        :param new_test: True — почати новий відлік просідання від сьогоднішнього
                         рахунку. False — продовжити раніше записаний
        :return: True, якщо рахунок заміряно
        """
        if self.ready:
            return True

        equity = None
        if self.exchange is not None:
            # Саме equity, а не вільний баланс: застава у відкритій позиції
            # нікуди не поділась і збитком не є
            equity = self.exchange.get_usdt_equity()

        if not equity:
            if paper_balance is None:
                self.stop_reason = 'Не вдалось отримати баланс з біржі'
                return False
            equity = float(paper_balance)

        self.balance = float(equity)

        # ДЕПОЗИТ ПЕРЕЖИВАЄ ПЕРЕЗАПУСК.
        #
        # Якби відлік починався заново на кожному запуску, межа в 20% нічого
        # б не тримала: втратив 20%, перезапустив — і межа поїхала за новим,
        # меншим рахунком. Домовлені $30 перетворились би на $30 щоразу.
        # Тому початковий депозит записується у файл і читається назад.
        saved = None if new_test else self._load_baseline()
        if saved:
            self.start_balance = float(saved['start_balance'])
            self.margin_usd = float(saved['margin_usd'])
            self.baseline_date = saved.get('recorded_at', '')
            self.continued = True
        else:
            self.start_balance = float(equity)
            self.margin_usd = round(self.start_balance * self.MARGIN_PCT / 100.0, 2)
            self.baseline_date = datetime.datetime.now().isoformat(timespec='seconds')
            self.continued = False
            self._save_baseline()

        self.ready = True
        return True

    #------------------------------
    # Пам'ять про депозит
    #------------------------------

    @_handle_error
    def _load_baseline(self) -> dict:
        "Читає записаний депозит. Немає файлу — None"
        path = PathManager.get_trading_state_path()
        if not path or not os.path.exists(path):
            return None
        with open(path, encoding='utf-8') as f:
            saved = json.load(f)
        return saved if saved.get('start_balance') else None

    @_handle_error
    def _save_baseline(self) -> None:
        "Записує депозит, від якого рахується просідання"
        path = PathManager.get_trading_state_path()
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'start_balance': self.start_balance,
                'margin_usd': self.margin_usd,
                'max_drawdown_pct': self.MAX_DRAWDOWN_PCT,
                'recorded_at': self.baseline_date,
            }, f, indent=4)

    @classmethod
    @_handle_error
    def saved_baseline(cls) -> dict:
        "Що вже записано. Інтерфейс питає це перед стартом"
        path = PathManager.get_trading_state_path()
        if not path or not os.path.exists(path):
            return None
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    #------------------------------
    # Поточний баланс
    #------------------------------

    @_handle_error
    def refresh(self) -> float:
        """
        Перепитує баланс. Застава з нього НЕ перераховується — вона зафіксована
        на старті. Баланс потрібен лише для рубильника й для показу в інтерфейсі.
        """
        if self.exchange is None:
            return self.balance

        # Знову equity: інакше відкрита позиція сама по собі виглядала б
        # як просідання на розмір застави
        equity = self.exchange.get_usdt_equity()
        if equity:
            self.balance = float(equity)
        return self.balance

    @property
    def drawdown_pct(self) -> float:
        "Скільки відсотків втрачено від стартового депозиту"
        if self.start_balance <= 0:
            return 0.0
        return max(0.0, (self.start_balance - self.balance) / self.start_balance * 100.0)

    #------------------------------
    # Рубильник
    #------------------------------

    @_handle_error
    def check_kill_switch(self) -> bool:
        """
        Просідання на 20% від старту — вимикаємось до ручного втручання.

        :return: True, якщо торгівля зупинена
        """
        if self.stopped:
            return True

        if self.ready and self.drawdown_pct >= self.MAX_DRAWDOWN_PCT:
            self.stopped = True
            self.stop_reason = (
                f"Просідання {self.drawdown_pct:.1f}% від старту "
                f"(${self.start_balance - self.balance:.2f}) — межа {self.MAX_DRAWDOWN_PCT}%"
            )
        return self.stopped

    #------------------------------
    # Відкриті позиції з біржі
    #------------------------------

    def open_positions(self, pairs: list):
        """
        Що зараз відкрито НА БІРЖІ.

        Свій список не ведемо навмисно: позицію могло закрити стопом, тейком
        або ліквідацією без нашої участі, і біржа — єдиний, хто це знає.

        РІЗНИЦЯ МІЖ «ПОРОЖНЬО» І «НЕ ЗНАЮ» ТУТ КОШТУЄ ГРОШЕЙ, тому метод
        свідомо БЕЗ _handle_error. Той декоратор повертає None на будь-якій
        помилці, і якби ми, як раніше, писали `or {}`, то збій зв'язку з
        біржею читався б як «вільно» — і ми відкрили б другу позицію поверх
        наявної. Тепер невдача повертає None, а водій циклу на None не торгує.

        :return: {'SOLUSDT': позиція, ...}, порожній словник — вільно,
                 None — спитати не вдалось
        """
        if self.exchange is None:
            return {}

        try:
            positions = self.exchange.fetch_positions(list(pairs))
        except Exception as e:
            print(f'[ExchangeAccount] Не вдалось спитати позиції: {e}')
            return None

        # CCXTModule сам загорнутий у _handle_error, тож None означає збій,
        # а не порожній рахунок
        if positions is None:
            return None
        return positions

    def has_open_position(self, pairs: list) -> bool:
        "Чи є відкрита позиція. Невідомо — вважаємо, що є: так безпечніше"
        positions = self.open_positions(pairs)
        return positions is None or bool(positions)

    #------------------------------
    # Плече під актив
    #------------------------------

    @_handle_error
    def ensure_leverage(self, pair: str):
        """
        Ставить плече на активі: спершу 20, і лише якщо не вийшло — 10.
        Потім ОБОВ'ЯЗКОВО перепитує біржу, що там стоїть насправді.

        ЧОМУ ПЕРЕПИТУЄМО. Прохання поставити плече може тихо не пройти —
        права ключа, обмеження активу, що завгодно. Раніше в такому разі
        метод просто повертав 10 і йшов далі, хоча на біржі могло стояти
        будь-що. А з плеча рахується обсяг позиції: помилка вдвічі означає
        вдвічі більшу заставу, ніж домовлено. Тому рахуємо з того числа,
        яке біржа підтвердила, а не з того, яке ми просили.

        :return: підтверджене плече, або None — тоді торгувати не можна
        """
        if pair in self._leverage:
            return self._leverage[pair]

        if self.exchange is None:
            self._leverage[pair] = self.LEVERAGE
            return self.LEVERAGE

        # Не просимо більше, ніж актив дозволяє. Межа лежить в описі ринку,
        # питати біржу окремо не треба
        ceiling = self.exchange.max_leverage(pair)
        wanted = self.LEVERAGE
        if ceiling and wanted > ceiling:
            wanted = int(ceiling)
            print(f'[ExchangeAccount] {pair}: {self.LEVERAGE}x понад межу активу, '
                  f'просимо {wanted}x')

        for leverage in (wanted, self.LEVERAGE_FALLBACK):
            try:
                self.exchange.set_leverage(pair, leverage)
                break
            except Exception as e:
                print(f'[ExchangeAccount] {pair}: плече {leverage}x не вийшло — {e}')

        actual = self.exchange.fetch_leverage(pair)
        if not actual:
            # Не знаємо плеча — не знаємо й розміру позиції. Не вгадуємо
            print(f'[ExchangeAccount] {pair}: не вдалось дізнатись плече на біржі')
            return None

        actual = int(float(actual))
        if actual != wanted:
            print(f'[ExchangeAccount] {pair}: на біржі стоїть {actual}x, '
                  f'а не {wanted}x — рахуємо обсяг за {actual}x')

        self._leverage[pair] = actual
        return actual

    #------------------------------
    # Вигляд для шару ризику
    #------------------------------

    @_handle_error
    def as_dict(self, pair: str = None) -> dict:
        """
        Те, що чекають AccountGuard і PositionSizer.

        margin_usd тут головніший за risk_per_trade_pct: сайзер, побачивши
        його, візьме саме цю суму, а не відсоток від поточного балансу.
        """
        return {
            'daily_loss_pct': self.drawdown_pct,
            'max_daily_loss_pct': self.MAX_DRAWDOWN_PCT,
            'active_positions': [],
            'total_capital': self.balance,
            'margin_usd': self.margin_usd,
            'risk_per_trade_pct': self.MARGIN_PCT,
            'leverage': self._leverage.get(pair, self.LEVERAGE),
            'asset': pair or '',
        }

    #------------------------------
    # Короткий звіт
    #------------------------------

    def report(self) -> str:
        "Один рядок про стан — для журналу й інтерфейсу"
        if not self.ready:
            return 'баланс ще не заміряно'

        state = f"ЗУПИНЕНО ({self.stop_reason})" if self.stopped else 'працює'
        return (f"баланс ${self.balance:.2f} зі ${self.start_balance:.2f} | "
                f"застава ${self.margin_usd:.2f} | "
                f"просідання {self.drawdown_pct:.1f}% | {state}")
