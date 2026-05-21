import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTextEdit, QLabel, QGroupBox, QSplitter, QCheckBox, 
                             QListWidget, QProgressBar)
from PyQt6.QtCore import Qt

#==================================
# TabCopilotVisual
#==================================
class TabCopilotVisual(QWidget):
    # ----------------------------------
    # __init__, ініціалізація візуалу Copilot
    # ----------------------------------
    # Параметри:
    # parent: батьківський віджет
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'config', 'settings.json'))
        self.cb_states = self._load_cb_states()
        self.init_ui()

    # ----------------------------------
    # init_ui, побудова інтерфейсу
    # ----------------------------------
    # Параметри: немає
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- HEADER ---
        header_layout = QHBoxLayout()
        title = QLabel("🤖 COPILOT CENTER")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #89B4FA;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        self.btn_active = QPushButton("● ACTIVE")
        self.btn_active.setStyleSheet("""
            QPushButton {
                font-size: 14px; 
                font-weight: bold; 
                color: #11111B; 
                background-color: #A6E3A1; 
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #94E2D5;
            }
        """)
        self.btn_active.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_active)
        
        self.btn_stop = QPushButton("■ STOP")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                font-size: 14px; 
                font-weight: bold; 
                color: #11111B; 
                background-color: #F38BA8; 
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #EBA0AC;
            }
        """)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_stop)
        
        main_layout.addLayout(header_layout)
        
        # --- SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ==========================================
        # LEFT PANEL
        # ==========================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # 1. Tasks Queue
        tasks_group = QGroupBox("📋 ЧЕРГА ЗАДАЧ")
        tasks_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        tasks_layout = QVBoxLayout(tasks_group)
        
        self.tasks_list = QListWidget()
        self.tasks_list.addItems([
            "✅ Аналіз прогалин",
            "🔄 Завантаження",
            "⏳ Генерація x50",
            "⏸ Тестування",
            "⏸ Запис досвіду"
        ])
        self.tasks_list.setStyleSheet("background-color: transparent; border: none; color: #CDD6F4;")
        tasks_layout.addWidget(self.tasks_list)
        
        tasks_btns = QHBoxLayout()
        self.btn_add_task = QPushButton("+ Задачу")
        self.btn_add_task.setStyleSheet("background-color: #45475A; padding: 5px;")
        
        self.btn_start_task = QPushButton("▶ Старт")
        self.btn_start_task.setStyleSheet("background-color: #A6E3A1; color: #11111B; padding: 5px; font-weight: bold;")
        
        tasks_btns.addWidget(self.btn_add_task)
        tasks_btns.addWidget(self.btn_start_task)
        tasks_layout.addLayout(tasks_btns)
        
        left_layout.addWidget(tasks_group)
        
        # 2. Settings
        settings_group = QGroupBox("⚙️ НАЛАШТУВАННЯ")
        settings_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        settings_layout = QVBoxLayout(settings_group)
        
        self.cb_auto_mode = QCheckBox("Авто-режим")
        self.cb_auto_mode.setChecked(self.cb_states.get("cb_auto_mode", True))
        self.cb_auto_gen = QCheckBox("Авто-генерація стратегій")
        self.cb_auto_gen.setChecked(self.cb_states.get("cb_auto_gen", True))
        self.cb_download_ccxt = QCheckBox("Авто-завантаження від CCXT")
        self.cb_download_ccxt.setChecked(self.cb_states.get("cb_download_ccxt", False))
        self.cb_download_massive = QCheckBox("Авто-завантаження від Massive")
        self.cb_download_massive.setChecked(self.cb_states.get("cb_download_massive", True))
        self.cb_gen_signals = QCheckBox("Генерація сигналів")
        self.cb_gen_signals.setChecked(self.cb_states.get("cb_gen_signals", False))
        
        for cb in [self.cb_auto_mode, self.cb_auto_gen, self.cb_download_ccxt, self.cb_download_massive, self.cb_gen_signals]:
            cb.setStyleSheet("color: #CDD6F4;")
            cb.stateChanged.connect(self.save_settings)
            settings_layout.addWidget(cb)
            
        left_layout.addWidget(settings_group)
        left_layout.addStretch()
        
        # ==========================================
        # RIGHT PANEL
        # ==========================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # 3. Stats & Top Components
        stats_comp_layout = QHBoxLayout()
        
        # Stats
        stats_group = QGroupBox("📊 СТАТИСТИКА ДОСВІДУ")
        stats_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        stats_inner = QVBoxLayout(stats_group)
        
        self.lbl_winrate = QLabel("Win Rate (середній): <span style='color:#CDD6F4'>--%</span>")
        self.lbl_profit_factor = QLabel("Profit Factor: <span style='color:#CDD6F4'>--</span>")
        self.lbl_records = QLabel("Записів у пам'яті: <span style='color:#CDD6F4'>--</span>")
        
        stats_inner.addWidget(self.lbl_winrate)
        stats_inner.addWidget(self.lbl_profit_factor)
        stats_inner.addWidget(self.lbl_records)
        stats_inner.addStretch()
        stats_comp_layout.addWidget(stats_group)
        
        # Top components
        top_group = QGroupBox("🏆 ТОП-5 КОМПОНЕНТІВ")
        top_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        self.top_inner = QVBoxLayout(top_group)
        self.top_inner.addStretch() # placeholder
        
        stats_comp_layout.addWidget(top_group)
        
        right_layout.addLayout(stats_comp_layout)
        
        # 4. Logs
        log_group = QGroupBox("📜 ЛОГ ДІЙ КОПІЛОТА")
        log_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        log_layout = QVBoxLayout(log_group)
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("background-color: #11111B; color: #CDD6F4; font-family: 'Consolas'; border: none;")
        self.log_console.append("[00:00:00] Копілот ініціалізований та готовий до роботи.")
        log_layout.addWidget(self.log_console)
        
        right_layout.addWidget(log_group)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 600])
        main_layout.addWidget(splitter)

    # ----------------------------------
    # _load_cb_states, завантаження станів чекбоксів
    # ----------------------------------
    # Параметри: немає
    def _load_cb_states(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("copilot_view", {})
            except Exception:
                pass
        return {}

    # ----------------------------------
    # save_settings, збереження станів чекбоксів
    # ----------------------------------
    # Параметри: немає
    def save_settings(self):
        data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass
                
        data["copilot_view"] = {
            "cb_auto_mode": self.cb_auto_mode.isChecked(),
            "cb_auto_gen": self.cb_auto_gen.isChecked(),
            "cb_download_ccxt": self.cb_download_ccxt.isChecked(),
            "cb_download_massive": self.cb_download_massive.isChecked(),
            "cb_gen_signals": self.cb_gen_signals.isChecked()
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log_console.append(f"Помилка збереження налаштувань: {e}")

    # ----------------------------------
    # update_stats_ui, оновлення UI статистики
    # ----------------------------------
    # Параметри:
    # df: pandas DataFrame
    # best_comps: dict
    def update_stats_ui(self, df, best_comps):
        if not df.empty:
            wr_avg = df['win_rate'].mean()
            pf_avg = df['profit_factor'].mean()
            records = len(df)
            
            color_wr = "#A6E3A1" if wr_avg >= 50 else "#F38BA8"
            color_pf = "#A6E3A1" if pf_avg >= 1.0 else "#F38BA8"
            
            self.lbl_winrate.setText(f"Win Rate (середній): <span style='color:{color_wr}'>{wr_avg:.1f}%</span>")
            self.lbl_profit_factor.setText(f"Profit Factor: <span style='color:{color_pf}'>{pf_avg:.2f}</span>")
            self.lbl_records.setText(f"Записів у пам'яті: <span style='color:#89B4FA'>{records}</span>")
            
            # Очищуємо старі компоненти
            while self.top_inner.count():
                item = self.top_inner.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    while item.layout().count():
                        subitem = item.layout().takeAt(0)
                        if subitem.widget():
                            subitem.widget().deleteLater()
                    item.layout().deleteLater()
            
            if best_comps:
                colors = ["#A6E3A1", "#89B4FA", "#F9E2AF", "#F38BA8", "#CBA6F7"]
                for i, (comp, score) in enumerate(list(best_comps.items())[:5]):
                    row = QHBoxLayout()
                    lbl_name = QLabel(f"{comp:<15}")
                    lbl_name.setStyleSheet("font-size: 12px;")
                    row.addWidget(lbl_name)
                    
                    pb = QProgressBar()
                    val = min(100, int(score * 100))
                    pb.setValue(val)
                    pb.setTextVisible(False)
                    pb.setFixedHeight(8)
                    color = colors[i % len(colors)]
                    pb.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }} QProgressBar {{ border: 1px solid #313244; background: #181825; border-radius: 4px; }}")
                    row.addWidget(pb)
                    
                    lbl_score = QLabel(f"{score:.2f}")
                    lbl_score.setStyleSheet("font-size: 12px; color: #A6ADC8;")
                    row.addWidget(lbl_score)
                    
                    self.top_inner.addLayout(row)
            self.top_inner.addStretch()
        else:
            self.lbl_winrate.setText("Win Rate (середній): <span style='color:#CDD6F4'>--%</span>")
            self.lbl_profit_factor.setText("Profit Factor: <span style='color:#CDD6F4'>--</span>")
            self.lbl_records.setText("Записів у пам'яті: <span style='color:#CDD6F4'>0</span>")
