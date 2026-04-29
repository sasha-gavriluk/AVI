from PyQt6.QtWidgets import QTableView
from PyQt6.QtCore import QAbstractTableModel, Qt
import pandas as pd

# ==================================
# Модель для Pandas Dataframe
# ==================================

class PandasTableModel(QAbstractTableModel):
    """Модель даних для ефективного зв'язування Pandas DataFrame з QTableView"""
    
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------
    
    def __init__(self, data=None):
        """Метод для ініціалізації табличної моделі"""
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()
        
    # ----------------------------------
    # Оновлення даних
    # ----------------------------------
        
    def update_data(self, data: pd.DataFrame):
        """Метод для оновлення DataFrame та сповіщення віджета про зміни"""
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    # ----------------------------------
    # Перевизначені методи QAbstractTableModel
    # ----------------------------------

    def rowCount(self, parent=None):
        """Метод для отримання кількості рядків у DataFrame"""
        return self._data.shape[0]

    def columnCount(self, parent=None):
        """Метод для отримання кількості колонок у DataFrame"""
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Метод для надання даних для конкретної комірки за її індексом"""
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._data.iat[index.row(), index.column()]
            return str(value)
        return None

    def headerData(self, section, orientation, role):
        """Метод для відображення заголовків колонок та рядків"""
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            if orientation == Qt.Orientation.Vertical:
                return str(self._data.index[section])
        return None

# ==================================
# Віджет таблиці
# ==================================

class DataTableView(QTableView):
    """Візуальний віджет таблиці для відображення даних бази"""
    
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------
    
    def __init__(self):
        """Метод для ініціалізації візуальної таблиці та її налаштувань"""
        super().__init__()
        self.model = PandasTableModel()
        self.setModel(self.model)
        
        # Налаштування вигляду
        self.setAlternatingRowColors(True)
        
    # ----------------------------------
    # Передача даних
    # ----------------------------------
        
    def set_data(self, df: pd.DataFrame):
        """Метод для передачі нових даних у модель та автозміни розміру колонок"""
        self.model.update_data(df)
        self.resizeColumnsToContents()
