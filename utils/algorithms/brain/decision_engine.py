import pandas as pd

from .block_a_context import MarketRegimeDetector, ConsensusEvaluator, HTFAligner
from .block_b_state import TrendPhaseDetector, FlatPhaseDetector, RiskMap
from .block_c_entry import EntryTriggerValidator, RewardRiskCalculator, InvalidationRules
from .block_d_risk import AccountGuard, CorrelationGuard, EventGuard, PositionSizer
from .block_e_management import PositionManager

#------------------------------
# Головний контролер рішень
#------------------------------

class DecisionEngine:
    "Пропускає кожну свічку через конвеєр фільтрів. Будь-яке вето зупиняє генерацію сигналу"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self):
        # Блок A — контекст
        self.regime_detector = MarketRegimeDetector()
        self.consensus = ConsensusEvaluator()
        self.htf_aligner = HTFAligner()
        # Блок B — уточнення стану
        self.trend_phase = TrendPhaseDetector()
        self.flat_phase = FlatPhaseDetector()
        self.risk_map = RiskMap()
        # Блок C — вхід
        self.entry_validator = EntryTriggerValidator()
        self.rr_calculator = RewardRiskCalculator()
        # Блок D — ризик
        self.account_guard = AccountGuard()
        self.correlation_guard = CorrelationGuard()
        self.event_guard = EventGuard()
        self.position_sizer = PositionSizer()
        # Блок E — управління відкритою позицією (викликає той, хто веде позиції)
        self.position_manager = PositionManager()

    #------------------------------
    # Стан рахунку за замовчуванням
    #------------------------------

    def _default_account_state(self) -> dict:
        "Базовий стан рахунку. Для реального вето його має вести викликач (бектест/бот)"
        return {
            'daily_loss_pct': 0.0,
            'active_positions': [],
            'total_capital': 1000.0,
            'risk_per_trade_pct': 1.0,
            'leverage': 10
        }

    #------------------------------
    # Прогін датафрейму (бектест)
    #------------------------------

    def process_dataframe(self, df: pd.DataFrame, account_state: dict = None) -> dict:
        "Проганяє весь датафрейм через конвеєр і повертає результати по кожному рядку"
        if account_state is None:
            account_state = self._default_account_state()

        n = len(df)
        signals = ['NEUTRAL'] * n
        confidences = [0.0] * n
        reasons = [''] * n
        market_states = ['UNKNOWN'] * n
        stops = [None] * n
        targets = [None] * n
        rrs = [None] * n
        liquidations = [None] * n

        for i in range(n):
            row = df.iloc[i]
            current_price = row.get('close', 0.0)

            #--- БЛОК D: мета-ризик до всього ---
            if not self.account_guard.can_trade(account_state):
                reasons[i] = "Вето: Ліміт збитків / ризик портфеля"
                continue

            if not self.event_guard.is_safe_to_trade(row.get('timestamp'), account_state.get('news_calendar')):
                reasons[i] = "Вето: Небезпечне вікно новин"
                continue

            #--- БЛОК A: контекст ---
            votes = self.regime_detector.get_votes(row)
            consensus_result = self.consensus.evaluate(votes)
            regime = consensus_result['state']
            market_states[i] = regime

            if consensus_result['action'] == 'BLOCK_TRADING':
                reasons[i] = "Вето: Конфлікт радників (Утримання)"
                continue

            #--- БЛОК B: уточнення стану ---
            phase = 'UNKNOWN'
            if regime == 'TREND':
                phase = self.trend_phase.get_phase(row)
                if phase == 'EXHAUSTION':
                    reasons[i] = "Вето: Виснаження тренду"
                    continue
            elif regime == 'FLAT':
                # Межі каналу беремо з Nearest_* — колонок FRS_*_price не існує
                phase = self.flat_phase.evaluate(
                    current_price,
                    row.get('Nearest_Resistance_Price'),
                    row.get('Nearest_Support_Price')
                )
                if phase in ['SQUEEZE', 'CHOPPY']:
                    reasons[i] = f"Вето: Неторговий флет ({phase})"
                    continue

            r_map = self.risk_map.build_map(row, current_price)

            #--- БЛОК C: вхід ---
            trigger, direction = self.entry_validator.check_trigger(row, current_price, regime, phase)
            if not trigger:
                reasons[i] = "Немає тригера для входу"
                continue

            rr_eval = self.rr_calculator.evaluate(current_price, trigger, r_map, direction, row)
            if not rr_eval['valid']:
                reasons[i] = rr_eval['reason']
                continue

            #--- БЛОК D: сайзинг і перевірка ліквідації ---
            size_mult = self.correlation_guard.adjust_size(
                row.get('asset', ''), direction, account_state.get('active_positions', [])
            )
            sizing = self.position_sizer.calculate(
                account_state, current_price, rr_eval['stop'], direction, size_mult
            )
            if not sizing['valid']:
                reasons[i] = f"Вето: {sizing['reason']}"
                continue

            # Пройшли всі фільтри — угода дозволена
            signals[i] = direction
            confidences[i] = consensus_result['confidence']
            stops[i] = rr_eval['stop']
            targets[i] = rr_eval['target']
            rrs[i] = rr_eval['rr']
            liquidations[i] = sizing.get('liquidation_price')
            reasons[i] = f"Вхід: {trigger}, RR: {rr_eval['rr']:.2f}, Phase: {phase}"

        return {
            'signal': signals,
            'confidence': confidences,
            'block_reason': reasons,
            'market_state': market_states,
            'stop': stops,
            'target': targets,
            'rr': rrs,
            'liquidation': liquidations
        }

    #------------------------------
    # Управління відкритою позицією (Блок E)
    #------------------------------

    def manage_position(self, active_trade: dict, row: pd.Series, current_regime: str) -> str:
        "Викликається на кожній свічці, поки позиція відкрита. Повертає команду управління"
        self.position_manager.monitor_regime(active_trade, current_regime)

        command = self.position_manager.monitor_thesis(active_trade, row)
        if command != "HOLD":
            return command

        return self.position_manager.check_breakeven(active_trade, row.get('close', 0.0))
