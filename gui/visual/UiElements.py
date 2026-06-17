from PyQt6.QtWidgets import QLabel, QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit, QGroupBox, QWidget, QVBoxLayout, QTableWidget, QHeaderView, QTableWidgetItem
from PyQt6.QtGui import QColor

class NonWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class NonWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

#==================================
# UiElements
#==================================
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, QEvent

class CheckableComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.closeOnLineEditClick = False
        self.view().viewport().installEventFilter(self)
        self.model = QStandardItemModel(self)
        self.setModel(self.model)
        self._placeholder_text = "Виберіть активи..."
        
    def hidePopup(self):
        super().hidePopup()
        self.updateText()

    def setPlaceholderText(self, text):
        self._placeholder_text = text
        self.updateText()

    def updateText(self):
        checked_items = self.checkedItems()
        if not checked_items:
            self.lineEdit().setText(self._placeholder_text)
        else:
            self.lineEdit().setText(", ".join(checked_items))

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.MouseButtonRelease:
            index = self.view().indexAt(event.pos())
            item = self.model.item(index.row())
            if item.checkState() == Qt.CheckState.Checked:
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Checked)
            self.updateText()
            return True
        return super().eventFilter(widget, event)

    def addItem(self, text, data=None, checked=False):
        item = QStandardItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        item.setData(state, Qt.ItemDataRole.CheckStateRole)
        self.model.appendRow(item)
        self.updateText()

    def checkedItems(self):
        checked = []
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked.append(item.text())
        return checked

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
        self.lbl_entry_time = QLabel("Час Входу: -")
        self.lbl_exit_time = QLabel("Час Виходу: -")
        self.lbl_profit = QLabel("Прибуток: -")
        self.lbl_profit.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_duration = QLabel("Тривалість: -")
        
        vbox.addWidget(self.lbl_id)
        vbox.addWidget(self.lbl_dir)
        vbox.addWidget(self.lbl_entry_time)
        vbox.addWidget(self.lbl_exit_time)
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
    def set_trade_details(self, trade_id: str, direction: str, entry_time: str, exit_time: str, profit: float, duration: int, log_text: str):
        self.lbl_id.setText(f"ID: {trade_id}")
        self.lbl_dir.setText(f"Напрям: {direction}")
        self.lbl_entry_time.setText(f"Час Входу: {entry_time}")
        self.lbl_exit_time.setText(f"Час Виходу: {exit_time}")
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
        self.lbl_entry_time.setText("Час Входу: -")
        self.lbl_exit_time.setText("Час Виходу: -")
        self.lbl_profit.setText("Прибуток: -")
        self.lbl_profit.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_duration.setText("Тривалість: -")
        self.txt_log.clear()

from PyQt6.QtCore import pyqtSignal

class SimTradesPanel(QWidget):
    trade_selected = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel("Список Угод")
        self.title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        self.layout.addWidget(self.title)

        from PyQt6.QtWidgets import QAbstractItemView
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Час", "Тип", "Статус", "Профіт"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.layout.addWidget(self.table)
        
        self.trades_data = []
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        
    def _on_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected: return
        row = selected[0].row()
        if row < len(self.trades_data):
            self.trade_selected.emit(self.trades_data[row])

        
    def update_trades(self, trades_list):
        self.trades_data = list(reversed(trades_list))
        self.table.itemSelectionChanged.disconnect(self._on_selection_changed)
        self.table.setRowCount(0)
        for t in reversed(trades_list):
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            time_item = QTableWidgetItem(str(t.get('entry_time', '')))
            type_item = QTableWidgetItem(str(t.get('type', '')))
            status_item = QTableWidgetItem(str(t.get('status', '')))
            
            pnl = t.get('pnl', 0.0)
            pnl_str = f"{pnl:.4f}"
            if pnl > 0: pnl_str = f"+{pnl_str}"
            pnl_item = QTableWidgetItem(pnl_str)
            
            # Color coding
            color = QColor('#A6E3A1') if pnl > 0 else (QColor('#F38BA8') if pnl < 0 else QColor('#CBA6F7'))
            if t.get('status') == 'CLOSED':
                color.setAlpha(100)
            
            for item in (time_item, type_item, status_item, pnl_item):
                item.setBackground(color)
                item.setForeground(QColor('#11111B'))
                
            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, type_item)
            self.table.setItem(row, 2, status_item)
            self.table.setItem(row, 3, pnl_item)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        
    def select_trade_by_time(self, time_str):
        self.table.itemSelectionChanged.disconnect(self._on_selection_changed)
        for i, t in enumerate(self.trades_data):
            if str(t.get('entry_time', '')) == time_str:
                self.table.selectRow(i)
                break
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
