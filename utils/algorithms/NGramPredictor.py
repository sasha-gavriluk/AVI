import pandas as pd
import numpy as np
import json

from collections import defaultdict, Counter
from utils.OtherUtils import _handle_error
from utils.Config import ensure_predictions_dir_exists

#==================================
# NGramPredictor
#==================================

class NGramPredictor:

    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, data: pd.DataFrame, prediction_road: int = 2):
        self.data = data
        self.prediction_road = prediction_road
        

    # ----------------------------------
    # Метод для отримання колонки з даними
    # ----------------------------------

    @_handle_error
    def _get_column(self, column_name: str):
        """Метод для отримання колонки з даними column_name: назва колонки"""

        if column_name in self.data.columns:
            return self.data[column_name].dropna().values
        
        return np.array([])
    
    # ----------------------------------
    # Метод для збору тріграми та передбачення наступного токена
    # ----------------------------------
    
    @_handle_error
    def _collect_trigrams(self, column_name: str = None, data: list = None, num_tokens: int = 3):
        """Метод для збору тріграми з колонки column_name: назва колонки data: список даних для збору тріграми (якщо не вказано, буде використана колонка column_name)"""

        column_data = data if data is not None else self._get_column(column_name)

        trigrams = defaultdict(list)
        pattern_popularity = Counter()

        for i in range(len(column_data) - num_tokens - self.prediction_road + 1):
            history = tuple(column_data[i : i + num_tokens])
            if self.prediction_road == 1:
                next_items = column_data[i + num_tokens]
            else:
                next_items = tuple(column_data[i + num_tokens : i + num_tokens + self.prediction_road])

            trigrams[history].append(next_items)
            pattern_popularity[history] += 1

        return trigrams, pattern_popularity
    
    # ----------------------------------
    # Метод для передбачення наступного токена на основі історії
    # ----------------------------------

    @_handle_error
    def _predict_next_token(self, history: tuple, trigrams: dict, top: int = 1) -> str:
        """Метод для передбачення наступного токена на основі історії history: кортеж з num_tokens токенів trigrams: словарь з тріграмами top: кількість найбільш ймовірних токенів для повернення"""

        next_tokens = trigrams.get(history, [])
         
        if not next_tokens:
            return None
        
        token_counts = Counter(next_tokens)
        return token_counts.most_common(top)
    
    # ----------------------------------
    # Метод для кластеризації патернів на основі схожості
    # ----------------------------------

    @_handle_error
    def _cluster_similar_histories(self, exact_trigrams: dict, exact_popularity: Counter, tolerance: int = 1) -> tuple:
        """Зливає схожі патерни в один 'базовий' патерн (Швидка версія)."""

        cluster_trigrams = defaultdict(list)
        cluster_popularity = Counter()

        parsed_cache = {}
        for history in exact_popularity.keys():
            parsed_hist = []
            for t in history:
                if "N" in t or len(t) < 4:
                    parsed_hist.append(t)
                else:
                    if len(t) >= 5:
                        parsed_hist.append((t[0], int(t[1]), int(t[2]), int(t[3]), int(t[4])))
                    else:
                        parsed_hist.append((t[0], int(t[1]), int(t[2]), int(t[3])))
            parsed_cache[history] = tuple(parsed_hist)

        clusters_by_direction = defaultdict(list)

        sorted_histories = sorted(exact_popularity.items(), key=lambda x: x[1], reverse=True)

        for history, count in sorted_histories:
            parsed_hist = parsed_cache[history]
            
            dir_signature = tuple(
                pt[0] if isinstance(pt, tuple) else pt for pt in parsed_hist
            )

            found_cluster = None
            
            for base_history in clusters_by_direction[dir_signature]:
                base_parsed = parsed_cache[base_history]
                
                is_similar = True
                for pt1, pt2 in zip(parsed_hist, base_parsed):
                    if type(pt1) != type(pt2):
                        is_similar = False
                        break
                    
                    if isinstance(pt1, tuple):
                        if abs(pt1[1] - pt2[1]) > tolerance or \
                           abs(pt1[2] - pt2[2]) > tolerance or \
                           abs(pt1[3] - pt2[3]) > tolerance:
                            is_similar = False
                            break
                            
                        if len(pt1) > 4 and len(pt2) > 4:
                            if abs(pt1[4] - pt2[4]) > tolerance:
                                is_similar = False
                                break
                    elif pt1 != pt2:
                        is_similar = False
                        break
                
                if is_similar:
                    found_cluster = base_history
                    break

            if found_cluster:
                cluster_trigrams[found_cluster].extend(exact_trigrams[history])
                cluster_popularity[found_cluster] += count
            else:
                cluster_trigrams[history] = exact_trigrams[history]
                cluster_popularity[history] += count
                clusters_by_direction[dir_signature].append(history)

        return cluster_trigrams, cluster_popularity

    # ----------------------------------
    # Метод для сортування патернів за популярністю
    # ----------------------------------

    @_handle_error
    def _sort(self, predictions: dict):
        """Сортує патерни. Параметри: predictions - словарь з патернами від більш популярного до менш популярного"""

        sorted_predictions = dict(sorted(
            predictions.items(), 
            key=lambda item: item[1][0][1] if item[1] and item[1][0] else 0, 
            reverse=True
        ))

        return sorted_predictions
    
    # ----------------------------------
    # Метод для аналізу даних та передбачення наступного токена
    # ----------------------------------

    @_handle_error
    def _analysis(self, column_name: str = None, data: list = None, num_tokens: int = 3, top: int = 1, min_occurrences: int = 10, use_fuzzy_logic: bool = True) -> dict:
        """Метод для аналізу даних та передбачення наступного токена column_name: назва колонки data: список даних для аналізу (якщо не вказано, буде використана колонка column_name) num_tokens: кількість токенів в історії top: кількість найбільш ймовірних токенів для повернення, min_occurrences: мінімальна кількість появ патерну для його включення в передбачення use_fuzzy_logic: чи використовувати нечітку логіку для злиття схожих патернів"""

        trigrams, pattern_popularity = self._collect_trigrams(column_name=column_name, data=data, num_tokens=num_tokens)
        
        if use_fuzzy_logic:
            trigrams, pattern_popularity = self._cluster_similar_histories(trigrams, pattern_popularity, tolerance=1)

        predictions = {}
        for history in trigrams.keys():

            if pattern_popularity[history] >= min_occurrences:
                predictions[history] = self._predict_next_token(history, trigrams, top=top)

        self.predictions = self._sort(predictions)
        return self.predictions
    
    # ----------------------------------
    # Метод для збереження результатів аналізу у файл
    # ----------------------------------

    @_handle_error
    def save_predictions_to_file(self, filename: str = None, fname: str = None):
        """Метод для збереження результатів аналізу у файл predictions: словарь з історіями та їх передбаченнями filename: назва файлу для збереження результатів"""

        if not hasattr(self, "predictions"):
            print("Немає результатів для збереження. Виконайте спочатку метод _analysis.")
            return

        if fname is None:
            fname = f"predictions_road_{self.prediction_road}.json"

        if filename is None:
            filename = ensure_predictions_dir_exists() + f"/{fname}"

        json_ready_predictions = {
            str(list(history)): predicted_token 
            for history, predicted_token in self.predictions.items()
        }

        with open(filename, "w", encoding='utf-8') as f:
            json.dump(json_ready_predictions, f, indent=4)