import os
import json
import datetime

import numpy as np
import pandas as pd

from utils.OtherUtils import _handle_error

#==============================
# Збірка готового сету фічей
#==============================
#
# Перетворює сирі свічки на повний набір фічей, який чекає ChronoSeer.
# Порядок дій той самий, що й у лабораторії при збиранні датасету — інакше
# мережа отримає не те, на чому вчилась:
#
#   для кожного таймфрейму: індикатори -> FMR -> FRS -> FFB -> префікс
#   склейка старших ТФ назад у часі (merge_asof, без заглядання в майбутнє)
#   фінансовий контекст (ATR, відстані до рівнів)
#   викидання 11 колонок без власної інформації
#
# НОРМАЛІЗАЦІЯ ТУТ НЕ РОБИТЬСЯ. Сет зберігається в базу сирим, а ділиться на
# дільники вже перед самою мережею — так одні й ті самі дані можна віддати
# і мережі, і людині, і бектесту.
#
# ЩО ВАРТО ЗНАТИ ПРО СТАБІЛЬНІСТЬ. Більшість фічей рахуються ковзними вікнами
# назад і не залежать від того, коли їх порахували. Але значущі рівні
# (Nearest_*_Price) будуються з УСІЄЇ переданої історії. Якщо порахувати їх
# на тисячі свічок сьогодні й на двох тисячах завтра — числа для тієї самої
# свічки вийдуть різні. Тому глибина історії задається сталою і не має гуляти.
#==============================


class FeatureSetBuilder:
    "Готує повний набір фічей для однієї монети з сирих свічок"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    BASE_TF = '15m'
    TIMEFRAMES = ['15m', '1h', '4h']

    # Тривалість свічки в секундах. Старший таймфрейм стає доступним лише ПІСЛЯ
    # свого закриття — див. _process_timeframe. Мусить збігатись із однойменною
    # сталою в AI_Lab/Futures/Transformer/dataset.py, інакше живий шлях і датасет
    # навчання розійдуться.
    TF_SECONDS = {'15m': 900, '1h': 3600, '4h': 14400}

    # Скільки сирих свічок брати для перерахунку. FMR має власне вікно на 1000,
    # тож щоб отримати фічі бодай для однієї свічки, стільки ж потрібно позаду.
    DEPTH = 2500

    LEVERAGE = 10
    RISK_REWARD = 2.0

    # Колонки без власної інформації. Доведено замірами 30.08.2026:
    # дві сталі, три копії ATR_14, по три ціни з 1h та 4h (кореляція > 0.999).
    DROP_COLS = [
        'Context_Liq_Dist_Long', 'Context_Liq_Dist_Short',
        'Context_ATR_Pct', 'Context_Suggested_SL_Pct', 'Context_Suggested_TP_Pct',
        '1h_open', '1h_high', '1h_low',
        '4h_open', '4h_high', '4h_low',
        # Рівні: викинуті 01.09.2026 через підглядання в майбутнє. Значущі рівні
        # збираються з усієї історії й застосовуються до кожного рядка — у живій
        # торгівлі це неможливо відтворити. Докладно в журналі змін dataset.py.
        '15m_Near_Resistance', '15m_Near_Support',
        '1h_Near_Resistance', '1h_Near_Support',
        '4h_Near_Resistance', '4h_Near_Support',
    ]

    BASE_COLS = ['open', 'high', 'low', 'close', 'volume', 'timestamp']

    # Підпис набору. Дописується в КІНЕЦЬ сету й лежить у базі разом із фічами.
    #
    # ЧОМУ ЦЕ ТУТ, А НЕ В DatasetPatcher. Раніше підпис ставив тільки патчер,
    # і таблиці <ПАРА>_set виходили на дві колонки ширшими за те, що збирає
    # цей клас. insert_data_from_pandas_append кладе рядок ПОЗИЦІЙНО, тож жива
    # торгівля отримувала «table has 204 columns but 202 values», помилку
    # ковтав _handle_error — і сет у базі мовчки лишався вчорашнім.
    # Тепер схему задає той, хто збирає дані, і розійтись більше нема з чим.
    STAMP_COLS = ['feature_set_version', 'built_at']

    # Мережі фічей вантажимо ОДИН раз на весь клас
    _fmr = None
    _frs = None
    _ffb = None

    #------------------------------
    # Підпис версії набору
    #------------------------------

    @staticmethod
    def version() -> str:
        """
        Скільки фічей чекає модель — це й є підпис набору.

        Ми вже маємо досвід, коли набір змінився зі 108 фічей на 97, а потім
        на 91. Без підпису старий сет виглядає цілком робочим і тихо годує
        мережу не тим.
        """
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), 'models', 'CS', 'inputs.json')
        try:
            with open(path, encoding='utf-8') as f:
                return f"features-{len(json.load(f)['meta_features'])}"
        except Exception:
            return 'features-unknown'

    @classmethod
    def _add_stamp(cls, df: pd.DataFrame) -> pd.DataFrame:
        "Дописує підпис набору. Обидві колонки одним рухом, без фрагментації"
        stamp = pd.DataFrame({
            'feature_set_version': cls.version(),
            'built_at': datetime.datetime.now().isoformat(timespec='seconds'),
        }, index=df.index)
        return pd.concat([df, stamp], axis=1)

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self):
        if FeatureSetBuilder._fmr is None:
            from models.FMR.FMR import FMR
            from models.FRS.FRS import FRS
            from models.FFB.FFB import FFB
            FeatureSetBuilder._fmr = FMR()
            FeatureSetBuilder._frs = FRS()
            FeatureSetBuilder._ffb = FFB()

        self.fmr = FeatureSetBuilder._fmr
        self.frs = FeatureSetBuilder._frs
        self.ffb = FeatureSetBuilder._ffb

    #------------------------------
    # ATR у цінах
    #------------------------------

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        "Середній розмах свічки. Та сама формула, що в лабораторії"
        high, low, close = df['high'], df['low'], df['close']
        prev = close.shift(1)
        tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    #------------------------------
    # Один таймфрейм
    #------------------------------

    @_handle_error
    def _process_timeframe(self, df: pd.DataFrame, tf: str) -> tuple:
        """
        Проганяє свічки через індикатори й мережі фічей, чіпляє префікс таймфрейму.

        :return: (датафрейм, список доданих мета-колонок)
        """
        from utils.algorithms.indicators.DataProcessingManager import DataProcessingManager

        d = DataProcessingManager(data=df.copy()).process_all()
        d = self.fmr.process(d)
        d = self.frs.process(d)
        d = self.ffb.process(d)
        if d is None:
            return None, []

        # Мережа не їсть True/False
        for col in d.columns:
            if d[col].dtype == 'bool':
                d[col] = d[col].astype(float)

        numeric = d.select_dtypes(include=[np.number]).columns.tolist()
        meta = [c for c in numeric if c not in self.BASE_COLS and 'price' not in c.lower()]

        renames = {c: f"{tf}_{c}" for c in meta}
        if tf != self.BASE_TF:
            for b in ['open', 'high', 'low', 'close', 'volume']:
                renames[b] = f"{tf}_{b}"

        d = d.rename(columns=renames)
        new_meta = list(renames.values())

        d[new_meta] = d[new_meta].ffill().fillna(0.0)
        d = d.dropna(subset=['timestamp'])
        d['timestamp'] = d['timestamp'].astype('int64')

        # ЧАС ЗАКРИТТЯ, а не відкриття — для СТАРШИХ таймфреймів.
        # У базі timestamp — це час ВІДКРИТТЯ, тож без цього зсуву 15-хвилинка
        # о 12:15 діставала 4h-свічку, помічену 12:00, разом з усім, що станеться
        # до 16:00. У датасеті навчання це було підгляданням у майбутнє; тут, у
        # живому шляху, майбутнього нема — біржа віддала б НЕДОформовану свічку,
        # тобто не те, на чому мережа вчилась. Обидві біди лікує один зсув.
        if tf != self.BASE_TF:
            step = self.TF_SECONDS[tf]
            ms = 1000 if d['timestamp'].max() > 1_000_000_000_000 else 1
            d['timestamp'] = d['timestamp'] + step * ms

        keep = ['timestamp'] + new_meta
        if tf == self.BASE_TF:
            keep = self.BASE_COLS + new_meta
            # Ціни рівнів потрібні окремо — з них рахуються сирі відстані
            for src, dst in (('FRS_res_price', '15m_FRS_res_price'),
                             ('FRS_sup_price', '15m_FRS_sup_price')):
                if src in d.columns:
                    d = d.rename(columns={src: dst})
                    keep.append(dst)

        return d[[c for c in keep if c in d.columns]], new_meta

    #------------------------------
    # Фінансовий контекст
    #------------------------------

    @_handle_error
    def _add_context(self, df: pd.DataFrame) -> tuple:
        """
        Додає ATR у відсотках і сирі відстані до рівнів.

        ATR_14 лишається НЕнормалізованим: за ним рахується стоп, і йому
        потрібне справжнє число, а не зсунуте.
        """
        atr_frac = self._atr(df) / df['close']
        sl_pct = atr_frac * 1.5

        if '15m_FRS_res_price' in df.columns and '15m_FRS_sup_price' in df.columns:
            res_dist = ((df['15m_FRS_res_price'] - df['close']) / df['close']).fillna(0.05)
            sup_dist = ((df['close'] - df['15m_FRS_sup_price']) / df['close']).fillna(0.05)
        else:
            res_dist = 0.05
            sup_dist = 0.05

        new_cols = {
            'ATR_14': (atr_frac * 100).bfill().fillna(0.0),
            'Context_ATR_Pct': atr_frac,
            'Context_Liq_Dist_Long': 1.0 / self.LEVERAGE,
            'Context_Liq_Dist_Short': 1.0 / self.LEVERAGE,
            'Context_Suggested_SL_Pct': sl_pct,
            'Context_Suggested_TP_Pct': sl_pct * self.RISK_REWARD,
            'Raw_Res_Dist_Pct': res_dist,
            'Raw_Sup_Dist_Pct': sup_dist,
        }
        df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)

        context_cols = ['Context_ATR_Pct', 'Context_Liq_Dist_Long', 'Context_Liq_Dist_Short',
                        'Context_Suggested_SL_Pct', 'Context_Suggested_TP_Pct']
        df[context_cols] = df[context_cols].ffill().fillna(0.0)
        return df, context_cols

    #------------------------------
    # Головний метод: зібрати сет
    #------------------------------

    @_handle_error
    def build(self, candles: dict) -> pd.DataFrame:
        """
        Збирає повний сет фічей із сирих свічок трьох таймфреймів.

        :param candles: {'15m': df, '1h': df, '4h': df} — сирі OHLCV
        :return: датафрейм із усіма фічами й підписом набору, НЕ нормалізований
        """
        merged, meta = self._process_timeframe(candles[self.BASE_TF], self.BASE_TF)
        if merged is None:
            return None

        all_meta = list(meta)

        # Старші таймфрейми чіпляються НАЗАД у часі: беремо останнє відоме
        # значення. Так свічка не бачить 4-годинку, яка ще не закрилась.
        for tf in self.TIMEFRAMES:
            if tf == self.BASE_TF or tf not in candles:
                continue
            d, m = self._process_timeframe(candles[tf], tf)
            if d is None:
                continue
            merged = pd.merge_asof(merged, d, on='timestamp', direction='backward')
            all_meta.extend(m)

        merged[all_meta] = merged[all_meta].ffill().fillna(0.0)
        merged = merged.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)

        merged, context_cols = self._add_context(merged)
        all_meta.extend(context_cols)
        all_meta.extend(['ATR_14', 'Raw_Res_Dist_Pct', 'Raw_Sup_Dist_Pct'])

        # Службові ціни рівнів далі не потрібні
        for col in ['15m_FRS_res_price', '15m_FRS_sup_price']:
            if col in merged.columns:
                merged = merged.drop(columns=[col])

        drop = [c for c in self.DROP_COLS if c in merged.columns]
        if drop:
            merged = merged.drop(columns=drop)

        return self._add_stamp(merged.reset_index(drop=True))
