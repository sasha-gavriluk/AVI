import json
import os
import random
import sys

# Додаємо корінь проекту до шляху для імпорту страховки
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
from utils.create_insurance import Insurance

class StrategyGenerator:
    """
    Генератор торгових стратегій, що використовує правила з rules.json.
    Враховує Tolerance для створення варіативності, та Симбіоз для поєднання індикаторів.
    Може генерувати стратегії виключно на покупку (BUY) або виключно на продаж (SELL).
    """
    def __init__(self, rules_path=None, copilot=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        # Гарантуємо, що файли конфігурації існують
        Insurance.ensure_files_exist(base_dir)
        
        if rules_path is None:
            self.rules_path = os.path.join(base_dir, 'data', 'config', 'rules.json')
        else:
            self.rules_path = rules_path
            
        self.copilot = copilot
        self.rules = self._load_rules()
        self.meta_data = self._load_meta()
        
    def _load_meta(self):
        meta_path = os.path.join(os.path.dirname(self.rules_path), 'strategy_meta.json')
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Помилка завантаження strategy_meta.json: {e}. Використовуємо страховку.")
            return Insurance.get_meta_content()
        
    def _load_rules(self):
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Помилка завантаження {self.rules_path}: {e}. Використовуємо страховку.")
            return Insurance.get_rules_content()
            
    def _apply_tolerance(self, val, tolerance):
        """Застосовує випадкове відхилення до значення в межах tolerance."""
        if isinstance(val, (int, float)) and tolerance > 0:
            # Генеруємо зсув, наприклад якщо 30, tolerance 5 -> від 25 до 35
            shift = random.uniform(-tolerance, tolerance)
            if isinstance(val, int):
                return int(val + shift)
            return round(val + shift, 2)
        return val

    def _get_class_by_type(self, t):
        if "pattern" in t.lower(): return "Pattern"
        if "algorithm" in t.lower(): return "Algorithm"
        return "Indicator"

    def _build_conditions(self, var_name, conditions):
        """Формує Python код умов на основі правил."""
        if not conditions:
            return "False"
            
        cond_strs = []
        for c in conditions:
            op = c["op"]
            val = c["value"]
            tol = c.get("tolerance", 0)
            
            # Обробка спеціальних значень
            if isinstance(val, str):
                final_val = f"\"{val}\""
            elif isinstance(val, bool):
                final_val = "True" if val else "False"
            else:
                final_val = self._apply_tolerance(val, tol)
                
            cond_strs.append(f"({var_name} {op} {final_val})")
            
        return " & ".join(cond_strs)

    def _generate_indicator_args(self, base_name, class_type):
        """Шукає індикатор в мета-даних та генерує випадкові параметри (періоди тощо)."""
        if not self.meta_data:
            return base_name
            
        base_id = base_name.lower()
        if "_" in base_id and base_id not in ["ema_cross", "sma_cross", "bollinger_upper", "bollinger_lower", "keltner_upper", "keltner_lower", "volume_avg", "market_state_linear", "order_blocks", "ngram_road", "inverted_hammer", "shooting_star", "morning_star", "evening_star", "hanging_man", "three_white_soldiers", "three_black_crows", "wce_anomaly"]:
            # Щоб відсікти суфікси типу _14
            base_id = base_id.split("_")[0]
            
        # Шукаємо в мета-даних
        for cat in self.meta_data.get("categories", []):
            for item in cat.get("items", []):
                if item["id"] == base_id or item["id"].replace("_", "") == base_id.replace("_", ""):
                    if not item.get("params"):
                        return base_name
                        
                    param_vals = []
                    for param in item["params"]:
                        val = param.get("default", 14)
                        if param.get("type") == "int" and "min" in param and "max" in param:
                            # Генеруємо період в межах [min, max]
                            v_max = min(param["max"], max(val * 2, 50))
                            val = random.randint(param["min"], v_max)
                        elif param.get("type") == "float":
                            val = round(random.uniform(param.get("min", 0.1), param.get("max", 5.0)), 1)
                        param_vals.append(str(val))
                        
                    suffix = "_" + "_".join(param_vals)
                    if class_type == "Algorithm" and base_id == "ngram_road":
                        return f"NGRAM_ROAD_{param_vals[0]}"
                    elif class_type == "Algorithm" and base_id == "wce_anomaly":
                        return f"WCE_ANOMALY_{param_vals[0]}_{param_vals[1]}"
                    elif class_type == "Algorithm":
                        return base_id.upper()
                    elif class_type == "Pattern":
                        return base_id.replace("_", " ").title().replace(" ", "_")
                    else:
                        return base_id.upper() + suffix
                        
        return base_name

    def generate(self, direction="BUY") -> str:
        """
        Генерує готову Python стратегію.
        direction: "BUY" або "SELL"
        """
        if not self.rules:
            return "# Помилка: відсутні правила генерації"
            
        # Якщо передано copilot, можемо викликати самонавчання перед генерацією
        copilot_rating = {}
        if self.copilot:
            if hasattr(self.copilot, 'update_rules_from_experience'):
                self.copilot.update_rules_from_experience(self.rules_path)
                self.rules = self._load_rules()
            if hasattr(self.copilot, 'get_best_components'):
                copilot_rating = self.copilot.get_best_components(direction)
            
        # 1. Знаходимо підходящі сигнали
        signals_pool = []
        for name, data in self.rules.items():
            if data.get("role") == "signal":
                d = data.get("direction", "both")
                if direction == "BUY" and d in ["both", "buy_only"]:
                    if data.get("buy_conditions"): signals_pool.append((name, data))
                elif direction == "SELL" and d in ["both", "sell_only"]:
                    if data.get("sell_conditions"): signals_pool.append((name, data))
                    
        if not signals_pool:
            return "# Помилка: не знайдено сигналів для даного напрямку"
            
        # Зважений вибір сигналу на основі copilot_rating
        signal_weights = []
        for name, _ in signals_pool:
            weight = 1.0
            for comp, score in copilot_rating.items():
                if name.upper() in comp.upper():
                    weight += score * 3  # Збільшуємо вагу за рахунок рейтингу
                    break
            signal_weights.append(weight)
            
        sig_name, sig_data = random.choices(signals_pool, weights=signal_weights, k=1)[0]
        
        # 2. Підбираємо фільтр за симбіозом
        num_filters = random.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
        
        filters_list = []
        symbiosis_strong = sig_data.get("symbiosis", {}).get("strong", [])
        symbiosis_moderate = sig_data.get("symbiosis", {}).get("moderate", [])
        avoid = sig_data.get("symbiosis", {}).get("avoid", [])
        
        preferred = symbiosis_strong + symbiosis_moderate
        for name, data in self.rules.items():
            if data.get("role") == "filter" and name not in avoid:
                # Базова вага
                weight = 1.0
                if name in symbiosis_strong:
                    weight = 3.0
                elif name in symbiosis_moderate:
                    weight = 2.0
                    
                # Додаємо вагу з досвіду копілота
                for comp, score in copilot_rating.items():
                    if name.upper() in comp.upper():
                        weight += score * 5
                        break
                        
                # Перевіряємо чи підходить для напрямку
                d = data.get("direction", "both")
                if direction == "BUY" and d in ["both", "buy_only"] and data.get("buy_conditions"):
                    filters_list.append((name, data, weight))
                elif direction == "SELL" and d in ["both", "sell_only"] and data.get("sell_conditions"):
                    filters_list.append((name, data, weight))
                        
        chosen_filters = []
        if filters_list:
            actual_num = min(num_filters, len(filters_list))
            while len(chosen_filters) < actual_num:
                available = [f for f in filters_list if not any(cf[0] == f[0] for cf in chosen_filters)]
                if not available:
                    break
                a_weights = [f[2] for f in available]
                chosen = random.choices(available, weights=a_weights, k=1)[0]
                chosen_filters.append((chosen[0], chosen[1]))
        
        # 3. Генеруємо код
        lines = []
        lines.append("from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy")
        lines.append("")
        lines.append(f"# Згенерована ШІ стратегія. Напрямок: {direction}")
        lines.append(f"# Основний сигнал: {sig_name}")
        if chosen_filters:
            lines.append(f"# Фільтри: {', '.join(f[0] for f in chosen_filters)}")
        lines.append("")
        
        # Оголошення
        sig_class = self._get_class_by_type(sig_data.get('type', ''))
        sig_arg = self._generate_indicator_args(sig_name, sig_class)
        sig_var = sig_name.lower().split("_")[0] + "_sig" # Щоб імена змінних не конфліктували
        lines.append(f"{sig_var} = {sig_class}(\"{sig_arg}\")")
        
        filter_vars = []
        for i, (fil_name, fil_data) in enumerate(chosen_filters):
            fil_class = self._get_class_by_type(fil_data.get('type', ''))
            fil_arg = self._generate_indicator_args(fil_name, fil_class)
            fil_var = fil_name.lower().split("_")[0] + f"_fil_{i}"
            lines.append(f"{fil_var} = {fil_class}(\"{fil_arg}\")")
            filter_vars.append((fil_var, fil_data))
            
        lines.append("")
        
        # Логіка
        if direction == "BUY":
            entry_sig = self._build_conditions(sig_var, sig_data["buy_conditions"])
            if filter_vars:
                entry_fils = [self._build_conditions(fv, fd["buy_conditions"]) for fv, fd in filter_vars]
                entry_rule = f"{entry_sig} & " + " & ".join(entry_fils)
            else:
                entry_rule = entry_sig
                
            exit_sig = self._build_conditions(sig_var, sig_data.get("sell_conditions", []))
            # Якщо сигнал не має sell conditions (наприклад buy_only патерн), ми повинні виходити по фільтру або тайм-ауту.
            if exit_sig == "False" and filter_vars:
                # Виходимо по протилежному сигналу першого фільтра
                exit_rule = self._build_conditions(filter_vars[0][0], filter_vars[0][1].get("sell_conditions", []))
            else:
                exit_rule = exit_sig
                
        else: # SELL (Шорт)
            entry_sig = self._build_conditions(sig_var, sig_data["sell_conditions"])
            if filter_vars:
                entry_fils = [self._build_conditions(fv, fd["sell_conditions"]) for fv, fd in filter_vars]
                entry_rule = f"{entry_sig} & " + " & ".join(entry_fils)
            else:
                entry_rule = entry_sig
                
            exit_sig = self._build_conditions(sig_var, sig_data.get("buy_conditions", []))
            if exit_sig == "False" and filter_vars:
                exit_rule = self._build_conditions(filter_vars[0][0], filter_vars[0][1].get("buy_conditions", []))
            else:
                exit_rule = exit_sig

        lines.append(f"entry = {entry_rule}")
        lines.append(f"exit = {exit_rule}")
        lines.append("")
        # Передаємо напрямок у Strategy (потребує підтримки у rules_engine)
        lines.append(f"strategy = Strategy(entry_rule=entry, exit_rule=exit)")
        
        return "\n".join(lines)
