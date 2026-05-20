import pandas as pd

class Strategy:
    """
    Клас для управління повним життєвим циклом угоди (Entry та Exit).
    Дозволяє комбінувати логічні правила (ООП-вирази) з часовими затримками.
    """
    def __init__(self, entry_rule, exit_rule=None, exit_after_candles=None, delay_entry_candles=0):
        """
        :param entry_rule: Логічне правило для входу (напр. Pattern('Hammer') & Indicator('RSI_14') < 30)
        :param exit_rule: Логічне правило для виходу (напр. Indicator('RSI_14') > 70)
        :param exit_after_candles: Якщо вказано, позиція автоматично закриється через N свічок після входу.
        :param delay_entry_candles: Якщо вказано, фактичний вхід відбудеться через N свічок після сигналу.
        """
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
        
        # Переконуємось, що отримали Pandas Series (булеву маску)
        if not isinstance(entry_signals, pd.Series):
            # Якщо правило повернуло просто одне значення (напр. True), розтягуємо його на весь датафрейм
            entry_signals = pd.Series(entry_signals, index=registry.data.index)

        # 2. Відкладений вхід (wait_n_candles_after_signal)
        if self.delay_entry_candles > 0:
            entry_signals = entry_signals.shift(self.delay_entry_candles).fillna(False)

        # 3. Обчислюємо сигнали на вихід
        exit_signals = pd.Series(False, index=entry_signals.index)
        
        if self.exit_rule is not None:
            raw_exits = self.exit_rule.evaluate(registry)
            if not isinstance(raw_exits, pd.Series):
                raw_exits = pd.Series(raw_exits, index=entry_signals.index)
            exit_signals = raw_exits
            
        # 4. Закриття по кількості свічок (exit_after_n_candles)
        if self.exit_after_candles is not None and self.exit_after_candles > 0:
            # Зсуваємо сигнали на вхід на N свічок вперед
            # Це означає, що якщо ми увійшли на свічці X, таймерний вихід спрацює на X + N
            timer_exits = entry_signals.shift(self.exit_after_candles).fillna(False)
            
            # Об'єднуємо обидві умови виходу (або по логіці, або по таймеру)
            exit_signals = exit_signals | timer_exits
            
        return pd.DataFrame({
            'entry': entry_signals,
            'exit': exit_signals
        })
