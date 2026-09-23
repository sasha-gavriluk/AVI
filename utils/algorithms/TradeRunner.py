import time
import datetime

from utils.DataBaseManager import DataBaseManager
from utils.OtherUtils import _handle_error
from utils.algorithms.ChronoSeerService import ChronoSeerService
from utils.algorithms.MarketDataRefresher import MarketDataRefresher
from utils.algorithms.brain.ExchangeAccount import ExchangeAccount
from utils.algorithms.brain.DecisionEngine import DecisionEngine
from utils.algorithms.brain.OrderExecutor import OrderExecutor
from utils.algorithms.brain.TradeJournal import TradeJournal

#==============================
# Водій торгового циклу
#==============================
#
# Той, хто ставить питання «що робити ЗАРАЗ». Чекає закриття свічки, оновлює
# дані, обходить активи, вибирає одну найкращу угоду й веде її до біржі.
#
# ЛАНЦЮГ ОДНОГО ТАКТУ:
#     1. баланс з біржі, перевірка рубильника
#     2. відкриті позиції з біржі — якщо є хоч одна, нових не відкриваємо
#     3. свіжі свічки (три потоки, три таймфрейми)
#     4. фічі -> база -> мережа, по кожному активу
#     5. вибір найкращого вердикту з усіх активів і горизонтів
#     6. новини, запізнення, сайзинг
#     7. ордер на біржу
#
# ОДНА ПОЗИЦІЯ НА ВЕСЬ РАХУНОК. Поки на біржі щось відкрито, нових угод не
# ставимо взагалі. Заміряно 01.09.2026: п'ять активів одночасно дали BUY із
# впевненістю 82-94% — тобто це одна ставка п'ятикратним розміром під виглядом
# п'яти різних. Правда про відкрите береться в біржі, а не з власного списку:
# позицію могло закрити стопом чи ліквідацією без нашої участі.
#
# ЧОМУ ЧЕКАЄМО ЗАКРИТТЯ СВІЧКИ. Мережа вчилась на закритих свічках. Та, що ще
# формується, має інші максимум, мінімум і закриття — це просто інші дані.
#
# ПРО БЮДЖЕТ У 30 СЕКУНД. Збірка фічей коштує близько 4.2 секунди НА АКТИВ і
# потоками не пришвидшується (заміряно 02.09.2026, GIL). Тобто десять активів
# це ~42 секунди — більше за бюджет, і остання пара в черзі не встигне.
# Тому такт міряє час і пише його в журнал: видно, чи бюджет тримається.
# Якщо не тримається — або менше активів, або більший бюджет у OrderGuard.
#==============================


class TradeRunner:
    "Будить логіку на кожній новій свічці й веде одну угоду на весь рахунок"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    BAR_MINUTES = 15

    # Скільки чекати після закриття свічки, перш ніж питати біржу. Біржа
    # віддає останню свічку не миттєво, і без паузи ми стабільно тягнули б
    # передостанню. Тримаємо коротко: ці секунди йдуть із бюджету в 30
    SETTLE_SEC = 5

    # Поріг впевненості. Нуль означає «порогу немає»: беремо найкраще з того,
    # що дала мережа, яким би воно не було.
    #
    # ЗНЯТО 02.09.2026 на прохання господаря. Раніше стояло 0.70 і такт міг
    # закінчитись нічим. Що варто пам'ятати: на 117 750 рішеннях кошик 50-55%
    # впевненості дав 34.8% плюсових угод, а кошик 80%+ — 60.9%. Тобто угоди
    # з низькою впевненістю не просто гірші, вони збиткові. Повернути поріг —
    # це змінити нуль назад на 0.70, більше нічого чіпати не треба.
    MIN_CONFIDENCE = 0.0

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, pairs: list, db: DataBaseManager = None, exchange=None,
                 live: bool = False, paper_balance: float = 150.0,
                 new_test: bool = False, on_state=None, on_log=None):
        """
        :param pairs: ['SOLUSDT', 'BTCUSDT', ...]
        :param exchange: CCXTModule. None — працюємо на тому, що вже є в базі
        :param live: True — ставити справжні ордери. Вимагає exchange
        :param paper_balance: чим підмінити баланс, коли біржі немає
        :param new_test: True — почати новий відлік просідання від сьогоднішнього
                         рахунку, забувши раніше записаний депозит
        :param on_state: куди віддавати стан такту (інтерфейсу)
        :param on_log: куди віддавати рядки журналу (інтерфейсу)
        """
        self.pairs = list(pairs)
        self.db = db or DataBaseManager()
        self.exchange = exchange
        self.live = bool(live and exchange is not None)
        self.paper_balance = paper_balance
        self.new_test = bool(new_test)

        self.account = ExchangeAccount(exchange=exchange)
        self.refresher = MarketDataRefresher(exchange=exchange)
        self.service = ChronoSeerService(db=self.db)
        self.engine = DecisionEngine()
        self.executor = OrderExecutor(exchange=exchange, live=self.live)
        self.journal = TradeJournal(db=self.db, mode='live' if self.live else 'paper')

        self.on_state = on_state
        self.on_log = on_log

        self.running = False
        self.ticks = 0

        # Угоди, які ми відкрили й за якими стежимо: пара -> запис.
        # Зникла з біржі — значить закрилась, і це треба дописати в журнал
        self.watched = {}

    #------------------------------
    # Зв'язок з інтерфейсом
    #------------------------------

    def log(self, message: str) -> None:
        "Рядок у журнал. Без інтерфейсу — просто в консоль"
        print(f'[TradeRunner] {message}', flush=True)
        if self.on_log:
            self.on_log(message)

    def emit(self, state: dict) -> None:
        "Віддає стан такту інтерфейсу"
        if self.on_state:
            self.on_state(state)

    @_handle_error
    def idle_state(self, message: str) -> dict:
        """
        Стан для міжчасся: розгін і очікування свічки.

        Потрібен, щоб після натискання «Старт» вкладка одразу показала баланс
        і заставу, а не стояла порожньою до чверті години, доки не закриється
        перша свічка.
        """
        return {
            'tick': self.ticks,
            'balance': self.account.balance,
            'start_balance': self.account.start_balance,
            'margin_usd': self.account.margin_usd,
            'drawdown_pct': self.account.drawdown_pct,
            'stopped': False,
            'waiting': True,
            'position': None,
            'signal': None,
            'block_reason': message,
            'verdicts': {},
        }

    #------------------------------
    # Очікування закриття свічки
    #------------------------------

    @_handle_error
    def seconds_to_next_bar(self) -> float:
        "Скільки секунд лишилось до закриття поточної свічки плюс пауза на біржу"
        now = datetime.datetime.now(datetime.timezone.utc)
        step = self.BAR_MINUTES * 60
        passed = (now.minute % self.BAR_MINUTES) * 60 + now.second + now.microsecond / 1e6
        return step - passed + self.SETTLE_SEC

    @_handle_error
    def wait_for_bar(self) -> None:
        "Спить до закриття наступної свічки. Прокидається, якщо цикл спинили"
        target = time.monotonic() + self.seconds_to_next_bar()
        while self.running and time.monotonic() < target:
            time.sleep(min(1.0, max(0.0, target - time.monotonic())))

    #------------------------------
    # Старт: заміряти депозит
    #------------------------------

    @_handle_error
    def next_bar_at(self) -> str:
        "О котрій закриється наступна свічка. Для журналу й інтерфейсу"
        now = datetime.datetime.now(datetime.timezone.utc)
        step = datetime.timedelta(minutes=self.BAR_MINUTES)
        floor = now.replace(minute=now.minute - now.minute % self.BAR_MINUTES,
                            second=0, microsecond=0)
        return (floor + step).strftime('%H:%M')

    #------------------------------
    # Розгін: дані до першого такту
    #------------------------------

    @_handle_error
    def warmup(self) -> None:
        """
        Довантажує свічки ДО того, як почнеться робота.

        НАВІЩО ОКРЕМИМ КРОКОМ. Бота можна натиснути посеред свічки — і майже
        завжди так і буває. Свічка, яка ще формується, має інші максимум,
        мінімум і закриття, ніж матиме за десять хвилин; мережа вчилась на
        закритих, тож рішення на недороблених — це рішення на інших даних.
        Тому при старті ми ТІЛЬКИ качаємо історію, а потім чекаємо, доки
        поточна свічка закриється, і аж тоді робимо перший такт.

        Заразом це латає діру, якщо бот стояв вимкненим кілька годин.
        """
        self.log('Розгін: качаємо свічки...')
        self.refresher.refresh_all(self.pairs)

        for pair, err in (self.refresher.last_errors or {}).items():
            self.log(f'{pair}: {err}')

        self.log(f'Дані завантажено. Чекаємо закриття свічки о {self.next_bar_at()} UTC — '
                 f'з середини свічки не починаємо')

    @_handle_error
    def prepare(self) -> bool:
        """
        Питає біржу про баланс і фіксує заставу. Робиться ОДИН раз за запуск.

        :return: True, якщо можна торгувати
        """
        if not self.account.start(paper_balance=self.paper_balance,
                                  new_test=self.new_test):
            self.log(f'Старт неможливий: {self.account.stop_reason}')
            return False

        if self.account.continued:
            self.log(f'Продовжуємо тест від депозиту ${self.account.start_balance:.2f} '
                     f'(записано {self.account.baseline_date[:16].replace("T", " ")})')
        else:
            self.log(f'Новий тест. Депозит ${self.account.start_balance:.2f}')

        self.adopt_open_trades()

        limit = self.account.start_balance * self.account.MAX_DRAWDOWN_PCT / 100.0
        self.log(f'Застава на угоду ${self.account.margin_usd:.2f} '
                 f'({self.account.MARGIN_PCT:.0f}%, рахується один раз) | '
                 f'рахунок зараз ${self.account.balance:.2f} | '
                 f'зупинка на ${self.account.start_balance - limit:.2f} '
                 f'(мінус ${limit:.2f})')
        return True

    #------------------------------
    # Облік закритих угод
    #------------------------------

    @_handle_error
    def adopt_open_trades(self) -> None:
        """
        Підбирає угоди, які лишились відкритими в журналі з минулого запуску.

        Без цього перезапуск втрачав би зв'язок із власною угодою: позиція
        собі закрилась би на біржі, а рядок у журналі назавжди лишився б
        зі статусом open, і підсумок тесту не було б з чого рахувати.
        """
        rows = self.journal.open_trades()
        if rows is None or rows.empty:
            return

        for _, row in rows.iterrows():
            self.watched[row['pair']] = {
                'id': row['id'],
                'pair': row['pair'],
                'direction': row['direction'],
                'entry_price': float(row['entry_price'] or 0.0),
                'stop_price': float(row['stop_price'] or 0.0),
                'target_price': float(row['target_price'] or 0.0),
                'opened_at': int(row['opened_at'] or 0),
                'bars_held': int(row['bars_held'] or 0),
            }

        self.log(f'Підхоплено незакритих угод у журналі: {len(self.watched)}')

    @_handle_error
    def settle_closed(self, positions: dict) -> list:
        """
        Дописує в журнал ті угоди, яких на біржі вже немає.

        Стоп і тейк спрацьовують без нас, тому єдиний спосіб дізнатись про
        закриття — помітити, що позиція зникла зі списку біржі, і піти
        спитати в журналі закритих позицій, чим воно скінчилось.

        :param positions: що біржа зараз показує відкритим
        :return: список подій для інтерфейсу
        """
        events = []
        open_pairs = set(positions or {})

        for pair, trade in list(self.watched.items()):
            if pair in open_pairs:
                trade['bars_held'] = trade.get('bars_held', 0) + 1
                continue

            closed = self.journal_close(pair, trade)
            if closed:
                events.append(closed)
            self.watched.pop(pair, None)

        return events

    @_handle_error
    def journal_close(self, pair: str, trade: dict) -> dict:
        """
        Питає біржу про результат і закриває рядок у журналі.

        Якщо біржа не змогла відповісти, рядок усе одно закривається — але
        з чесною позначкою, що цифри невідомі. Вічно відкритий рядок гірший
        за закритий із прогалиною: перший тихо псує будь-який підсумок.
        """
        info = None
        if self.exchange is not None:
            info = self.exchange.fetch_closed_position(pair, since=trade.get('opened_at'))

        exit_price, pnl, closed_at = 0.0, 0.0, 0
        reason = 'закрито поза ботом'

        if info:
            raw = info.get('info') or {}
            exit_price = float(info.get('markPrice') or raw.get('avgExitPrice')
                               or raw.get('exitPrice') or 0.0)
            pnl = float(info.get('realizedPnl') or raw.get('closedPnl') or 0.0)
            closed_at = int(info.get('timestamp') or raw.get('updatedTime') or 0)
            reason = self._exit_reason(trade, exit_price, pnl)

        self.journal.on_close(trade, exit_price, reason, pnl,
                              self.account.balance, closed_at)

        self.log(f'Угода {pair} закрита: {reason}, вихід {exit_price or "?"}, '
                 f'результат {pnl:+.2f} USDT')
        return {'pair': pair, 'reason': reason, 'exit_price': exit_price, 'pnl': pnl}

    @staticmethod
    def _exit_reason(trade: dict, exit_price: float, pnl: float) -> str:
        """
        Чим скінчилась угода. Визначаємо за ціною виходу: до чого ближче
        стала, те й спрацювало. Знак прибутку — запасний варіант, коли
        рівні невідомі.
        """
        stop = trade.get('stop_price') or 0.0
        target = trade.get('target_price') or 0.0

        if exit_price and stop and target:
            return 'стоп' if abs(exit_price - stop) <= abs(exit_price - target) else 'тейк'
        if pnl:
            return 'тейк' if pnl > 0 else 'стоп'
        return 'закрито поза ботом'

    #------------------------------
    # Вердикти по всіх активах
    #------------------------------

    @_handle_error
    def collect_verdicts(self) -> dict:
        """
        Обходить активи по черзі: фічі -> база -> мережа.

        Послідовно навмисно: рахунок фічей потоками не пришвидшується, а от
        одна база DuckDB від паралельного запису тільки страждає.

        :return: {'SOLUSDT': вердикт, ...}
        """
        verdicts = {}
        for pair in self.pairs:
            if not self.running:
                break
            verdict = self.service.process(pair)
            if verdict and 'horizons' in verdict:
                verdicts[pair] = verdict
            else:
                self.log(f'{pair}: мережа не дала вердикту')
        return verdicts

    #------------------------------
    # Вибір найкращої угоди
    #------------------------------

    @_handle_error
    def pick_best(self, verdicts: dict) -> dict:
        """
        Одна угода з усього: найбільша впевненість серед усіх активів
        і всіх горизонтів мережі.

        Мережа дає три горизонти на кожен актив, кожен зі своїм напрямком,
        стопом, ціллю й впевненістю. Беремо один максимум по всій таблиці —
        і горизонт при ньому теж запам'ятовуємо, бо стоп із ціллю в кожного свої.

        :return: найкраще або None, якщо ніхто не перетнув поріг
        """
        best = None
        for pair, verdict in (verdicts or {}).items():
            for horizon, h in (verdict.get('horizons') or {}).items():
                if h.get('confidence', 0.0) < self.MIN_CONFIDENCE:
                    continue
                if best is None or h['confidence'] > best['confidence']:
                    best = {
                        'pair': pair,
                        'horizon': horizon,
                        'direction': h['direction'],
                        'confidence': h['confidence'],
                        'stop_price': h['stop_price'],
                        'target_price': h['target_price'],
                        'price': verdict['price'],
                        'timestamp': verdict['timestamp'],
                    }
        return best

    #------------------------------
    # Постановка угоди
    #------------------------------

    @_handle_error
    def place_trade(self, best: dict, bar_closed_at: float) -> dict:
        """
        Проводить обрану угоду крізь шар ризику й ставить ордер.

        Виконується в ОДНОМУ потоці — тому, що крутить цикл. Паралельно тут
        робити нічого: угода одна, а два потоки на одному рахунку неминуче
        колись поставлять дві.

        :param bar_closed_at: мітка time.monotonic() закриття свічки. Від неї
                              сторож рахує бюджет у 30 секунд
        """
        import pandas as pd

        pair = best['pair']

        # Годинник іде від СВІЧКИ, а не від цієї миті
        intent = self.executor.begin(started=bar_closed_at)

        # Плече ставимо до ордера й звіряємо з тим, що показує біржа.
        # Не знаємо плеча — не знаємо розміру позиції, тому не торгуємо
        leverage = self.account.ensure_leverage(pair)
        if not leverage:
            return {'placed': False,
                    'reason': f'Не вдалось підтвердити плече на {pair}'}

        candle = pd.Series({
            'close': best['price'],
            'high': best['price'],
            'low': best['price'],
            'timestamp': best['timestamp'],
        })

        decision = self.engine.evaluate(
            verdict=best,
            row=candle,
            account_state=self.account.as_dict(pair),
        )
        if not decision or not decision.get('allowed'):
            reason = (decision or {}).get('reason', 'Відмова шару ризику')
            return {'placed': False, 'reason': reason}

        decision['leverage'] = leverage
        decision['horizon'] = best['horizon']

        self.executor.aim(intent, best['price'], best['direction'])
        fill = self.executor.place(intent, decision, pair)
        if not fill or not fill.get('filled'):
            return {'placed': False, 'reason': (fill or {}).get('reason', 'Ордер не виконано')}

        # Записуємо угоду за ціною ВИКОНАННЯ, а не за ціною рішення
        trade = {
            'id': str(fill.get('order_id') or int(time.time()))[:32],
            'pair': pair,
            'direction': best['direction'],
            'entry_price': fill['price'],
            'stop_price': decision['stop_price'],
            'target_price': decision.get('target_price'),
            'liquidation_price': decision.get('liquidation_price'),
            'confidence': best['confidence'],
            'position_size': decision.get('position_size_usd'),
            'margin': decision.get('margin_required_usd'),
            'opened_at': best['timestamp'],
        }
        self.journal.on_open(trade, horizon=best['horizon'], leverage=leverage,
                             balance=self.account.balance)

        # Тепер за нею стежимо: коли зникне з біржі, допишемо підсумок
        trade['bars_held'] = 0
        self.watched[pair] = trade

        return {'placed': True, 'trade': trade, 'leverage': leverage,
                'delay_sec': fill.get('delay_sec'), 'slip_pct': fill.get('slip_pct'),
                'order_id': fill.get('order_id')}

    #------------------------------
    # Один такт
    #------------------------------

    @_handle_error
    def tick(self, dry_run: bool = False) -> dict:
        """
        Повний ланцюг на одній свічці.

        :param dry_run: True — усе порахувати й показати, але ордер не ставити
        :return: стан такту для інтерфейсу
        """
        self.ticks += 1
        bar_closed_at = time.monotonic() - self.SETTLE_SEC
        started = time.monotonic()

        state = {
            'tick': self.ticks,
            'time': datetime.datetime.now(datetime.timezone.utc).strftime('%d.%m %H:%M'),
            'balance': self.account.balance,
            'start_balance': self.account.start_balance,
            'margin_usd': self.account.margin_usd,
            'drawdown_pct': self.account.drawdown_pct,
            'stopped': False,
            'position': None,
            'signal': None,
            'block_reason': '',
            'events': [],
            'verdicts': {},
        }

        # 1. Баланс і рубильник
        self.account.refresh()
        state['balance'] = self.account.balance
        state['drawdown_pct'] = self.account.drawdown_pct

        if self.account.check_kill_switch():
            state['stopped'] = True
            state['block_reason'] = self.account.stop_reason
            self.log(f'РУБИЛЬНИК: {self.account.stop_reason}')
            self.running = False
            self.emit(state)
            return state

        # 2. Що вже відкрито НА БІРЖІ.
        # None означає, що спитати не вдалось. Тоді не торгуємо: краще
        # пропустити свічку, ніж покласти другу позицію поверх наявної
        positions = self.account.open_positions(self.pairs)
        if positions is None:
            state['block_reason'] = 'Біржа не відповіла про позиції — такт пропущено'
            self.log(state['block_reason'])
            self.emit(state)
            return state

        # Чи не закрилось щось із нашого, поки нас не питали
        state['events'] = self.settle_closed(positions) or []

        if positions:
            pair, position = next(iter(positions.items()))
            state['position'] = {
                'pair': pair,
                'side': position.get('side'),
                'entry_price': position.get('entryPrice'),
                'size': position.get('contracts') or position.get('size'),
                'pnl': position.get('unrealizedPnl'),
            }
            state['block_reason'] = f'Угода на {pair} відкрита — нових не ставимо'
            self.log(state['block_reason'])
            self.emit(state)
            return state

        # 3. Свіжі свічки — три потоки
        self.refresher.refresh_all(self.pairs)
        if self.refresher.last_errors:
            for pair, err in self.refresher.last_errors.items():
                self.log(f'{pair}: {err}')

        # 4. Фічі -> база -> мережа
        verdicts = self.collect_verdicts()
        state['verdicts'] = {
            pair: {
                'price': v['price'],
                'horizons': {h: {'direction': d['direction'],
                                 'confidence': round(d['confidence'], 3)}
                             for h, d in v['horizons'].items()},
            }
            for pair, v in (verdicts or {}).items()
        }

        # 5. Найкраще з усього
        best = self.pick_best(verdicts)
        state['elapsed_sec'] = round(time.monotonic() - started + self.SETTLE_SEC, 1)

        if best is None:
            # Без порогу сюди можна потрапити лише тоді, коли мережа не дала
            # взагалі нічого — а це вже не «сигналу немає», а поламані дані
            state['block_reason'] = (
                'Мережа не дала жодного вердикту — перевір дані' if not verdicts
                else f'Жоден актив не перетнув поріг {self.MIN_CONFIDENCE * 100:.0f}%')
            self.log(f"такт {self.ticks}: {state['block_reason']} "
                     f"({state['elapsed_sec']} с)")
            self.emit(state)
            return state

        state['signal'] = best
        self.log(f"такт {self.ticks}: {best['pair']} {best['direction']} "
                 f"{best['confidence'] * 100:.1f}% горизонт {best['horizon']} "
                 f"({state['elapsed_sec']} с від свічки)")

        if dry_run:
            state['block_reason'] = 'Режим перегляду — ордер не ставимо'
            self.emit(state)
            return state

        # 6-7. Ризик і ордер
        result = self.place_trade(best, bar_closed_at)
        if not result or not result.get('placed'):
            state['block_reason'] = (result or {}).get('reason', 'Ордер не поставлено')
            self.log(f"   відмова: {state['block_reason']}")
        else:
            trade = result['trade']
            state['position'] = {
                'pair': trade['pair'],
                'side': trade['direction'],
                'entry_price': trade['entry_price'],
                'size': trade['position_size'],
                'pnl': 0.0,
            }
            self.log(f"   УГОДА: {trade['pair']} {trade['direction']} "
                     f"вхід {trade['entry_price']} стоп {trade['stop_price']} "
                     f"ціль {trade['target_price']} плече {result['leverage']}x "
                     f"(запізнення {result.get('delay_sec')} с)")

        self.emit(state)
        return state

    #------------------------------
    # Головний цикл
    #------------------------------

    @_handle_error
    def run(self, ticks: int = None, dry_run: bool = False,
            wait_first_bar: bool = True) -> None:
        """
        Крутиться, доки не спинять.

        :param ticks: скільки тактів зробити. None — доки не викличуть stop()
        :param dry_run: True — цикл рахує й показує, але не торгує
        :param wait_first_bar: True — після розгону дочекатись закриття свічки
                               й аж тоді працювати. Вимикати можна тільки для
                               перевірок: у живій торгівлі старт посеред свічки
                               означає рішення на недороблених даних
        """
        self.running = True
        mode = 'ПЕРЕГЛЯД' if dry_run else ('ЖИВИЙ' if self.live else 'ПАПІР')
        self.log(f'Старт. Режим: {mode}. Активів: {len(self.pairs)}')

        if not self.prepare():
            self.running = False
            return

        # Баланс і застава мають з'явитись в інтерфейсі одразу, ще до того,
        # як почнеться очікування свічки
        self.emit(self.idle_state('Розгін: качаємо дані'))

        try:
            if wait_first_bar:
                self.warmup()
                self.emit(self.idle_state(
                    f'Чекаємо закриття свічки о {self.next_bar_at()} UTC'))
                self.wait_for_bar()

            while self.running:
                self.tick(dry_run=dry_run)

                if ticks is not None and self.ticks >= ticks:
                    break

                self.wait_for_bar()
                if not self.running:
                    break
        except KeyboardInterrupt:
            self.log('Зупинено з клавіатури')
        finally:
            self.running = False
            self.refresher.stop()
            self.log(f'Стоп. {self.account.report()}')

    @_handle_error
    def stop(self) -> None:
        "Просить цикл завершитись. Поточний такт дороблюється до кінця"
        self.running = False
