import pandas as pd
from models.FFB.FFB import FFB
from models.FRS.FRS import FRS
from models.FMR.FMR import FMR
from .brain.decision_engine import DecisionEngine

#------------------------------
# Точка входу крипто-логіки
#------------------------------

class FCryptoLogic:
    "Обгортка над конвеєром DecisionEngine (brain/): готує дані й віддає торгове рішення"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    # Крипто-моделі вантажимо ОДИН раз на весь клас (кеш)
    _fmr = None
    _ffb = None
    _frs = None

    def __init__(self, df: pd.DataFrame):
        "Моделі підвантажуються один раз (кеш класу), далі беруться з кешу"
        if FCryptoLogic._ffb is None:
            FCryptoLogic._fmr = FMR()
            FCryptoLogic._ffb = FFB()
            FCryptoLogic._frs = FRS()

        self.mr = FCryptoLogic._fmr
        self.fb = FCryptoLogic._ffb
        self.rs = FCryptoLogic._frs

        self.df_processed = df.copy()

        # Двигун прийняття рішень (блоки A-E)
        self.engine = DecisionEngine()

    #==============================
    # Вхідні дані (Data Enrichment)
    #==============================

    #------------------------------
    # Збагачення датасету
    #------------------------------

    def _enrich_data(self) -> pd.DataFrame:
        "Єдиний метод, який готує всі дані: індикатори, патерни, мережі, рівні"
        from utils.algorithms.indicators.DataProcessingManager import DataProcessingManager

        # Тех. аналіз, патерни та алгоритми
        dpm = DataProcessingManager(data=self.df_processed)
        self.df_processed = dpm.process_all()

        # Послідовно пропускаємо через усі мережі
        self.df_processed = self.mr.process(self.df_processed)
        self.df_processed = self.rs.process(self.df_processed)
        self.df_processed = self.fb.process(self.df_processed)

        return self.df_processed

    #==============================
    # Головний метод обробки (Main)
    #==============================

    #------------------------------
    # Отримання сигналу
    #------------------------------

    def process(self) -> dict:
        "Готує дані, проганяє через конвеєр і віддає рішення для останньої свічки"
        # 1. Готуємо всі дані (індикатори, НН, рівні)
        self.df_processed = self._enrich_data()

        # 2. Пропускаємо через конвеєр жорстких фільтрів (DecisionEngine)
        results = self.engine.process_dataframe(self.df_processed)

        # 3. Записуємо результати назад у датафрейм (потрібно бектесту)
        self.df_processed['Logic_Signal'] = results['signal']
        self.df_processed['Logic_Confidence'] = results['confidence']
        self.df_processed['Logic_BlockReason'] = results['block_reason']
        self.df_processed['Logic_MarketState'] = results['market_state']
        self.df_processed['Logic_Stop'] = results['stop']
        self.df_processed['Logic_Target'] = results['target']
        self.df_processed['Logic_RR'] = results['rr']
        self.df_processed['Logic_Liquidation'] = results['liquidation']

        # 4. Формуємо словник для останньої свічки (жива торгівля / GUI)
        last_idx = -1
        last_row = self.df_processed.iloc[last_idx]

        return {
            "signal": results['signal'][last_idx],
            "confidence": round(results['confidence'][last_idx], 3),
            "block_reason": results['block_reason'][last_idx],
            "market_state": results['market_state'][last_idx],

            # Параметри угоди від конвеєра (потрібні бектесту й ризик-менеджменту)
            "stop_price": results['stop'][last_idx],
            "take_profit_price": results['target'][last_idx],
            "risk_reward_ratio": results['rr'][last_idx],
            "liquidation_price": results['liquidation'][last_idx],

            # Рівні беремо з Nearest_* — колонок FRS_*_price не існує
            "support_price": last_row.get('Nearest_Support_Price'),
            "resistance_price": last_row.get('Nearest_Resistance_Price'),

            # Legacy-поля для сумісності зі старими інтерфейсами виводу
            "active_triggers": 1 if results['signal'][last_idx] != 'NEUTRAL' else 0,
            "counter_trend_penalty": 0.0,
            "confluence_families": [],
            "active_signals": []
        }
