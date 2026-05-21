from PyQt6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from gui.visual.UiElements import TitleLabel, DbTreeView, DataTableView

#==================================
# TabExplorerVisual
#==================================
class TabExplorerVisual(QWidget):
    # ----------------------------------
    # __init__, ініціалізація вкладки провідника БД
    # ----------------------------------
    # Параметри:
    # parent (QWidget): Батьківський віджет (за замовчуванням None)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    # ----------------------------------
    # init_ui, побудова візуальних елементів
    # ----------------------------------
    # Параметри: немає
    def init_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Ліва панель
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = TitleLabel("Бази даних")
        self.tree_view = DbTreeView()
        
        left_layout.addWidget(title_label)
        left_layout.addWidget(self.tree_view)
        
        # Права панель
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        self.table_view = DataTableView()
        
        right_layout.addLayout(header_layout)
        right_layout.addWidget(self.table_view)
        
        # Пагінація
        pagination_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Попередня")
        self.lbl_page = QLabel("Рядки: 0 - 0")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton("Наступна ▶")
        
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        
        pagination_layout.addWidget(self.btn_prev)
        pagination_layout.addWidget(self.lbl_page, stretch=1)
        pagination_layout.addWidget(self.btn_next)
        
        right_layout.addLayout(pagination_layout)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([200, 800])
        
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)
