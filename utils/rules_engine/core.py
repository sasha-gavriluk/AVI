import pandas as pd
import operator

class Expression:
    """Базовий клас для всіх логічних виразів у нашому ООП-будівельнику."""
    
    def evaluate(self, registry):
        """Цей метод має бути реалізований у дочірніх класах."""
        raise NotImplementedError("Метод evaluate() має бути перевизначений.")

    # Магічні методи для порівняння (перевантаження операторів)
    def __gt__(self, other):
        return BinaryOperation(self, operator.gt, ">", other)

    def __lt__(self, other):
        return BinaryOperation(self, operator.lt, "<", other)

    def __ge__(self, other):
        return BinaryOperation(self, operator.ge, ">=", other)

    def __le__(self, other):
        return BinaryOperation(self, operator.le, "<=", other)

    def __eq__(self, other):
        return BinaryOperation(self, operator.eq, "==", other)

    def __ne__(self, other):
        return BinaryOperation(self, operator.ne, "!=", other)

    # Магічні методи для логічних 'AND' та 'OR' (використовуємо & та |)
    def __and__(self, other):
        # В pandas 'and' це '&' (побітове і), тому перевантажуємо __and__
        return BinaryOperation(self, operator.and_, "&", other)

    def __or__(self, other):
        return BinaryOperation(self, operator.or_, "|", other)

    # Математичні оператори, якщо захочемо робити формули: Indicator("SMA") + 100
    def __add__(self, other):
        return BinaryOperation(self, operator.add, "+", other)

    def __sub__(self, other):
        return BinaryOperation(self, operator.sub, "-", other)

    def __mul__(self, other):
        return BinaryOperation(self, operator.mul, "*", other)

    def __truediv__(self, other):
        return BinaryOperation(self, operator.truediv, "/", other)

    # ----------------------------------
    # Спеціальні операції (Перетин)
    # ----------------------------------
    def crosses_over(self, other):
        return CrossOver(self, other)

    def crosses_under(self, other):
        return CrossUnder(self, other)


class CrossOver(Expression):
    """Визначає перетин лінією 1 лінії 2 ЗНИЗУ ВГОРУ."""
    def __init__(self, left, right):
        self.left = left if isinstance(left, Expression) else Constant(left)
        self.right = right if isinstance(right, Expression) else Constant(right)

    def evaluate(self, registry):
        l_val = self.left.evaluate(registry)
        r_val = self.right.evaluate(registry)
        
        # Для перетину нам потрібне попереднє значення (shift(1)). 
        # Якщо це константа, вона не змінюється.
        l_prev = l_val.shift(1) if isinstance(l_val, pd.Series) else l_val
        r_prev = r_val.shift(1) if isinstance(r_val, pd.Series) else r_val
        
        return (l_val > r_val) & (l_prev <= r_prev)

    def __repr__(self):
        return f"CrossOver({self.left}, {self.right})"


class CrossUnder(Expression):
    """Визначає перетин лінією 1 лінії 2 ЗВЕРХУ ВНИЗ."""
    def __init__(self, left, right):
        self.left = left if isinstance(left, Expression) else Constant(left)
        self.right = right if isinstance(right, Expression) else Constant(right)

    def evaluate(self, registry):
        l_val = self.left.evaluate(registry)
        r_val = self.right.evaluate(registry)
        
        l_prev = l_val.shift(1) if isinstance(l_val, pd.Series) else l_val
        r_prev = r_val.shift(1) if isinstance(r_val, pd.Series) else r_val
        
        return (l_val < r_val) & (l_prev >= r_prev)

    def __repr__(self):
        return f"CrossUnder({self.left}, {self.right})"


class Constant(Expression):
    """Представляє статичне число або рядок у нашому правилі."""
    def __init__(self, value):
        self.value = value

    def evaluate(self, registry):
        return self.value

    def __repr__(self):
        return str(self.value)


class Indicator(Expression):
    """Представляє динамічний індикатор або колонку з датафрейму."""
    def __init__(self, name: str):
        self.name = name

    def evaluate(self, registry):
        # Звертаємось до реєстру, щоб він повернув нам Pandas Series
        return registry.get_indicator(self.name)

    def __repr__(self):
        return f"Indicator('{self.name}')"


class Pattern(Expression):
    """Представляє свічковий патерн."""
    def __init__(self, name: str):
        self.name = name

    def evaluate(self, registry):
        # Реєстр автоматично знайде або згенерує потрібний патерн
        return registry.get_indicator(self.name)

    def __repr__(self):
        return f"Pattern('{self.name}')"


class Algorithm(Expression):
    """Представляє алгоритмічну фічу (напр. BOS, CHoCH, FVG)."""
    def __init__(self, name: str):
        self.name = name

    def evaluate(self, registry):
        return registry.get_indicator(self.name)

    def __repr__(self):
        return f"Algorithm('{self.name}')"


class BinaryOperation(Expression):
    """Представляє операцію між двома виразами (наприклад, Індикатор > Число)."""
    def __init__(self, left, op_func, op_symbol, right):
        # Якщо передали звичайне число (напр. 5), автоматично загортаємо його в Constant(5)
        self.left = left if isinstance(left, Expression) else Constant(left)
        self.right = right if isinstance(right, Expression) else Constant(right)
        self.op_func = op_func
        self.op_symbol = op_symbol

    def evaluate(self, registry):
        # 1. Обчислюємо ліву частину
        left_val = self.left.evaluate(registry)
        # 2. Обчислюємо праву частину
        right_val = self.right.evaluate(registry)
        # 3. Виконуємо операцію (наприклад, Pandas Series > 50)
        return self.op_func(left_val, right_val)

    def __repr__(self):
        return f"({self.left} {self.op_symbol} {self.right})"
