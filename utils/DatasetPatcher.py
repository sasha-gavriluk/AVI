import os
import time

from utils.DataBaseManager import DataBaseManager
from utils.OtherUtils import _handle_error
from utils.algorithms.FeatureSetBuilder import FeatureSetBuilder

#==============================
# Патч бази: сирі свічки -> готові сети
#==============================
#
# Окремий інструмент. У торгівлі НЕ бере участі, запускається руками.
#
# Що робить: для кожної крипто-пари збирає повний набір фічей (три таймфрейми,
# склейка, фінансовий контекст) і кладе ОКРЕМОЮ таблицею <ПАРА>_set.
# Сирі свічки не чіпає взагалі — вони єдине, чого не можна перерахувати.
#
# Сет лежить у базі НЕ нормалізованим. Дільники накладаються в останню мить
# перед мережею, бо вони прив'язані до дати навчання й міняються при
# перенавчанні, а самі фічі — ні.
#
# ПОЗНАЧКА ВЕРСІЇ. У кожній таблиці є колонка версії набору. Ми вже маємо
# досвід, коли набір змінився зі 108 фічей на 97, а потім на 91 — без позначки
# старий сет виглядав би цілком робочим і тихо годував мережу не тим.
#
# Запуск:
#     ../venv/bin/python -c "from utils.DatasetPatcher import DatasetPatcher; DatasetPatcher().run()"
#==============================


class DatasetPatcher:
    "Перебирає крипто-пари в базі й будує для кожної готовий сет фічей"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    SET_SUFFIX = '_set'
    BASE_TF = '15m'
    REQUIRED_TF = ['15m', '1h', '4h']

    # Скільки свічок брати за раз. Уся історія одразу з'їдає пам'ять,
    # а надто дрібними шматками фічі не встигають прогрітись.
    CHUNK = 20000

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, db: DataBaseManager = None, version: str = None):
        """
        :param version: підпис набору фічей. None — узяти з паспорта моделі
        """
        self.db = db or DataBaseManager()
        self.version = version or FeatureSetBuilder.version()

        self.builder = FeatureSetBuilder()

    #------------------------------
    # Які пари є в базі
    #------------------------------

    @_handle_error
    def find_pairs(self) -> list:
        """
        Крипто-пари, у яких є всі потрібні таймфрейми.
        Форекс не чіпаємо: мережі фічей навчені на крипті.
        """
        tables = set(self.db.get_all_tables() or [])
        pairs = sorted({t.replace(f'_{self.BASE_TF}', '')
                       for t in tables
                       if t.endswith(f'_{self.BASE_TF}') and 'USDT' in t})

        ready = []
        for pair in pairs:
            missing = [tf for tf in self.REQUIRED_TF if f'{pair}_{tf}' not in tables]
            if missing:
                print(f"  ⚠️ {pair}: немає таймфреймів {missing}, пропускаємо")
                continue
            ready.append(pair)
        return ready

    #------------------------------
    # Чи сет уже свіжий
    #------------------------------

    @_handle_error
    def is_fresh(self, pair: str) -> bool:
        """
        Сет вважається свіжим, якщо він є, зібраний ПОТОЧНОЮ версією набору
        і доходить до останньої сирої свічки.
        """
        table = f'{pair}{self.SET_SUFFIX}'
        if not self.db.table_exists(table):
            return False
        try:
            r = self.db._get_conn().cursor().execute(
                f'SELECT MAX(timestamp), MAX(feature_set_version) FROM "{table}"').fetchone()
            set_last, version = r[0], r[1]
            raw_last = self.db._get_conn().cursor().execute(
                f'SELECT MAX(timestamp) FROM "{pair}_{self.BASE_TF}"').fetchone()[0]
        except Exception:
            return False

        return version == self.version and set_last == raw_last

    #------------------------------
    # Одна пара
    #------------------------------

    @_handle_error
    def patch_pair(self, pair: str) -> int:
        """
        Збирає сет для однієї пари й кладе його в базу.

        :return: скільки рядків записано
        """
        candles = {}
        for tf in self.REQUIRED_TF:
            d = self.db.get_data_by_number_range(f'{pair}_{tf}', self.CHUNK)
            if d is None or d.empty:
                raise ValueError(f'{pair}: порожня таблиця {tf}')
            candles[tf] = d.sort_values('timestamp').reset_index(drop=True)

        feature_set = self.builder.build(candles)
        if feature_set is None or feature_set.empty:
            raise ValueError(f'{pair}: збірка нічого не повернула')

        # Підпис набору ставить сам FeatureSetBuilder — і тут, і в живій
        # торгівлі. Раніше він стояв тільки тут, через що сет із живого циклу
        # виходив на дві колонки вужчий і взагалі не записувався
        self.db.insert_data_from_pandas_auto(f'{pair}{self.SET_SUFFIX}', feature_set)
        return len(feature_set)

    #------------------------------
    # Головний метод
    #------------------------------

    @_handle_error
    def run(self, pairs: list = None, force: bool = False) -> dict:
        """
        Проходить по всіх парах.

        :param pairs: обмежити список. None — усі крипто-пари з бази
        :param force: True — рахувати навіть те, що вже свіже
        """
        t0 = time.time()
        pairs = pairs or self.find_pairs()

        print('=' * 70)
        print(f'ПАТЧ БАЗИ: {len(pairs)} пар | версія набору: {self.version}')
        print('Сирі свічки НЕ чіпаються, сети кладуться окремими таблицями')
        print('=' * 70, flush=True)

        summary = {'done': [], 'skipped': [], 'errors': {}}

        for i, pair in enumerate(pairs, 1):
            label = f'[{i}/{len(pairs)}] {pair}'
            if not force and self.is_fresh(pair):
                print(f'{label}: сет свіжий, пропускаємо', flush=True)
                summary['skipped'].append(pair)
                continue
            try:
                t = time.time()
                n = self.patch_pair(pair)
                print(f'{label}: {n} рядків за {time.time() - t:.0f} с', flush=True)
                summary['done'].append(pair)
            except Exception as e:
                # Одна пара не має валити весь прогін — решта збереться
                print(f'{label}: ПОМИЛКА — {e}', flush=True)
                summary['errors'][pair] = str(e)

        print('=' * 70)
        print(f'ГОТОВО за {(time.time() - t0) / 60:.1f} хв | '
              f'зібрано {len(summary["done"])}, '
              f'пропущено {len(summary["skipped"])}, '
              f'помилок {len(summary["errors"])}')
        return summary
