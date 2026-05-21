from PyQt6.QtWidgets import QLabel, QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit, QGroupBox, QWidget

class NonWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class NonWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

#==================================
# UiElements
#==================================
class TitleLabel(QLabel):
    # ----------------------------------
    # __init__, ініціалізація заголовку
    # ----------------------------------
    # Параметри:
    # text (str): Текст, який буде відображено в заголовку
    def __init__(self, text: str):
        super().__init__(text)
        self.setStyleSheet("font-size: 20px; font-weight: bold; color: #F9E2AF; margin-bottom: 10px;")

class StyledGroupBox(QGroupBox):
    # ----------------------------------
    # __init__, ініціалізація стилізованої групи
    # ----------------------------------
    # Параметри:
    # title (str): Заголовок групи елементів
    def __init__(self, title: str):
        super().__init__(title)
        self.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")

class PasswordLineEdit(QLineEdit):
    # ----------------------------------
    # __init__, ініціалізація поля для вводу пароля
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        super().__init__()
        self.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244; padding: 5px;")

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QTableView
from PyQt6.QtCore import pyqtSignal, QAbstractTableModel, Qt
import pandas as pd

class DbTreeView(QTreeWidget):
    # ----------------------------------
    # __init__, ініціалізація дерева БД
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.itemClicked.connect(self._on_item_clicked)
        
    table_selected = pyqtSignal(str, str)
        
    # ----------------------------------
    # populate, заповнення дерева даними
    # ----------------------------------
    # Параметри:
    # databases_dict (dict): Словник з даними про БД та таблиці
    def populate(self, databases_dict: dict):
        self.clear()
        for db_name, data in databases_dict.items():
            db_path = data.get("path")
            tables = data.get("tables", [])
            root_item = QTreeWidgetItem([db_name])
            root_item.setData(0, 32, "database") 
            root_item.setData(0, 34, db_path)
            self.addTopLevelItem(root_item)
            for table in tables:
                table_item = QTreeWidgetItem([table])
                table_item.setData(0, 32, "table")
                table_item.setData(0, 33, table)
                table_item.setData(0, 34, db_path)
                root_item.addChild(table_item)

    # ----------------------------------
    # _on_item_clicked, обробка кліку по дереву
    # ----------------------------------
    # Параметри:
    # item (QTreeWidgetItem): Елемент, на який клікнули
    # column (int): Колонка кліку
    def _on_item_clicked(self, item, column):
        item_type = item.data(0, 32)
        if item_type == "table":
            table_name = item.data(0, 33)
            db_path = item.data(0, 34)
            self.table_selected.emit(db_path, table_name)

class PandasTableModel(QAbstractTableModel):
    # ----------------------------------
    # __init__, ініціалізація моделі таблиці
    # ----------------------------------
    # Параметри:
    # data (pd.DataFrame): Дані таблиці
    def __init__(self, data=None):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()
        
    # ----------------------------------
    # update_data, оновлення даних в моделі
    # ----------------------------------
    # Параметри:
    # data (pd.DataFrame): Нові дані таблиці
    def update_data(self, data):
        self.beginResetModel()
        self._data = data if data is not None else pd.DataFrame()
        self.endResetModel()

    # ----------------------------------
    # rowCount, отримання кількості рядків
    # ----------------------------------
    # Параметри:
    # parent (QModelIndex): Батьківський індекс
    def rowCount(self, parent=None):
        return self._data.shape[0]

    # ----------------------------------
    # columnCount, отримання кількості колонок
    # ----------------------------------
    # Параметри:
    # parent (QModelIndex): Батьківський індекс
    def columnCount(self, parent=None):
        return self._data.shape[1]

    # ----------------------------------
    # data, отримання даних для комірки
    # ----------------------------------
    # Параметри:
    # index (QModelIndex): Індекс комірки
    # role (int): Роль даних
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self._data.iat[index.row(), index.column()])
        return None

    # ----------------------------------
    # headerData, отримання заголовків
    # ----------------------------------
    # Параметри:
    # section (int): Секція заголовку
    # orientation (Qt.Orientation): Орієнтація
    # role (int): Роль даних
    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal: return str(self._data.columns[section])
            if orientation == Qt.Orientation.Vertical: return str(self._data.index[section])
        return None

class DataTableView(QTableView):
    # ----------------------------------
    # __init__, ініціалізація візуальної таблиці
    # ----------------------------------
    # Параметри: немає
    def __init__(self):
        super().__init__()
        self.model = PandasTableModel()
        self.setModel(self.model)
        self.setAlternatingRowColors(True)
        
    # ----------------------------------
    # set_data, встановлення даних таблиці
    # ----------------------------------
    # Параметри:
    # df (pd.DataFrame): Дані таблиці pandas
    def set_data(self, df: pd.DataFrame):
        self.model.update_data(df)
        self.resizeColumnsToContents()

class TradeDetailPanel(QWidget):
    # ----------------------------------
    # __init__, ініціалізація панелі угод
    # ----------------------------------
    # Параметри:
    # parent (QWidget): Батьківський віджет
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        
        from PyQt6.QtWidgets import QVBoxLayout, QLabel, QTextEdit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        group = StyledGroupBox("Деталі Угоди")
        vbox = QVBoxLayout(group)
        
        self.lbl_id = QLabel("ID: -")
        self.lbl_dir = QLabel("Напрям: -")
        self.lbl_profit = QLabel("Прибуток: -")
        self.lbl_profit.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_duration = QLabel("Тривалість: -")
        
        vbox.addWidget(self.lbl_id)
        vbox.addWidget(self.lbl_dir)
        vbox.addWidget(self.lbl_profit)
        vbox.addWidget(self.lbl_duration)
        
        vbox.addWidget(QLabel("Лог (Сигнали):"))
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #313244;")
        vbox.addWidget(self.txt_log)
        
        layout.addWidget(group)
        
    # ----------------------------------
    # set_trade_details, заповнення панелі даними
    # ----------------------------------
    # Параметри:
    # trade_id (str): ID угоди
    # direction (str): Напрям
    # profit (float): Прибуток
    # duration (int): Тривалість у хвилинах
    # log_text (str): Текст логу
    def set_trade_details(self, trade_id: str, direction: str, profit: float, duration: int, log_text: str):
        self.lbl_id.setText(f"ID: {trade_id}")
        self.lbl_dir.setText(f"Напрям: {direction}")
        color = "#A6E3A1" if profit > 0 else "#F38BA8"
        self.lbl_profit.setText(f"Прибуток: {profit:.2f}")
        self.lbl_profit.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
        self.lbl_duration.setText(f"Тривалість: {duration} хв")
        self.txt_log.setText(log_text)
        
    # ----------------------------------
    # clear, очищення панелі
    # ----------------------------------
    # Параметри: немає
    def clear(self):
        self.lbl_id.setText("ID: -")
        self.lbl_dir.setText("Напрям: -")
        self.lbl_profit.setText("Прибуток: -")
        self.lbl_profit.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_duration.setText("Тривалість: -")
        self.txt_log.clear()
