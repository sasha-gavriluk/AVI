import os
import json
import re
import pandas as pd

class GapAnalyzer:
    """
    Розумний аналізатор прогалин з урахуванням
    форекс-сесій, вихідних та свят.
    """

    # Пари, що торгуються ЛИШЕ у будні
    FOREX_ASSETS_PATTERN = re.compile(
        r'(EUR|GBP|USD|JPY|CHF|CAD|AUD|NZD|XAU|XAG|SPX|NAS|US30|GER|UK)'
    )

    def __init__(self):
        self.holidays = {}
        self._load_holidays()

    def _load_holidays(self):
        from utils.PathManager import PathManager
        config_path = PathManager.get_holidays_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.holidays = json.load(f)
            except Exception as e:
                print(f"Помилка завантаження календаря свят: {e}")

    def is_expected_gap(self, gap_start_ms: int, gap_end_ms: int,
                        asset_name: str, timeframe_ms: int, market_type: str = "Forex") -> bool:
        """
        Повертає True якщо прогалина є 'очікуваною' (вихідний/свято)
        і НЕ потребує завантаження.
        """
        if market_type == "Crypto":
            return False
            
        start = pd.Timestamp(gap_start_ms, unit='ms', tz='UTC')
        end = pd.Timestamp(gap_end_ms, unit='ms', tz='UTC')

        # 1. Якщо це форекс-актив і прогалина перекриває вихідні
        if market_type == "Forex" or self._is_forex_asset(asset_name):
            if self._gap_covers_weekend(start, end):
                return True
            if self._gap_covers_holiday(start, end):
                return True

        return False

    def _is_forex_asset(self, name: str) -> bool:
        return bool(self.FOREX_ASSETS_PATTERN.search(name.upper()))

    def _gap_covers_weekend(self, start: pd.Timestamp, end: pd.Timestamp) -> bool:
        """Перевіряє чи прогалина є суботою/неділею форекс-ринку.
        Форекс закривається в п'ятницю ~22:00 UTC, відкривається в понеділок ~22:00 UTC.
        """
        FOREX_CLOSE_HOUR = 22  # UTC
        current = start
        while current < end:
            # Якщо це п'ятниця після 22:00 UTC до понеділка 22:00 UTC — очікувана прогалина
            if current.weekday() == 4 and current.hour >= FOREX_CLOSE_HOUR:
                return True
            if current.weekday() in (5, 6):  # Субота, Неділя
                return True
            current += pd.Timedelta(hours=1)
        return False

    def _gap_covers_holiday(self, start: pd.Timestamp, end: pd.Timestamp) -> bool:
        """Перевіряє по збереженому календарю свят."""
        current = start
        while current < end:
            date_str = current.strftime('%Y-%m-%d')
            for source, dates in self.holidays.items():
                if date_str in dates:
                    return True
            current += pd.Timedelta(hours=24)
        return False

    def filter_real_gaps(self, gaps: list, asset_name: str,
                         timeframe_ms: int, market_type: str = "Forex") -> list:
        """Повертає тільки реальні прогалини (не вихідні і не свята)."""
        return [
            g for g in gaps
            if not self.is_expected_gap(
                g['gap_start'], g['gap_end'], asset_name, timeframe_ms, market_type
            )
        ]
