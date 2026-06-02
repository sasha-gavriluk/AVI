import pandas as pd
import operator

class Expression:
    """Базовий клас для всіх логічних виразів у нашому ООП-будівельнику."""
    
    def evaluate(self, registry):
        """Цей метод має бути реалізований у дочірніх класах."""
        raise NotImplementedError("Метод evaluate() має бути перевизначений.")

    def evaluate_proximity(self, registry):
        """
        Повертає 'відсоток готовності' сигналу від 0.0 до 1.0 (Fuzzy Logic).
        За замовчуванням (для булевих значень), повертає 1.0 якщо True, 0.0 якщо False.
        """
        val = self.evaluate(registry)
        if isinstance(val, pd.Series):
            if val.dtype == bool:
                return val.astype(float)
            else:
                return val # Якщо це просто число (напр. RSI), повертаємо його
        else:
            if isinstance(val, bool):
                return 1.0 if val else 0.0
            return val

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
        return BinaryOperation(self, operator.and_, "&", other)

    def __or__(self, other):
        return BinaryOperation(self, operator.or_, "|", other)

    # Математичні оператори
    def __add__(self, other):
        return BinaryOperation(self, operator.add, "+", other)

    def __sub__(self, other):
        return BinaryOperation(self, operator.sub, "-", other)

    def __mul__(self, other):
        return BinaryOperation(self, operator.mul, "*", other)

    def __truediv__(self, other):
        return BinaryOperation(self, operator.truediv, "/", other)

    # Спеціальні операції (Перетин)
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
        
        l_prev = l_val.shift(1) if isinstance(l_val, pd.Series) else l_val
        r_prev = r_val.shift(1) if isinstance(r_val, pd.Series) else r_val
        
        try:
            return (l_val > r_val) & (l_prev <= r_prev)
        except Exception:
            if isinstance(l_val, pd.Series):
                return pd.Series(False, index=l_val.index)
            return False

    def evaluate_proximity(self, registry):
        l_val = self.left.evaluate(registry)
        r_val = self.right.evaluate(registry)
        is_true = self.evaluate(registry)
        
        try:
            denom = r_val.abs()
            if isinstance(denom, pd.Series):
                denom = denom.where(denom != 0, l_val.abs())
                denom = denom.replace(0, 1e-5)
            else:
                denom = denom if denom != 0 else abs(l_val)
                denom = denom if denom != 0 else 1e-5
                
            diff = (r_val - l_val) # Відстань до перетину.
            pct_diff = diff.abs() / denom
            max_pct = 0.15 # Буферна зона 15% для перетину
            
            prox = 1.0 - (pct_diff / max_pct)
            if isinstance(prox, pd.Series):
                prox = prox.clip(lower=0.0, upper=1.0)
                # Якщо left > right, але is_true = False (перетин був давно) -> prox = 0
                prox = prox.where(l_val <= r_val, 0.0) 
                prox = prox.where(~is_true, 1.0)
            else:
                prox = max(0.0, min(1.0, prox))
                if l_val > r_val and not is_true:
                    prox = 0.0
                if is_true:
                    prox = 1.0
            return prox
        except:
            return is_true.astype(float) if isinstance(is_true, pd.Series) else (1.0 if is_true else 0.0)

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
        
        try:
            return (l_val < r_val) & (l_prev >= r_prev)
        except Exception:
            if isinstance(l_val, pd.Series):
                return pd.Series(False, index=l_val.index)
            return False

    def evaluate_proximity(self, registry):
        l_val = self.left.evaluate(registry)
        r_val = self.right.evaluate(registry)
        is_true = self.evaluate(registry)
        
        try:
            denom = r_val.abs()
            if isinstance(denom, pd.Series):
                denom = denom.where(denom != 0, l_val.abs())
                denom = denom.replace(0, 1e-5)
            else:
                denom = denom if denom != 0 else abs(l_val)
                denom = denom if denom != 0 else 1e-5
                
            diff = (l_val - r_val)
            pct_diff = diff.abs() / denom
            max_pct = 0.15
            
            prox = 1.0 - (pct_diff / max_pct)
            if isinstance(prox, pd.Series):
                prox = prox.clip(lower=0.0, upper=1.0)
                prox = prox.where(l_val >= r_val, 0.0) 
                prox = prox.where(~is_true, 1.0)
            else:
                prox = max(0.0, min(1.0, prox))
                if l_val < r_val and not is_true:
                    prox = 0.0
                if is_true:
                    prox = 1.0
            return prox
        except:
            return is_true.astype(float) if isinstance(is_true, pd.Series) else (1.0 if is_true else 0.0)

    def __repr__(self):
        return f"CrossUnder({self.left}, {self.right})"


class Constant(Expression):
    def __init__(self, value):
        self.value = value

    def evaluate(self, registry):
        return self.value

    def __repr__(self):
        return str(self.value)


class Indicator(Expression):
    def __init__(self, name: str):
        self.name = name

    def evaluate(self, registry):
        return registry.get_indicator(self.name)

    def __repr__(self):
        return f"Indicator('{self.name}')"


class Pattern(Expression):
    def __init__(self, name: str):
        self.name = name

    def evaluate(self, registry):
        return registry.get_indicator(self.name)

    def __repr__(self):
        return f"Pattern('{self.name}')"


class Algorithm(Expression):
    def __init__(self, name: str):
        self.name = name

    def evaluate(self, registry):
        return registry.get_indicator(self.name)

    def __repr__(self):
        return f"Algorithm('{self.name}')"


class BinaryOperation(Expression):
    def __init__(self, left, op_func, op_symbol, right):
        self.left = left if isinstance(left, Expression) else Constant(left)
        self.right = right if isinstance(right, Expression) else Constant(right)
        self.op_func = op_func
        self.op_symbol = op_symbol

    def evaluate(self, registry):
        left_val = self.left.evaluate(registry)
        right_val = self.right.evaluate(registry)
        try:
            return self.op_func(left_val, right_val)
        except Exception:
            if isinstance(left_val, pd.Series):
                return pd.Series(False, index=left_val.index)
            elif isinstance(right_val, pd.Series):
                return pd.Series(False, index=right_val.index)
            return False

    def evaluate_proximity(self, registry):
        if self.op_symbol == "&":
            l_prox = self.left.evaluate_proximity(registry)
            r_prox = self.right.evaluate_proximity(registry)
            try:
                # Використовуємо СЕРЕДНЄ значення (Average) замість MIN.
                # Це дозволяє оцінювати часткову готовність. Наприклад, якщо A=1.0, B=0.0, готовність = 50%.
                if isinstance(l_prox, pd.Series) and isinstance(r_prox, pd.Series):
                    return (l_prox + r_prox) / 2.0
                elif isinstance(l_prox, pd.Series):
                    return (l_prox + r_prox) / 2.0
                elif isinstance(r_prox, pd.Series):
                    return (l_prox + r_prox) / 2.0
                else:
                    return (l_prox + r_prox) / 2.0
            except:
                # Фолбек для жорстких булевих значень
                val = l_prox & r_prox
                return val.astype(float) if isinstance(val, pd.Series) else (1.0 if val else 0.0)
                
        elif self.op_symbol == "|":
            l_prox = self.left.evaluate_proximity(registry)
            r_prox = self.right.evaluate_proximity(registry)
            try:
                if isinstance(l_prox, pd.Series) and isinstance(r_prox, pd.Series):
                    return pd.DataFrame({'l': l_prox, 'r': r_prox}).max(axis=1)
                elif isinstance(l_prox, pd.Series):
                    return l_prox.clip(lower=r_prox)
                elif isinstance(r_prox, pd.Series):
                    return r_prox.clip(lower=l_prox)
                else:
                    return max(l_prox, r_prox)
            except:
                val = l_prox | r_prox
                return val.astype(float) if isinstance(val, pd.Series) else (1.0 if val else 0.0)
                
        elif self.op_symbol in [">", "<", ">=", "<=", "=="]:
            is_true = self.evaluate(registry)
            left_val = self.left.evaluate(registry)
            right_val = self.right.evaluate(registry)
            
            try:
                max_pct = 0.15 # 15% буферна зона
                denom = right_val.abs() if hasattr(right_val, 'abs') else abs(right_val)
                
                if isinstance(denom, pd.Series):
                    denom = denom.where(denom != 0, left_val.abs() if hasattr(left_val, 'abs') else abs(left_val))
                    denom = denom.replace(0, 1e-5)
                else:
                    denom = denom if denom != 0 else (abs(left_val) if left_val else 1e-5)
                    denom = denom if denom != 0 else 1e-5
                    
                diff = (left_val - right_val).abs() if hasattr((left_val - right_val), 'abs') else abs(left_val - right_val)
                pct_diff = diff / denom
                
                prox = 1.0 - (pct_diff / max_pct)
                
                if isinstance(prox, pd.Series):
                    prox = prox.clip(lower=0.0, upper=1.0)
                    prox = prox.where(~is_true, 1.0)
                else:
                    prox = max(0.0, min(1.0, prox))
                    if is_true:
                        prox = 1.0
                return prox
            except Exception:
                return is_true.astype(float) if isinstance(is_true, pd.Series) else (1.0 if is_true else 0.0)
        else:
            return self.evaluate(registry)

    def __repr__(self):
        return f"({self.left} {self.op_symbol} {self.right})"
