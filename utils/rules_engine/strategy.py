# ==================================================================
# ВІДКЛЮЧЕНО (RULES_ENGINE): робота з класичними стратегіями (rules_engine)
# тимчасово заморожена — рушій НІДЕ більше не використовується (заморожені
# також StrategyGenerator.py, MarketRunner.py, і виклики в TradingCopilot.py/
# copilot_service.py/CopilotLogic.py). Весь код нижче загорнутий у рядковий
# літерал і не виконується. Довідка: Code/COPILOT_ARCHITECTURE.md, Code/REFACTOR_LOG.md.
# ==================================================================

_DISABLED_RULES_ENGINE_STRATEGY_SOURCE = r'''
import pandas as pd

class Strategy:
    """
    Клас для управління повним життєвим циклом угоди (Entry та Exit).
    Дозволяє комбінувати логічні правила (ООП-вирази) з часовими затримками.
    """
    def __init__(self, entry_rule, exit_rule=None, exit_after_candles=None, delay_entry_candles=0):
        self.entry_rule = entry_rule
        self.exit_rule = exit_rule
        self.exit_after_candles = exit_after_candles
        self.delay_entry_candles = delay_entry_candles

    def execute(self, registry):
        """
        Виконує стратегію на історичних даних і повертає DataFrame з сигналами входу та виходу.
        """
        # 1. Обчислюємо базові сигнали на вхід
        entry_signals = self.entry_rule.evaluate(registry)
        if not isinstance(entry_signals, pd.Series):
            entry_signals = pd.Series(entry_signals, index=registry.data.index)
            
        # Обчислюємо PRE-SIGNALS (Fuzzy Logic Proximity)
        try:
            entry_proximity = self.entry_rule.evaluate_proximity(registry)
            if not isinstance(entry_proximity, pd.Series):
                entry_proximity = pd.Series(entry_proximity, index=registry.data.index)
        except Exception:
            entry_proximity = entry_signals.astype(float)

        # 2. Відкладений вхід (wait_n_candles_after_signal)
        if self.delay_entry_candles > 0:
            entry_signals = entry_signals.shift(self.delay_entry_candles).fillna(False)
            entry_proximity = entry_proximity.shift(self.delay_entry_candles).fillna(0.0)

        # 3. Обчислюємо сигнали на вихід
        exit_signals = pd.Series(False, index=entry_signals.index)
        
        if self.exit_rule is not None:
            raw_exits = self.exit_rule.evaluate(registry)
            if not isinstance(raw_exits, pd.Series):
                raw_exits = pd.Series(raw_exits, index=entry_signals.index)
            exit_signals = raw_exits
            
        # 4. Закриття по кількості свічок (exit_after_n_candles)
        if self.exit_after_candles is not None and self.exit_after_candles > 0:
            timer_exits = entry_signals.shift(self.exit_after_candles).fillna(False)
            exit_signals = exit_signals | timer_exits
            
        return pd.DataFrame({
            'entry': entry_signals,
            'entry_proximity': entry_proximity,
            'exit': exit_signals
        })

'''
