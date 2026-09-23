import pandas as pd

from utils.DataBaseManager import DataBaseManager
from utils.OtherUtils import _handle_error
from utils.algorithms.FeatureSetBuilder import FeatureSetBuilder
from models.CS.ChronoSeer import ChronoSeer

#==============================
# Служба ChronoSeer
#==============================
#
# Єдина точка роботи з мережею. Порядок дій:
#
#   1. приймає свічки й назву монети
#   2. збирає повний сет фічей і КЛАДЕ ЙОГО В БАЗУ (сирим, без нормалізації)
#   3. бере з бази останнє вікно й віддає мережі
#   4. повертає вердикт далі — у шар ризику
#
# НАВІЩО ЗБЕРІГАТИ В БАЗУ. Фічі коштують часу: повне вікно на 1000 свічок
# рахується близько 2.8 секунди, і більшість цієї роботи — перерахунок того,
# що вже рахувалось учора. Порахувавши один раз і склавши в базу, на кожній
# новій свічці лишається дорахувати тільки хвіст.
#
# Сет у базі лежить СИРИМ. Нормалізація робиться в останню мить перед мережею,
# бо дільники прив'язані до дати навчання й можуть змінитись при перенавчанні,
# а самі фічі — ні.
#==============================


class ChronoSeerService:
    "Збирає сет, зберігає його в базу, питає мережу й віддає вердикт"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    SET_SUFFIX = '_set'            # SOLUSDT -> SOLUSDT_set
    WINDOW = 1000                  # скільки свічок бачить мережа
    WARMUP = 1500                  # додатковий розгін для індикаторів і мереж фічей

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, db: DataBaseManager = None):
        """
        :param db: менеджер бази. None — створити свій
        """
        self.db = db or DataBaseManager()
        self.builder = FeatureSetBuilder()
        self.seer = ChronoSeer()

    #------------------------------
    # Імена таблиць
    #------------------------------

    def _set_table(self, pair: str) -> str:
        "Ім'я таблиці з готовим сетом для цієї монети"
        return f"{pair}{self.SET_SUFFIX}"

    def _candle_table(self, pair: str, tf: str) -> str:
        "Ім'я таблиці із сирими свічками"
        return f"{pair}_{tf}"

    #------------------------------
    # Крок 1: зібрати сирі свічки
    #------------------------------

    @_handle_error
    def _collect_candles(self, pair: str, df_15m: pd.DataFrame = None) -> dict:
        """
        Складає сирі свічки трьох таймфреймів.

        :param df_15m: якщо передані — беремо їх, інакше читаємо з бази
        """
        depth = self.builder.DEPTH
        candles = {}

        if df_15m is not None:
            candles['15m'] = df_15m.sort_values('timestamp').reset_index(drop=True)
        else:
            candles['15m'] = self.db.get_data_by_number_range(
                self._candle_table(pair, '15m'), depth)

        for tf in ('1h', '4h'):
            d = self.db.get_data_by_number_range(self._candle_table(pair, tf), depth)
            if d is not None and not d.empty:
                candles[tf] = d.sort_values('timestamp').reset_index(drop=True)

        return candles

    #------------------------------
    # Крок 2: зібрати сет і записати в базу
    #------------------------------

    @_handle_error
    def update_set(self, pair: str, df_15m: pd.DataFrame = None) -> pd.DataFrame:
        """
        Рахує фічі й дописує їх у таблицю сету.

        :return: зібраний сет (те, що щойно пораховано)
        """
        candles = self._collect_candles(pair, df_15m)
        if '15m' not in candles or candles['15m'] is None or candles['15m'].empty:
            raise ValueError(f"Немає свічок для {pair}")

        feature_set = self.builder.build(candles)
        if feature_set is None or feature_set.empty:
            raise ValueError(f"Не вдалось зібрати сет для {pair}")

        # insert_data_from_pandas_auto сам вирішує, створити таблицю чи дописати,
        # і не дублює рядки за timestamp
        self.db.insert_data_from_pandas_auto(self._set_table(pair), feature_set)
        return feature_set

    #------------------------------
    # Крок 3: взяти вікно з бази
    #------------------------------

    @_handle_error
    def _window_from_db(self, pair: str) -> pd.DataFrame:
        "Останні WINDOW рядків готового сету"
        d = self.db.get_data_by_number_range(self._set_table(pair), self.WINDOW)
        if d is None or d.empty:
            return None
        return d.sort_values('timestamp').reset_index(drop=True)

    #------------------------------
    # Крок 4: головний метод
    #------------------------------

    @_handle_error
    def process(self, pair: str, df_15m: pd.DataFrame = None,
                refresh: bool = True) -> dict:
        """
        Повний ланцюг: candles -> feature_set у базі -> мережа -> verdict.

        :param pair: 'SOLUSDT'
        :param df_15m: свіжі свічки. None — узяти з бази
        :param refresh: False — не перераховувати фічі, читати готове з бази
        :return: verdict мережі по кожному горизонту
        """
        if refresh:
            feature_set = self.update_set(pair, df_15m)
        else:
            feature_set = None

        window = self._window_from_db(pair)
        if window is None or len(window) < self.WINDOW:
            # База ще не наповнена — беремо щойно пораховане
            window = feature_set if feature_set is not None else self.update_set(pair, df_15m)

        if len(window) < self.WINDOW:
            raise ValueError(
                f"Замало рядків у сеті {pair}: {len(window)}, потрібно {self.WINDOW}"
            )

        verdict = self.seer.process(window, pair)
        verdict['pair'] = pair
        verdict['timestamp'] = int(window.iloc[-1]['timestamp'])
        return verdict
