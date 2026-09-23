import pandas as pd

from utils.OtherUtils import _handle_error
from utils.algorithms.ChronoSeerService import ChronoSeerService
from utils.algorithms.brain.DecisionEngine import DecisionEngine
from utils.algorithms.brain.AccountState import AccountState
from utils.algorithms.brain.PositionKeeper import PositionKeeper
from utils.algorithms.brain.TradeJournal import TradeJournal
from utils.algorithms.brain.OrderExecutor import OrderExecutor

#==============================
# Точка входу крипто-логіки
#==============================
#
# ЩО ЗМІНИЛОСЬ 01.09.2026. Раніше цей клас готував дані й віддавав їх у
# конвеєр правил, який сам вирішував, куди заходити. Конвеєр прибрано.
#
# Тепер ланцюг такий:
#
#   ChronoSeerService  — збирає сет, зберігає в базу, питає мережу
#          ↓  вердикт: бік, впевненість, стоп, ціль
#   DecisionEngine     — шар ризику: новини, стан рахунку, кореляція, сайзинг
#          ↓  дозвіл із розміром позиції
#   PositionKeeper     — відкриває угоду й веде її до закриття
#
# Мережа відповідає за «куди», конвеєр — за «чи можна й скільки».
#==============================


class FCryptoLogic:
    "Зв'язує мережу, шар ризику й ведення позицій в один ланцюг"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    # Який горизонт слухаємо. На бойових тестах 31.08 п'ятнадцятисвічковий
    # дав найбільше грошей у вибірковому режимі, п'ятдесятисвічковий — те саме
    # меншою кількістю угод.
    HORIZON = 15

    # Нижче цієї впевненості вхід не розглядається. Заміряно на 117 750
    # рішеннях: кошик 50-55% дає 34.8% плюсових угод, кошик 80%+ дає 60.9%.
    MIN_CONFIDENCE = 0.70

    MAX_POSITIONS = 1

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, pair: str, account: AccountState = None, db=None,
                 engine: DecisionEngine = None, journal: TradeJournal = None,
                 keeper: PositionKeeper = None, executor: OrderExecutor = None,
                 service: ChronoSeerService = None):
        """
        :param pair: 'SOLUSDT'
        :param account: стан рахунку. None — створити свій зі $150
        :param db: менеджер бази для ChronoSeerService

        ЧОМУ РЕШТА ПАРАМЕТРІВ ЗОВНІШНІ. Коли кожна пара створює собі власний
        рахунок і власного доглядача, вони одна про одну не знають — і
        CorrelationGuard не бачить, що на всіх монетах уже відкрито в один бік.
        Заміряно 01.09.2026: п'ять монет дали BUY одночасно, і кожна зайшла б
        повним розміром. Тому TradeRunner створює це один раз і роздає всім.

        Поодинці клас теж працює: чого не передали — створить сам.
        """
        self.pair = pair
        self.account = account or AccountState()
        self.service = service or ChronoSeerService(db=db)
        self.engine = engine or DecisionEngine()
        # Журнал пише кожну угоду в базу ОДРАЗУ — і при відкритті, і при закритті
        self.journal = journal or TradeJournal(db=db)
        self.keeper = keeper or PositionKeeper(self.account, self.engine,
                                               journal=self.journal)
        # Без біржі виконавець працює в папері, але шлях і перевірки ті самі
        self.executor = executor or OrderExecutor()

    #------------------------------
    # Головний метод обробки
    #------------------------------

    @_handle_error
    def process(self, df: pd.DataFrame = None, dry_run: bool = False) -> dict:
        """
        Один крок на новій свічці: провести відкриті позиції, спитати мережу,
        пропустити крізь ризик і, якщо все дозволено, відкрити угоду.

        :param df: свіжі свічки. None — узяти з бази
        :param dry_run: True — тільки показати рішення, НЕ відкривати позицію
                        і не чіпати відкриті. Саме цей режим потрібен інтерфейсу:
                        він лише малює картку сигналу, а торгувати не має права.
        :return: словник стану для GUI й бектесту
        """
        result = {
            'pair': self.pair,
            'signal': 'NEUTRAL',
            'confidence': 0.0,
            'block_reason': '',
            'account': self.account.report(),
            'events': [],
        }

        # Годинник пускаємо ДО мережі. Збірка фічей коштує близько чотирьох
        # секунд, і це теж запізнення — сторож має його бачити.
        intent = None if dry_run else self.executor.begin()

        # 1. Мережа. Вона ж оновить сет у базі.
        verdict = self.service.process(self.pair, df_15m=df)
        no_verdict = verdict is None or 'horizons' not in verdict
        if no_verdict:
            result['block_reason'] = 'Мережа не дала вердикту'
            return result

        candle = pd.Series({
            'close': verdict['price'],
            'high': verdict['price'],
            'low': verdict['price'],
            'timestamp': verdict['timestamp'],
            'ATR_14': verdict['atr_pct'],
        })
        if df is not None and not df.empty:
            candle = df.iloc[-1]

        # 2. Провести вже відкриті позиції через цю свічку.
        # У режимі перегляду не чіпаємо нічого: інтерфейс може оновлюватись
        # довільно часто, і кожне оновлення двигало б позиції на крок уперед.
        if not dry_run:
            result['events'] = self.keeper.on_candle(candle, self.pair)

        h = verdict['horizons'].get(self.HORIZON)
        if h is None:
            result['block_reason'] = f'Немає горизонту {self.HORIZON}'
            return result

        result['confidence'] = round(h['confidence'], 3)
        result['horizons'] = verdict['horizons']

        # 3. Рубильник і місце під нову позицію
        if self.account.check_kill_switch():
            result['block_reason'] = self.account.stop_reason
            return result

        if not self.keeper.has_room(self.MAX_POSITIONS, self.pair):
            # Дві різні причини, і плутати їх шкідливо: перша каже «ця монета
            # зайнята», друга — «рахунок повний». У журналі такту видно, чи
            # стеля справді тримає, чи ми просто товчемось на одній монеті.
            busy = any(p.get('pair') == self.pair for p in self.account.positions)
            result['block_reason'] = ('Позиція на цій монеті вже відкрита' if busy
                                      else f'Стеля позицій вичерпана ({self.MAX_POSITIONS})')
            return result

        # 4. Поріг впевненості
        if h['confidence'] < self.MIN_CONFIDENCE:
            result['block_reason'] = (f"Впевненість {h['confidence']*100:.1f}% "
                                         f"нижча за поріг {self.MIN_CONFIDENCE*100:.0f}%")
            return result

        # 5. Шар ризику
        decision = self.engine.evaluate(
            verdict={'direction': h['direction'], 'confidence': h['confidence'],
                     'stop_price': h['stop_price'], 'target_price': h['target_price']},
            row=candle,
            account_state={**self.account.as_dict(), 'asset': self.pair}
        )
        if not decision or not decision.get('allowed'):
            result['block_reason'] = (decision or {}).get('reason', 'Відмова шару ризику')
            return result

        # 6. Ордер. Сторож може скасувати його вже після всіх дозволів —
        # якщо ціна пішла проти нас або ми надто довго думали.
        decision['horizon'] = self.HORIZON
        result.update({
            'signal': h['direction'],
            'stop_price': decision['stop_price'],
            'take_profit_price': decision.get('target_price'),
            'liquidation_price': decision.get('liquidation_price'),
            'dry_run': dry_run,
        })

        if dry_run:
            result['account'] = self.account.report()
            return result

        self.executor.aim(intent, verdict['price'], h['direction'])
        fill = self.executor.place(intent, decision, self.pair)
        if not fill or not fill.get('filled'):
            result['signal'] = 'NEUTRAL'
            result['block_reason'] = (fill or {}).get('reason', 'Ордер не виконано')
            result['account'] = self.account.report()
            return result

        # Заходимо за ціною ВИКОНАННЯ, а не за ціною рішення
        decision['entry_price'] = fill['price']

        # 7. Записуємо позицію
        trade = self.keeper.open(decision, self.pair, verdict['timestamp'])
        result.update({
            'entry_price': fill['price'],
            'delay_sec': fill.get('delay_sec'),
            'slip_pct': fill.get('slip_pct'),
            'order_id': fill.get('order_id'),
            'trade_id': trade['id'] if trade else None,
            'account': self.account.report(),
        })
        return result
