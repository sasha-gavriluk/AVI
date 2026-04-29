from PyQt6.QtWidgets import QMainWindow, QSplitter, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt
import os
import sys

# Додаємо шлях для імпортів
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from gui.duckdb_explorer.views.components.db_tree_view import DBTreeView
from gui.duckdb_explorer.views.components.data_table_view import DataTableView
from gui.duckdb_explorer.logic.db_service import DuckDBService

# ==================================
# Головне вікно провідника DuckDB
# ==================================

class DuckDBExplorerWindow(QMainWindow):
    """Головне вікно застосунку для перегляду баз даних DuckDB"""
    
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------
    
    def __init__(self, default_db_path: str = None):
        """Метод для ініціалізації головного вікна та його компонентів"""
        super().__init__()
        self.setWindowTitle("Провідник DuckDB")
        self.resize(1000, 600)
        
        # Ініціалізуємо сервіс бази даних (логіку)
        self.db_service = DuckDBService()
        
        # Ініціалізуємо компоненти (візуал)
        self.tree_view = DBTreeView()
        self.table_view = DataTableView()
        
        # Стан пагінації
        self.current_table_name = None
        self.current_offset = 0
        self.limit = 1000
        self.current_total_rows = 0
        
        self.setup_ui()
        self.setup_connections()
        
        # Якщо передали шлях до БД - підключаємось одразу
        if default_db_path:
            self.load_database(default_db_path)
            
    # ----------------------------------
    # Налаштування інтерфейсу
    # ----------------------------------
            
    def setup_ui(self):
        """Метод для створення та розміщення всіх віджетів на формі"""
        # Створюємо головний віджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Спліттер для розділення лівої та правої панелі
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Ліва панель
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Бази даних")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        
        left_layout.addWidget(title_label)
        left_layout.addWidget(self.tree_view)
        
        # Права панель (Таблиця + Пагінація)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_layout.addWidget(self.table_view)
        
        # Панель пагінації
        pagination_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Попередня")
        self.lbl_page = QLabel("Рядки: 0 - 0")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton("Наступна ▶")
        
        # Початково вимкнені
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        
        pagination_layout.addWidget(self.btn_prev)
        pagination_layout.addWidget(self.lbl_page, stretch=1)
        pagination_layout.addWidget(self.btn_next)
        
        right_layout.addLayout(pagination_layout)
        
        # Додаємо у спліттер
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # Пропорції спліттера (20% на дерево, 80% на таблицю)
        splitter.setSizes([200, 800])
        
        # Головний лейаут
        main_layout = QVBoxLayout(central_widget)
        main_layout.addWidget(splitter)
        
    # ----------------------------------
    # Налаштування сигналів
    # ----------------------------------
        
    def setup_connections(self):
        """Метод для підключення сигналів кнопок та віджетів до їх обробників"""
        self.tree_view.table_selected.connect(self.on_table_selected)
        self.btn_prev.clicked.connect(self.on_prev_page)
        self.btn_next.clicked.connect(self.on_next_page)
        
    # ----------------------------------
    # Робота з базою даних
    # ----------------------------------
        
    def load_database(self, db_path: str):
        """Метод для завантаження бази даних та наповнення дерева таблиць"""
        self.db_service.connect(db_path)
        tables = self.db_service.get_tables()
        db_name = os.path.basename(db_path)
        self.tree_view.populate(db_name, tables)
        
    # ----------------------------------
    # Обробка кліку по таблиці
    # ----------------------------------
        
    def on_table_selected(self, table_name: str):
        """Метод-обробник події вибору таблиці користувачем"""
        self.current_table_name = table_name
        self.current_offset = 0
        self.current_total_rows = self.db_service.get_table_count(table_name)
        self.load_table_data()
        
    # ----------------------------------
    # Пагінація
    # ----------------------------------
        
    def on_prev_page(self):
        """Метод для переходу на попередню сторінку даних"""
        if self.current_offset >= self.limit:
            self.current_offset -= self.limit
            self.load_table_data()
            
    def on_next_page(self):
        """Метод для переходу на наступну сторінку даних"""
        self.current_offset += self.limit
        self.load_table_data()
        
    # ----------------------------------
    # Завантаження даних
    # ----------------------------------
        
    def load_table_data(self):
        """Метод для запиту даних з бази та оновлення візуальної таблиці та кнопок"""
        if not self.current_table_name:
            return
            
        df = self.db_service.get_table_data(self.current_table_name, limit=self.limit, offset=self.current_offset)
        self.table_view.set_data(df)
        
        # Оновлюємо статус пагінації
        current_rows = len(df)
        start_row = self.current_offset + 1 if current_rows > 0 else 0
        end_row = self.current_offset + current_rows
        self.lbl_page.setText(f"Рядки: {start_row} - {end_row} із {self.current_total_rows}")
        
        # Вмикаємо/вимикаємо кнопки
        self.btn_prev.setEnabled(self.current_offset > 0)
        self.btn_next.setEnabled((self.current_offset + self.limit) < self.current_total_rows)
