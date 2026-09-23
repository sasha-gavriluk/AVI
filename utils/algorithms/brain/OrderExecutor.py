from .OrderGuard import OrderGuard
from utils.OtherUtils import _handle_error

#==============================
# Виконавець ордерів
#==============================
#
# Між «мережа сказала BUY» і «на біржі стоїть позиція» лежить проміжок, у якому
# ламається найбільше. Досі цього шару не було взагалі: PositionKeeper одразу
# записував угоду так, ніби вона виконалась миттєво й за тією самою ціною.
# У паперовому режимі це нешкідлива брехня, у живому — джерело розходження
# між тестом і рахунком.
#
# Тут це місце й закрите. Виконавець робить три речі:
#     1. питає OrderGuard, чи ордер ще актуальний;
#     2. бере ЦІНУ ВИКОНАННЯ, а не ціну рішення;
#     3. у живому режимі ставить ордер на біржі разом зі стопом і ціллю.
#
# ЧОМУ НАМІР СТВОРЮЄТЬСЯ НЕ ТУТ. Запізнення треба міряти від моменту, коли
# мережа дала вердикт, а не від моменту, коли ми зібрались надсилати ордер —
# інакше вимір завжди показуватиме нуль і сторож не спрацює ніколи.
# Тому намір заводить FCryptoLogic одразу після вердикту й приносить сюди.
#
# ЖИВИЙ РЕЖИМ ВИМКНЕНИЙ ЗА ЗАМОВЧУВАННЯМ і вмикається лише явно, разом із
# підключеною біржею. Паперовий режим проходить рівно той самий шлях і ті
# самі перевірки — різниця тільки в останньому кроці.
#==============================


class OrderExecutor:
    "Ставить ордер: у папері чи на біржі, але завжди через сторожа"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    # Тип ордера в живому режимі. Ринковий, бо сторож уже перевірив ціну:
    # лімітний тут означав би ще одне очікування без гарантії виконання.
    ORDER_TYPE = 'market'

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, exchange=None, live: bool = False, guard: OrderGuard = None):
        """
        :param exchange: CCXTModule або None. Без нього ціна береться з рішення
        :param live: True — ставити справжні ордери. Вимагає exchange
        :param guard: OrderGuard. None — створити свій зі сталими за замовчуванням
        """
        self.exchange = exchange
        self.guard = guard or OrderGuard()
        self.live = bool(live and exchange is not None)

    #------------------------------
    # Намір
    #------------------------------

    @_handle_error
    def begin(self, started: float = None) -> dict:
        """
        Пускає годинник. Викликається на САМОМУ ПОЧАТКУ такту — до того, як
        рахуються фічі й питається мережа, бо ці секунди теж запізнення.
        Ціни на цей момент ще немає, її приносить aim().

        :param started: мітка time.monotonic() закриття свічки. Живий цикл
                        передає її, щоб бюджет рахувався від свічки
        """
        return self.guard.intent(0.0, None, started=started)

    @_handle_error
    def aim(self, intent: dict, price: float, direction: str) -> dict:
        "Дописує в намір ціну рішення й бік, коли мережа вже відповіла"
        intent['decision_price'] = float(price)
        intent['direction'] = direction
        return intent

    #------------------------------
    # Ціна просто зараз
    #------------------------------

    @_handle_error
    def price_now(self, pair: str, fallback: float) -> float:
        """
        Поточна ціна з біржі. Якщо біржі немає або вона не відповіла —
        повертаємо ціну рішення, і тоді сторож перевірить лише час.
        """
        if self.exchange is None:
            return fallback
        ticker = self.exchange.fetch_ticker(pair)
        if not ticker:
            return fallback
        price = ticker.get('last') or ticker.get('close')
        return float(price) if price else fallback

    #------------------------------
    # Постановка ордера
    #------------------------------

    @_handle_error
    def place(self, intent: dict, decision: dict, pair: str) -> dict:
        """
        Останній крок перед позицією.

        :param intent: те, що повернув begin() у момент вердикту
        :param decision: рішення, яке пройшло шар ризику
        :return: {'filled': bool, 'price': ціна виконання, 'reason': str,
                  'order_id': ..., 'delay_sec': ..., 'slip_pct': ...}
        """
        entry = decision['entry_price']
        price = self.price_now(pair, entry)

        check = self.guard.check(intent, price)
        answer = {'delay_sec': check.get('delay_sec'), 'slip_pct': check.get('slip_pct'),
                  'price': price, 'order_id': None, 'live': self.live}

        if not check.get('allowed'):
            return {**answer, 'filled': False, 'reason': check.get('reason', 'Сторож скасував ордер')}

        if not self.live:
            return {**answer, 'filled': True, 'reason': 'Паперове виконання'}

        # Обсяг мусить лягти в крок біржі, інакше ордер відхилять
        amount = self.exchange.amount_to_precision(pair, decision['position_size_units'])
        if not amount:
            return {**answer, 'filled': False, 'reason': 'Обсяг менший за крок біржі'}

        # Плече ставиться ОКРЕМО, до цього виклику (ExchangeAccount.ensure_leverage):
        # там воно пробує 20, а якщо біржа не дала — 10. Тут його не передаємо,
        # щоб не смикати біржу вдруге вже без запасного варіанта
        order = self.exchange.create_order(
            symbol=pair,
            order_type=self.ORDER_TYPE,
            side='buy' if decision['direction'] == 'BUY' else 'sell',
            amount=amount,
            stop_loss=decision.get('stop_price'),
            take_profit=decision.get('target_price'),
        )
        if not order:
            return {**answer, 'filled': False, 'reason': 'Біржа не прийняла ордер'}

        # Біржа знає справжню ціну виконання краще за нас
        filled_price = order.get('average') or order.get('price') or price
        return {**answer, 'filled': True, 'reason': '', 'price': float(filled_price),
                'order_id': order.get('id')}
