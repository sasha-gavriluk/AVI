import pandas as pd

#------------------------------
# Фаза тренду
#------------------------------

class TrendPhaseDetector:
    "Визначає фазу тренду (Ранній, Зрілий, Виснаження)"

    #------------------------------
    # Оцінка фази
    #------------------------------

    def get_phase(self, row: pd.Series) -> str:
        "Оцінює фазу тренду за виснаженням (WCE) та структурою (BOS/CHoCH)"
        # 1. Виснаження від модуля WCE. Колонка саме WCE_TREND_EXHAUSTION_15_3 —
        # раніше читалась неіснуюча WCE_Exhausted, тож вето ніколи не спрацьовувало.
        if row.get('WCE_TREND_EXHAUSTION_15_3', 0.0):
            return 'EXHAUSTION'

        # 2. Структура SMC (колонки від BacktestAlgorithmProcessor)
        if row.get('CHoCH', False):
            return 'EARLY'    # Щойно стався злам структури
        elif row.get('BOS', False):
            return 'MATURE'   # Продовження тренду
        else:
            return 'MATURE'   # Тренд триває без нових зламів

#------------------------------
# Фаза флету
#------------------------------

class FlatPhaseDetector:
    "Визначає тип флету (торговий діапазон, стиснення, рваний рух)"

    #------------------------------
    # Оцінка ширини каналу
    #------------------------------

    def evaluate(self, current_price: float, res_price: float, sup_price: float) -> str:
        "Рахує ширину каналу у відсотках і вирішує, чи він торговий"
        if res_price is None or sup_price is None:
            return 'CHOPPY'
        if pd.isna(res_price) or pd.isna(sup_price) or sup_price <= 0:
            return 'CHOPPY'

        range_pct = (res_price - sup_price) / sup_price

        if range_pct >= 0.008:       # Діапазон > 0.8%
            return 'TRADEABLE_RANGE' # Дозволено торгувати від меж
        elif range_pct <= 0.003:     # Діапазон < 0.3%
            return 'SQUEEZE'         # Вузька консолідація, чекаємо пробій
        else:
            return 'CHOPPY'          # Невизначений / рваний рух

#------------------------------
# Карта найближчих рівнів
#------------------------------

class RiskMap:
    "Формує карту найближчих значущих рівнів (цілей)"

    #------------------------------
    # Побудова карти
    #------------------------------

    def build_map(self, row: pd.Series, current_price: float) -> dict:
        "Знаходить найближчі опір і підтримку, які слугуватимуть таргетами"
        nearest_res = row.get('Nearest_Resistance_Price', None)
        nearest_sup = row.get('Nearest_Support_Price', None)

        # Рівень валідний лише якщо він з правильного боку від ціни
        if nearest_res is None or pd.isna(nearest_res) or nearest_res <= current_price:
            nearest_res = None
        if nearest_sup is None or pd.isna(nearest_sup) or nearest_sup >= current_price:
            nearest_sup = None

        return {'target_res': nearest_res, 'target_sup': nearest_sup}
