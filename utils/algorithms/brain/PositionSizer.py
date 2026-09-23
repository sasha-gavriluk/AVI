from utils.OtherUtils import _handle_error

#------------------------------
# Розрахунок розміру позиції
#------------------------------

class PositionSizer:
    "Рахує розмір ф'ючерсної позиції та перевіряє, що стоп не за ціною ліквідації"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self):
        pass

    #------------------------------
    # Ціна ліквідації
    #------------------------------

    @staticmethod
    def _liquidation_price(entry_price: float, leverage: int, side: str) -> float:
        """
        Де біржа примусово закриє позицію. При плечі 10 це 10% руху проти нас,
        при 20 — 5%. Підтримувальну маржу не враховуємо: вона зсуває межу трохи
        ближче, тож наша оцінка ОБЕРЕЖНІША за реальну, і це правильний бік помилки.

        Раніше рахувалось у FinancialAdvisor. Перенесено сюди 01.09.2026, бо той
        модуль пішов на ремонт.
        """
        is_long = (side == 'buy')
        distance = 1.0 / max(leverage, 1)
        return entry_price * (1 - distance) if is_long else entry_price * (1 + distance)

    #------------------------------
    # Розмір і перевірка ліквідації
    #------------------------------

    @_handle_error
    def calculate(self, account_state: dict, entry_price: float, stop_price: float,
                  direction: str, size_multiplier: float = 1.0) -> dict:
        "Повертає розмір позиції, маржу, ціну ліквідації та прапорець валідності"
        capital = account_state.get('total_capital', 0.0)
        risk_pct = account_state.get('risk_per_trade_pct', 1.0) * size_multiplier
        leverage = account_state.get('leverage', 10)

        if capital <= 0 or entry_price <= 0 or entry_price == stop_price:
            return {'valid': False, 'reason': 'Некоректні вхідні дані для сайзингу'}

        side = 'buy' if direction == 'BUY' else 'sell'

        # РОЗМІР РАХУЄМО ЧЕРЕЗ ЗАСТАВУ, а не через ризик на стопі.
        #
        # FinancialAdvisor.calculate_futures_position_size розуміє risk_per_trade_pct
        # як «скільки відсотків капіталу втратити на стопі». При частці 10% і стопі
        # 0.85% це дало б позицію на $1764 при балансі $150 — тобто заставу $176,
        # більшу за весь рахунок.
        #
        # Усі виміряні результати (бойові тести 30-31.08) отримані іншим правилом:
        # застава = частка балансу, обсяг = застава × плече. Живемо за ним, інакше
        # жива торгівля робитиме не те, що перевірялось.
        #
        # ФІКСОВАНА ЗАСТАВА ГОЛОВНІША ЗА ВІДСОТОК. Якщо стан рахунку приніс
        # margin_usd — беремо саме його. Так домовлено 02.09.2026: 10% рахуються
        # один раз при старті й далі не міняються, тобто без складного відсотка.
        # Відсоток лишається для паперових прогонів, де фіксованої суми немає.
        fixed_margin = account_state.get('margin_usd')
        margin = float(fixed_margin) * size_multiplier if fixed_margin else capital * risk_pct / 100.0
        margin = min(margin, capital)
        notional = margin * leverage
        position = {
            'position_size_usd': round(notional, 2),
            'position_size_units': round(notional / entry_price, 8),
            'margin_required_usd': round(margin, 2),
            'risk_per_trade_usd': round(notional * abs(entry_price - stop_price) / entry_price, 2),
            'leverage': leverage,
        }
        if margin <= 0:
            return {'valid': False, 'reason': 'Нульова застава'}

        liq_price = self._liquidation_price(entry_price, leverage, side)

        # Ключова перевірка для плеча: стоп МАЄ спрацювати раніше за ліквідацію
        if liq_price:
            is_safe = (side == 'buy' and stop_price > liq_price) or \
                      (side == 'sell' and stop_price < liq_price)
            if not is_safe:
                return {'valid': False, 'reason': f'Стоп ({stop_price}) за ціною ліквідації ({liq_price})'}

        return {
            'valid': True,
            'liquidation_price': liq_price,
            **position
        }
