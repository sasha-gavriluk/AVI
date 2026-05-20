from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt6.QtCore import pyqtSignal

# ==================================
# Віджет дерева БД
# ==================================

class DBTreeView(QTreeWidget):
    """Віджет дерева для відображення баз даних та таблиць"""
    
    # Сигнал, який спрацьовує, коли користувач клікає на таблицю
    table_selected = pyqtSignal(str, str) # db_path, table_name
    
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
        
    def populate(self, databases_dict: dict):
        """Метод для заповнення дерева списком баз даних та їхніх таблиць"""
        self.clear()
        
        for db_name, data in databases_dict.items():
            db_path = data.get("path")
            tables = data.get("tables", [])
            
            # Кореневий елемент - База даних
            root_item = QTreeWidgetItem([db_name])
            root_item.setData(0, 32, "database") 
            root_item.setData(0, 34, db_path)
            
            self.addTopLevelItem(root_item)
            
            # Додаємо таблиці як дочірні елементи
            for table in tables:
                table_item = QTreeWidgetItem([table])
                table_item.setData(0, 32, "table")
                table_item.setData(0, 33, table) # Зберігаємо ім'я таблиці
                table_item.setData(0, 34, db_path) # Зберігаємо шлях до БД
                root_item.addChild(table_item)
        
    # ----------------------------------
    # Обробка кліку
    # ----------------------------------
        
    def _on_item_clicked(self, item, column):
        """Метод-обробник кліку по елементу дерева"""
        item_type = item.data(0, 32)
        if item_type == "table":
            table_name = item.data(0, 33)
            db_path = item.data(0, 34)
            self.table_selected.emit(db_path, table_name)
