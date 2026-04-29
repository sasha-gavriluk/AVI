from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import pyqtSignal

# ==================================
# Віджет дерева БД
# ==================================

class DBTreeView(QTreeWidget):
    """Віджет дерева для відображення баз даних та таблиць"""
    
    # Сигнал, який спрацьовує, коли користувач клікає на таблицю
    table_selected = pyqtSignal(str) 
    
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------
    
    def __init__(self):
        """Метод для ініціалізації віджета дерева"""
        super().__init__()
        self.setHeaderHidden(True)
        self.itemClicked.connect(self._on_item_clicked)
        
    # ----------------------------------
    # Заповнення дерева
    # ----------------------------------
        
    def populate(self, db_name: str, tables: list):
        """Метод для заповнення дерева назвою бази та списком її таблиць"""
        self.clear()
        
        # Кореневий елемент - База даних
        root_item = QTreeWidgetItem([db_name])
        # Можемо зберегти тип елемента у кастомних даних
        root_item.setData(0, 32, "database") 
        
        self.addTopLevelItem(root_item)
        
        # Додаємо таблиці як дочірні елементи
        for table in tables:
            table_item = QTreeWidgetItem([table])
            table_item.setData(0, 32, "table")
            table_item.setData(0, 33, table) # Зберігаємо ім'я таблиці
            root_item.addChild(table_item)
            
        # Розгортаємо дерево
        root_item.setExpanded(True)
        
    # ----------------------------------
    # Обробка кліку
    # ----------------------------------
        
    def _on_item_clicked(self, item, column):
        """Метод-обробник кліку по елементу дерева"""
        item_type = item.data(0, 32)
        if item_type == "table":
            table_name = item.data(0, 33)
            self.table_selected.emit(table_name)
