import os
import ast
import json
import pandas as pd
from collections import defaultdict

from utils.algorithms.backtesting.SignalProvider import Analyzer
from utils.algorithms.NGramPredictor import NGramPredictor
from utils.config import ensure_predictions_dir_exists

#==================================
# NGram Analyzer
#==================================

class NGramAnalyzer(Analyzer):

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, 
                 db_manager,
                 table_name: str,
                 ngram_length: int = 3, 
                 top: int = 10,
                 min_occurrences: int = 20,
                 tolerance: int = 1,
                 top_patterns: int = None,
                 force_update: bool = False,
                 prediction_road: int = 1):
        """
        Параметри:
        db_manager: DataBaseManager
        table_name: назва таблиці з даними (де є колонка 'WCE')
        ngram_length: кількість токенів, що утворюють патерн (довжина історії N-gram)
        top: кількість топ прогнозів для кожного патерну
        min_occurrences: мінімальна кількість збігів патерну
        tolerance: допуск для кластеризації
        top_patterns: скільки найпопулярніших патернів залишити для аналізу (None - всі)
        force_update: чи перегенерувати файл прогнозів примусово
        prediction_road: розмір дороги прогнозування (кількість токенів у майбутнє)
        """
        
        # Вікно розміром 1, оскільки ми самі збираємо історію токенів по одному
        super().__init__(window_size=1)
        
        self.db_manager = db_manager
        self.table_name = table_name
        self.ngram_length = ngram_length
        self.top = top
        self.min_occurrences = min_occurrences
        self.tolerance = tolerance
        self.top_patterns = top_patterns
        self.force_update = force_update
        self.prediction_road = prediction_road
        
        self.history = []
        
        # Завантажуємо або генеруємо прогнози
        self.predictions = self._load_or_generate_predictions()
        
        # Застосовуємо ліміт на кількість патернів, якщо вказано
        if self.top_patterns is not None and self.top_patterns > 0:
            print(f"Обмеження прогнозів до топових {self.top_patterns} патернів.")
            self.predictions = dict(list(self.predictions.items())[:self.top_patterns])
        
        # Парсимо прогнози для швидкого пошуку (за принципом _cluster_similar_histories)
        self.parsed_predictions = {}
        self.signature_index = defaultdict(list)
        self.valid_prefixes = set() # Для швидкого відкидання невалідних послідовностей
        self._build_search_index()

    #------------------------------
    # Завантаження або генерація
    #------------------------------

    def _load_or_generate_predictions(self) -> dict:
        """Перевіряє наявність predictions_road_X.json, генерує за потреби, повертає словник прогнозів."""
        
        pred_dir = ensure_predictions_dir_exists()
        pred_file = os.path.join(pred_dir, f"predictions_road_{self.prediction_road}.json")
        
        if os.path.exists(pred_file) and not self.force_update:
            try:
                with open(pred_file, "r", encoding='utf-8') as f:
                    print(f"Завантаження існуючих прогнозів з {pred_file}...")
                    return json.load(f)
            except Exception as e:
                print(f"Помилка читання {pred_file}: {e}. Перегенерація прогнозів...")
                
        # Генерація прогнозів
        print("Генерація нових прогнозів NGram (використовуючи колонку WCE з бази даних)...")
        
        df = self.db_manager.get_data_as_dataframe(self.table_name)
        if 'WCE' not in df.columns:
            raise ValueError(f"Колонка 'WCE' відсутня в таблиці {self.table_name}")
            
        predictor = NGramPredictor(df, prediction_road=self.prediction_road)
        predictor._analysis(column_name="WCE", num_tokens=self.ngram_length, top=self.top, min_occurrences=self.min_occurrences, use_fuzzy_logic=True)
        predictor.save_predictions_to_file(filename=pred_file)
        
        with open(pred_file, "r") as f:
            return json.load(f)

    #------------------------------
    # Підготовка індексу для швидкого пошуку
    #------------------------------

    def _parse_token(self, t: str):
        """Перетворює рядок 'B555' на кортеж ('B', 5, 5, 5)"""
        if "N" in t or len(t) < 4:
            return t
        else:
            return (t[0], int(t[1]), int(t[2]), int(t[3]))

    def _build_search_index(self):
        """Будує індекс за напрямками (dir_signature) для швидкого пошуку."""
        for key_str, pred in self.predictions.items():
            # key_str is something like "['B555', 'S555', 'B123']" or "B555 S555 B123"
            try:
                if key_str.startswith('[') or key_str.startswith('('):
                    hist_list = ast.literal_eval(key_str)
                else:
                    hist_list = key_str.split()
            except Exception:
                hist_list = key_str.split()
                
            parsed_hist = tuple(self._parse_token(t) for t in hist_list)
            dir_signature = tuple(pt[0] if isinstance(pt, tuple) else pt for pt in parsed_hist)
            
            self.parsed_predictions[parsed_hist] = pred
            self.signature_index[dir_signature].append(parsed_hist)
            
            # Додаємо всі префікси цієї сигнатури у множину для швидкого фільтрування
            for i in range(1, len(dir_signature) + 1):
                self.valid_prefixes.add(dir_signature[:i])

    #------------------------------
    # Метод генерації сигналів
    #------------------------------

    def check_signal(self, window: pd.DataFrame) -> str:
        """
        Отримує через callback свічку (window розміром 1) і збирає дані.
        Повертає 'BUY', 'SELL', 'CLOSE' або None.
        """
        
        token = window['WCE'].iloc[0]
        self.history.append(token)
        
        # Зберігаємо лише останні ngram_length токенів
        if len(self.history) > self.ngram_length:
            self.history.pop(0)
            
        parsed_hist = tuple(self._parse_token(t) for t in self.history)
        dir_signature = tuple(pt[0] if isinstance(pt, tuple) else pt for pt in parsed_hist)
        
        # Оптимізація: перевіряємо, чи є поточна історія (префікс) взагалі перспективною
        if dir_signature not in self.valid_prefixes:
            # Замість агресивного скидання історії просто повертаємо None,
            # дозволяючи вікну "ковзати" і накопичувати нові токени (наприклад, після D-токенів)
            return None
            
        if len(self.history) < self.ngram_length:
            return None
            
        # Якщо ми тут, значить довжина історії = ngram_length і dir_signature знайдено в valid_prefixes (і в signature_index)
            
        # Детальна перевірка з використанням tolerance
        found_prediction = None
        for base_parsed in self.signature_index[dir_signature]:
            is_similar = True
            for pt1, pt2 in zip(parsed_hist, base_parsed):
                if type(pt1) != type(pt2):
                    is_similar = False
                    break
                    
                if isinstance(pt1, tuple):
                    if abs(pt1[1] - pt2[1]) > self.tolerance or \
                       abs(pt1[2] - pt2[2]) > self.tolerance or \
                       abs(pt1[3] - pt2[3]) > self.tolerance:
                        is_similar = False
                        break
                elif pt1 != pt2:
                    is_similar = False
                    break
            
            if is_similar:
                found_prediction = self.parsed_predictions[base_parsed]
                break
                
        # 3. Якщо патерн знайдено, інтерпретуємо сигнал
        if found_prediction and len(found_prediction) > 0:
            predicted_token = found_prediction[0][0]
            
            # Якщо ми прогнозуємо цілу "дорогу" (список токенів), для входу беремо перший
            if isinstance(predicted_token, (list, tuple)):
                if len(predicted_token) > 0:
                    predicted_token = predicted_token[0]
                else:
                    return None
            
            if predicted_token.startswith('B'):
                return 'BUY'
            elif predicted_token.startswith('S'):
                return 'SELL'
                
        return None
