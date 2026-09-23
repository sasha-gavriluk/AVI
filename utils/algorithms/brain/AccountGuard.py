from utils.OtherUtils import _handle_error

#------------------------------
# Мета-захист рахунку
#------------------------------

class AccountGuard:
    "Захист від тільту та вигорання депозиту (денний ліміт + сукупний ризик портфеля)"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    # Скільки капіталу дозволено тримати під ризиком одночасно
    MAX_PORTFOLIO_RISK_PCT = 6.0

    def __init__(self, max_daily_loss_pct: float = 5.0):
        """
        :param max_daily_loss_pct: денний ліміт збитку у відсотках від капіталу
        """
        self.max_daily_loss_pct = max_daily_loss_pct

    #------------------------------
    # Дозвіл на торгівлю
    #------------------------------

    @_handle_error
    def can_trade(self, account_state: dict) -> bool:
        "Вирішує, чи дозволено відкривати нові угоди з огляду на стан рахунку"
        # 1. Денний ліміт збитків.
        #
        # Межу бере зі СТАНУ РАХУНКУ, якщо він її приніс. Раніше стан передавав
        # max_daily_loss_pct, а вартовий його не читав і завжди міряв власні
        # 5% — тобто справжня межа рахунку мовчки підмінялась чужою.
        limit = account_state.get('max_daily_loss_pct') or self.max_daily_loss_pct
        if account_state.get('daily_loss_pct', 0.0) >= limit:
            return False

        # 2. Сукупний ризик по вже відкритих позиціях.
        # Якщо портфель уже в зоні високого ризику — нових угод не беремо.
        # Скільки капіталу вже стоїть під ризиком у відкритих позиціях.
        # Раніше це рахував FinancialAdvisor, перенесено сюди 01.09.2026.
        capital = account_state.get('total_capital', 0.0)
        open_trades = account_state.get('active_positions', [])
        if capital > 0 and open_trades:
            at_risk = 0.0
            for p in open_trades:
                entry = p.get('entry_price') or 0.0
                stop = p.get('stop_price') or 0.0
                size = p.get('position_size') or 0.0
                if entry > 0 and stop > 0 and size > 0:
                    at_risk += size * abs(entry - stop) / entry
            if at_risk / capital * 100.0 >= self.MAX_PORTFOLIO_RISK_PCT:
                return False

        return True
