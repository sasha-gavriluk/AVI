import pandas as pd
from utils.OtherUtils import _handle_error

#------------------------------
# Визначення макро-режиму ринку
#------------------------------

class MarketRegimeDetector:
    "Визначає макро-режим ринку (Тренд, Флет, Вибух) ансамблем незалежних радників"

    #------------------------------
    # Збір оцінок радників
    #------------------------------

    @_handle_error
    def get_votes(self, row: pd.Series) -> dict:
        "Збирає оцінки за кожен режим. Моделі вже відпрацювали — читаємо їхні колонки"
        # 1. Основний голос: FMR (нейромережа режиму) — незалежні ймовірності [0.0 - 1.0]
        probs = {
            'TREND': row.get('FMR_Trend', 0.0),
            'FLAT': row.get('FMR_Flat', 0.0),
            'EXPLOSION': row.get('FMR_Explosion', 0.0)
        }

        # 2. Бонус від SMC: щойно стався злам або продовження структури — це тренд.
        # УВАГА: на поточних даних BOS майже завжди 0, тож цей бонус спрацьовує рідко —
        # варто розібратись із детектором структури.
        if row.get('BOS', False) or row.get('CHoCH', False):
            probs['TREND'] += 0.3

        # TODO: голос NGram. Колонки NGram_Regime поки НЕ існує — коли з'явиться,
        # додати сюди бонус за збіг режиму (раніше тут був мертвий виклик row.get).

        return probs

#------------------------------
# Оцінка узгодженості радників
#------------------------------

class ConsensusEvaluator:
    "Оцінює узгодженість радників і вирішує, чи дозволена торгівля"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, min_confidence: float = 0.35):
        self.min_confidence = min_confidence

    #------------------------------
    # Рішення за оцінками
    #------------------------------

    @_handle_error
    def evaluate(self, probs: dict) -> dict:
        "Обирає режим і дію, зберігаючи неперервну впевненість (частка переможця)"
        total = sum(probs.values())
        if total == 0:
            return {'state': 'HOLDING', 'action': 'BLOCK_TRADING', 'confidence': 0.0}

        # Нормалізуємо оцінки у частки 0.0 - 1.0
        normalized = {k: v / total for k, v in probs.items()}

        max_state = max(normalized, key=normalized.get)
        confidence = normalized[max_state]

        # Замало узгодженості — краще почекати
        if confidence < self.min_confidence:
            return {'state': max_state, 'action': 'BLOCK_TRADING', 'confidence': confidence}

        return {'state': max_state, 'action': 'ALLOW_TRADING', 'confidence': confidence}

#------------------------------
# Узгодженість зі старшим ТФ
#------------------------------

class HTFAligner:
    "Перевіряє узгодженість поточного таймфрейму зі старшим (HTF)"

    #------------------------------
    # Перевірка вирівнювання
    #------------------------------

    @_handle_error
    def check_alignment(self, current_state: str, current_dir: str) -> str:
        "Повертає статус узгодженості. Заглушка — потребує мульти-ТФ даних"
        return 'ALIGNED'
