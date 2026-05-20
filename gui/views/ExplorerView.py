from PyQt6.QtWidgets import QSplitter, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt
import os
import sys

from gui.components.db_tree_view import DBTreeView
from gui.components.data_table_view import DataTableView
from gui.logic.db_service import DuckDBService

# ==================================
# Головне вікно провідника DuckDB
# ==================================

class DuckDBExplorerWindow(QWidget):
    """Головна панель застосунку для перегляду баз даних DuckDB"""
    
    # ----------------------------------
    # Ініціалізація
    # ----------------------------------
    
    def __init__(self, default_db_path: str = None):
        """Метод для ініціалізації панелі та її компонентів"""
        super().__init__()
        
        # Колбеки для перевірки блокування БД
        self.is_db_locked_callback = None
        self.switch_to_downloader_callback = None
        
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
        
        # Завантажуємо всі бази з папки data/db
        self.load_all_databases()
            
    # ----------------------------------
    # Налаштування інтерфейсу
    # ----------------------------------
            
    def setup_ui(self):
        """Метод для створення та розміщення всіх віджетів на формі"""
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
        
        # Панель з кнопкою відкриття
        header_layout = QHBoxLayout()
        header_layout.addStretch()
        self.btn_refresh = QPushButton("🔄 Оновити")
        self.btn_refresh.setStyleSheet("padding: 5px 15px;")
        
        self.btn_disconnect = QPushButton("🔌 Відключитись (Звільнити БД)")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.setStyleSheet("padding: 5px 15px;")
        
        self.btn_clean_db = QPushButton("🧹 Очистити від тестів")
        self.btn_clean_db.setEnabled(False)
        self.btn_clean_db.setStyleSheet("padding: 5px 15px; color: #ff453a; font-weight: bold;")
        
        self.btn_delete_table = QPushButton("🗑 Видалити таблицю")
        self.btn_delete_table.setEnabled(False)
        self.btn_delete_table.setStyleSheet("padding: 5px 15px; color: #ff453a;")
        
        self.btn_open_chart = QPushButton("📈 Відкрити на графіку")
        self.btn_open_chart.setEnabled(False)
        self.btn_open_chart.setStyleSheet("padding: 5px 15px; font-weight: bold;")
        
        header_layout.addWidget(self.btn_refresh)
        header_layout.addWidget(self.btn_disconnect)
        header_layout.addWidget(self.btn_clean_db)
        header_layout.addWidget(self.btn_delete_table)
        header_layout.addWidget(self.btn_open_chart)
        
        right_layout.addLayout(header_layout)
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
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)
        
    # ----------------------------------
    # Налаштування сигналів
    # ----------------------------------
        
    def setup_connections(self):
        """Метод для підключення сигналів кнопок та віджетів до їх обробників"""
        self.tree_view.table_selected.connect(self.on_table_selected)
        self.btn_refresh.clicked.connect(self.load_all_databases)
        self.btn_prev.clicked.connect(self.on_prev_page)
        self.btn_next.clicked.connect(self.on_next_page)
        self.btn_disconnect.clicked.connect(self.on_disconnect)
        self.btn_clean_db.clicked.connect(self.on_clean_db)
        self.btn_delete_table.clicked.connect(self.on_delete_table)
        
    # ----------------------------------
    # Робота з базою даних
    # ----------------------------------
        
    def load_all_databases(self):
        """Метод для сканування папки data/db та наповнення дерева всіма базами"""
        # Зберігаємо поточний стан підключення, щоб не збивати його при скануванні
        active_db_path = self.db_service.current_db_path
        
        db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db'))
        if not os.path.exists(db_dir):
            return
            
        dbs = [f for f in os.listdir(db_dir) if f.endswith('.duckdb')]
        databases_dict = {}
        
        for db in dbs:
            db_path = os.path.join(db_dir, db)
            
            # Якщо база зараз завантажується, уникаємо підключення, щоб не було "database is locked"
            if self.is_db_locked_callback and self.is_db_locked_callback(db_path):
                databases_dict[db] = {
                    "path": db_path,
                    "tables": ["(Завантажується...)"]
                }
                continue

            try:
                # Короткочасне підключення для отримання списку таблиць
                self.db_service.connect(db_path)
                tables = self.db_service.get_tables()
                self.db_service.disconnect() # Одразу відключаємось, щоб не блокувати
                
                databases_dict[db] = {
                    "path": db_path,
                    "tables": tables
                }
            except Exception as e:
                print(f"Не вдалося завантажити таблиці для {db}: {e}")
                
        self.tree_view.populate(databases_dict)
        
        # Відновлюємо підключення, якщо воно було активним
        if active_db_path and os.path.exists(active_db_path):
            self.db_service.connect(active_db_path)
        
    # ----------------------------------
    # Обробка кліку по таблиці
    # ----------------------------------
        
    def on_table_selected(self, db_path: str, table_name: str):
        """Метод-обробник події вибору таблиці користувачем"""
        # Перевірка на блокування БД
        if self.is_db_locked_callback and self.is_db_locked_callback(db_path):
            if self.switch_to_downloader_callback:
                self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nПерегляд тимчасово недоступний.")
            return

        # Якщо ми підключені до іншої бази, перепідключаємось
        if self.db_service.current_db_path != db_path:
            self.db_service.connect(db_path)
            
        self.current_table_name = table_name
        self.current_offset = 0
        self.current_total_rows = self.db_service.get_table_count(table_name)
        self.load_table_data()
        self.btn_open_chart.setEnabled(True)
        self.btn_disconnect.setEnabled(True)
        self.btn_clean_db.setEnabled(True)
        self.btn_delete_table.setEnabled(True)
        
    def on_clean_db(self):
        """Очищає підключену базу від таблиць з результатами тестів (backtest, auto_learn)"""
        db_path = self.db_service.current_db_path
        if not db_path:
            return
            
        if self.is_db_locked_callback and self.is_db_locked_callback(db_path):
            if self.switch_to_downloader_callback:
                self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nОчищення неможливе.")
            return
            
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, 'Підтвердження', 
            'Ви дійсно хочете видалити всі таблиці результатів тестування (backtest_*, auto_learn_*) з цієї бази?\nЦя дія незворотна!', 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        try:
            tables = self.db_service.get_tables()
            drop_count = 0
            for t in tables:
                t_lower = t.lower()
                if "backtest" in t_lower or "auto_learn" in t_lower:
                    self.db_service.execute_query(f'DROP TABLE "{t}"')
                    drop_count += 1
                    
            if drop_count > 0:
                QMessageBox.information(self, "Успіх", f"Видалено {drop_count} таблиць з результатами тестів.")
                self.load_all_databases()
                self.table_view.set_data(None)
                self.current_table_name = None
                self.btn_open_chart.setEnabled(False)
            else:
                QMessageBox.information(self, "Інформація", "Немає таблиць для видалення.")
                
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Помилка при очищенні: {e}")

    def on_delete_table(self):
        """Видаляє обрану таблицю з бази даних"""
        if not self.current_table_name:
            return
            
        db_path = self.db_service.current_db_path
        if db_path and self.is_db_locked_callback and self.is_db_locked_callback(db_path):
            if self.switch_to_downloader_callback:
                self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nВидалення неможливе.")
            return
            
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, 'Підтвердження', 
            f'Ви дійсно хочете безповоротно видалити таблицю "{self.current_table_name}"?\nЦя дія знищить всі дані у ній!', 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        try:
            self.db_service.execute_query(f'DROP TABLE "{self.current_table_name}"')
            QMessageBox.information(self, "Успіх", f"Таблиця {self.current_table_name} успішно видалена.")
            self.load_all_databases()
            self.table_view.set_data(None)
            self.current_table_name = None
            self.btn_open_chart.setEnabled(False)
            self.btn_delete_table.setEnabled(False)
            self.lbl_page.setText("Оберіть іншу таблицю")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Помилка при видаленні: {e}")

    def on_disconnect(self):
        """Відключаємось від БД, щоб звільнити її для бектестера"""
        db_path = self.db_service.current_db_path
        if db_path and self.is_db_locked_callback and self.is_db_locked_callback(db_path):
            if self.switch_to_downloader_callback:
                self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nВідключення або модифікація тимчасово недоступні.")
            return

        self.db_service.disconnect()
        self.table_view.set_data(None)
        self.current_table_name = None
        self.lbl_page.setText("БД Відключена")
        self.btn_open_chart.setEnabled(False)
        self.btn_disconnect.setEnabled(False)
        self.btn_clean_db.setEnabled(False)
        self.btn_delete_table.setEnabled(False)
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        
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
