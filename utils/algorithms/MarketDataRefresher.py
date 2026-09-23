import time
import threading
import concurrent.futures

from utils.OtherUtils import _handle_error

#==============================
# Завантажувач свічок
#==============================
#
# Качає свіжі свічки трьох таймфреймів для всіх активів і кладе їх у базу.
# Це єдине місце в живому циклі, де є сенс у потоках.
#
# ЧОМУ САМЕ ТУТ. Завантаження — це очікування відповіді біржі, і поки один
# потік чекає, інші працюють. А от збірка фічей потоками НЕ пришвидшується:
# заміряно 02.09.2026, три пари послідовно — 11.9 с, ті самі три пари в три
# потоки — 12.5 с. Рахунок у Python тримає GIL, тож потоки там лише додають
# метушні. Тому фічі й мережа рахуються в один потік, у водієві циклу.
#
# ТРИ ПОТОКИ, І ВОНИ ЖИВУТЬ ПОСТІЙНО. Пул створюється один раз на весь запуск
# і перевикористовує ті самі потоки на кожному такті — не створюємо їх щоразу
# заново. Пари розкидані між потоками по черзі: при десяти активах виходить
# по три-чотири на потік, як і домовлялись.
#
# ЧОМУ НЕ БІЛЬШЕ ПОТОКІВ. Біржа рахує запити за одиницю часу, а не за потоки.
# Три — це компроміс: удвічі швидше за один і ще далеко від межі Bybit.
# Побільшати можна однією сталою.
#==============================


class MarketDataRefresher:
    "Тримає постійні потоки й довантажує свічки всіх активів у базу"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    THREADS = 3

    # Таймфрейми, на яких навчена мережа. Менше не можна: без 1h і 4h
    # склейка старших ТФ дасть порожнечу, і фічі поїдуть
    TIMEFRAMES = ['15m', '1h', '4h']

    # Скільки свічок просити щоразу. Двохсот вистачає, щоб залатати діру
    # після кількох годин без зв'язку, і це один запит на таймфрейм
    BARS = 200

    # Пауза між запитами В МЕЖАХ одного потоку. Захист від ліміту біржі
    # додатково до власного лічильника ccxt
    REQUEST_PAUSE_SEC = 0.25

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, exchange=None, threads: int = None):
        """
        :param exchange: CCXTModule. None — нічого не качаємо, працюємо на базі
        :param threads: скільки потоків. None — узяти сталу
        """
        self.exchange = exchange
        self.threads = int(threads or self.THREADS)

        self._pool = None
        self._lock = threading.Lock()

        # Що сталося з кожним активом на останньому такті — для журналу
        self.last_errors = {}

    #------------------------------
    # Пул потоків
    #------------------------------

    def _get_pool(self) -> concurrent.futures.ThreadPoolExecutor:
        "Створює пул при першому зверненні й далі повертає той самий"
        with self._lock:
            if self._pool is None:
                self._pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.threads,
                    thread_name_prefix='candles')
            return self._pool

    @_handle_error
    def stop(self) -> None:
        "Закриває потоки. Викликається при зупинці торгівлі"
        with self._lock:
            if self._pool is not None:
                self._pool.shutdown(wait=False)
                self._pool = None

    #------------------------------
    # Частка одного потоку
    #------------------------------

    @_handle_error
    def _split(self, pairs: list) -> list:
        """
        Розкидає активи між потоками по черзі.

        По черзі, а не шматками поспіль: якщо один актив відповідає повільно,
        затримка розмазується по всіх потоках, а не вішає один із них.
        """
        buckets = [[] for _ in range(self.threads)]
        for i, pair in enumerate(pairs):
            buckets[i % self.threads].append(pair)
        return [b for b in buckets if b]

    #------------------------------
    # Робота одного потоку
    #------------------------------

    @_handle_error
    def _fetch_bucket(self, pairs: list) -> dict:
        """
        Качає всі таймфрейми для своєї частки активів.

        Запис у базу робить сам CCXTModule.fetch_ohlcv через декоратор
        _save_to_db, а DataBaseManager серіалізує звернення спільним замком —
        тому одне з'єднання DuckDB витримує кілька потоків.
        """
        done = {}
        for pair in pairs:
            for tf in self.TIMEFRAMES:
                result = self.exchange.fetch_ohlcv(pair, tf, limit=self.BARS)
                if result is None:
                    self.last_errors[pair] = f'біржа не віддала {tf}'
                time.sleep(self.REQUEST_PAUSE_SEC)
            done[pair] = pair not in self.last_errors
        return done

    #------------------------------
    # Головний метод: оновити всі активи
    #------------------------------

    @_handle_error
    def refresh_all(self, pairs: list, timeout: float = 90.0) -> dict:
        """
        Оновлює свічки всіх активів і чекає, доки всі потоки закінчать.

        :param timeout: скільки секунд чекати на всіх, перш ніж рушити далі
                        з тим, що встигло завантажитись
        :return: {'SOLUSDT': True/False} — у кого вийшло
        """
        self.last_errors = {}
        if self.exchange is None or not pairs:
            return {}

        pool = self._get_pool()
        futures = [pool.submit(self._fetch_bucket, bucket) for bucket in self._split(pairs)]

        report = {}
        for future in concurrent.futures.as_completed(futures, timeout=timeout):
            result = future.result()
            if result:
                report.update(result)
        return report
