import os
from PyQt6.QtWidgets import QStatusBar, QLabel
from PyQt6.QtCore import QTimer, Qt, QTime

class GlobalStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Основний статус
        self.status_label = QLabel("Система: Очікування")
        self.status_label.setMinimumWidth(250)
        
        # Поточна активна БД
        self.db_label = QLabel("БД: Не вибрано")
        self.db_label.setMinimumWidth(150)
        
        # Активна вкладка
        self.tab_label = QLabel("Вкладка: Провідник БД")
        
        # Годинник
        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Додаємо віджети на статус-бар
        self.addWidget(self.status_label)
        self.addWidget(self.db_label)
        
        self.addPermanentWidget(self.tab_label)
        self.addPermanentWidget(self.time_label)
        
        # Таймер для оновлення часу
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
        
    def update_time(self):
        current_time = QTime.currentTime().toString("hh:mm:ss")
        self.time_label.setText(current_time)
            
    def set_status(self, message: str):
        self.status_label.setText(f"Система: {message}")
        
    def set_db(self, db_name: str):
        if not db_name:
            self.db_label.setText("БД: Не вибрано")
        else:
            self.db_label.setText(f"БД: {os.path.basename(db_name)}")
        
    def set_tab(self, tab_name: str):
        self.tab_label.setText(f"Вкладка: {tab_name}")
