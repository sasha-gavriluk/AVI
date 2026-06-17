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
        from utils.PathManager import PathManager
        self.config_path = PathManager.get_settings_path()
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
        self.tasks_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.tasks_list.setStyleSheet("background-color: transparent; border: 1px solid #45475A; border-radius: 4px; color: #CDD6F4;")
        tasks_layout.addWidget(self.tasks_list)
        
        tasks_btns = QHBoxLayout()
        self.btn_add_task = QPushButton("+ Задачу")
        self.btn_add_task.setStyleSheet("""
            QPushButton {
                background-color: #89B4FA; 
                color: #11111B; 
                padding: 6px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B4BEFE;
            }
        """)
        
        self.btn_start_task = QPushButton("▶ Старт")
        self.btn_start_task.setStyleSheet("""
            QPushButton {
                background-color: #A6E3A1; 
                color: #11111B; 
                padding: 6px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #94E2D5;
            }
        """)
        
        tasks_btns.addWidget(self.btn_add_task)
        tasks_btns.addWidget(self.btn_start_task)
        tasks_layout.addLayout(tasks_btns)
        
        left_layout.addWidget(tasks_group)
        
        # 1.5 Routine Queue
        routine_group = QGroupBox("🔄 РУТИНА (АВТО)")
        routine_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; padding-top: 15px; color: #A6ADC8; font-weight: bold; }")
        routine_layout = QVBoxLayout(routine_group)
        self.routine_list = QListWidget()
        self.routine_list.setStyleSheet("background-color: transparent; border: 1px solid #45475A; border-radius: 4px; color: #CDD6F4;")
        self.routine_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.routine_list.setFixedHeight(120)
        routine_layout.addWidget(self.routine_list)
        left_layout.addWidget(routine_group)
        
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
            cb.stateChanged.connect(self._update_routine_ui)
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
        
        # All components
        comps_group = QGroupBox()
        comps_group.setStyleSheet("QGroupBox { border: 1px solid #313244; border-radius: 6px; color: #A6ADC8; font-weight: bold; }")
        comps_layout = QVBoxLayout(comps_group)
        comps_layout.setContentsMargins(5, 5, 5, 5)
        
        # Header layout with title and button
        comps_header = QHBoxLayout()
        comps_title = QLabel("🏆 РЕЙТИНГ КОМПОНЕНТІВ")
        comps_title.setStyleSheet("border: none; font-size: 13px;")
        self.btn_expanded = QPushButton("Розширені")
        self.btn_expanded.setCheckable(True)
        self.btn_expanded.setStyleSheet("""
            QPushButton {
                background-color: #45475A; color: #CDD6F4; border-radius: 4px; padding: 2px 8px; font-size: 11px;
            }
            QPushButton:hover {
                background-color: #585B70;
            }
            QPushButton:checked {
                background-color: #89B4FA; color: #11111B; font-weight: bold;
            }
            QPushButton:checked:hover {
                background-color: #B4BEFE;
            }
        """)
        comps_header.addWidget(comps_title)
        comps_header.addStretch()
        comps_header.addWidget(self.btn_expanded)
        comps_layout.addLayout(comps_header)
        
        from PyQt6.QtWidgets import QScrollArea
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.top_inner_widget = QWidget()
        self.top_inner_widget.setStyleSheet("background-color: transparent;")
        self.top_inner = QVBoxLayout(self.top_inner_widget)
        self.top_inner.addStretch()
        
        self.scroll_area.setWidget(self.top_inner_widget)
        comps_layout.addWidget(self.scroll_area)
        
        stats_comp_layout.addWidget(comps_group)
        
        self.btn_expanded.toggled.connect(self._render_components)
        self.last_best_comps = {}
        
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
        self._update_routine_ui()

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
                
            # Log specific toggles
            if self.sender() == self.cb_gen_signals:
                if self.cb_gen_signals.isChecked():
                    self.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] 🔔 Генерація сигналів активована (Тестовий режим).")
                else:
                    self.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] 🔕 Генерація сигналів вимкнена.")
        except Exception as e:
            self.log_console.append(f"Помилка збереження налаштувань: {e}")

    def _update_routine_ui(self):
        is_auto = self.cb_auto_mode.isChecked()
        
        for cb in [self.cb_auto_gen, self.cb_download_ccxt, self.cb_download_massive, self.cb_gen_signals]:
            cb.setEnabled(not is_auto)
            
        if not is_auto:
            has_download = self.cb_download_ccxt.isChecked() or self.cb_download_massive.isChecked()
            self.cb_gen_signals.setEnabled(has_download)
            if not has_download and self.cb_gen_signals.isChecked():
                self.cb_gen_signals.setChecked(False)
                
        self.routine_list.clear()
        
        if is_auto:
            self.routine_list.addItem("1. Аналіз прогалин в БД")
            self.routine_list.addItem("2. Завантаження даних (CCXT / Massive)")
            self.routine_list.addItem("3. Генерація сигналів (Аналіз стратегій)")
            self.routine_list.addItem("4. Відправка звітів у Telegram")
            self.routine_list.addItem("5. Авто-генерація стратегій (Топ-10)")
        else:
            step = 1
            has_download = self.cb_download_ccxt.isChecked() or self.cb_download_massive.isChecked()
            if has_download:
                self.routine_list.addItem(f"{step}. Аналіз прогалин в БД")
                step += 1
                self.routine_list.addItem(f"{step}. Завантаження даних (CCXT / Massive)")
                step += 1
                
            if self.cb_gen_signals.isChecked():
                self.routine_list.addItem(f"{step}. Генерація сигналів (Аналіз стратегій)")
                step += 1
                self.routine_list.addItem(f"{step}. Відправка звітів у Telegram")
                step += 1
                
            if self.cb_auto_gen.isChecked():
                self.routine_list.addItem(f"{step}. Авто-генерація стратегій (Топ-10)")
                step += 1
                
            if step == 1:
                self.routine_list.addItem("Рутина порожня")

    # ----------------------------------
    # update_stats_ui, оновлення UI статистики
    # ----------------------------------
    # Параметри:
    # df: pandas DataFrame
    # best_comps: dict
    def update_stats_ui(self, df, best_comps):
        if df is None:
            import pandas as pd
            df = pd.DataFrame()
            
        if not df.empty:
            wr_avg = df['win_rate'].mean()
            pf_avg = df['profit_factor'].mean()
            records = len(df)
            
            color_wr = "#A6E3A1" if wr_avg >= 50 else "#F38BA8"
            color_pf = "#A6E3A1" if pf_avg >= 1.0 else "#F38BA8"
            
            self.lbl_winrate.setText(f"Win Rate (середній): <span style='color:{color_wr}'>{wr_avg:.1f}%</span>")
            self.lbl_profit_factor.setText(f"Profit Factor: <span style='color:{color_pf}'>{pf_avg:.2f}</span>")
            self.lbl_records.setText(f"Записів у пам'яті: <span style='color:#89B4FA'>{records}</span>")
            
            self.last_best_comps = best_comps
            self._render_components()
        else:
            self.lbl_winrate.setText("Win Rate (середній): <span style='color:#CDD6F4'>--%</span>")
            self.lbl_profit_factor.setText("Profit Factor: <span style='color:#CDD6F4'>--</span>")
            self.lbl_records.setText("Записів у пам'яті: <span style='color:#CDD6F4'>0</span>")

    def _render_components(self):
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
        
        comps_to_render = {}
        if self.btn_expanded.isChecked():
            comps_to_render = self.last_best_comps
        else:
            import re
            for comp, score in self.last_best_comps.items():
                base_name = re.sub(r'_[0-9]+(?:_[0-9]+)*$', '', comp)
                if base_name not in comps_to_render or score > comps_to_render[base_name]:
                    comps_to_render[base_name] = score
            comps_to_render = dict(sorted(comps_to_render.items(), key=lambda x: x[1], reverse=True))

        if comps_to_render:
            colors = ["#A6E3A1", "#89B4FA", "#F9E2AF", "#F38BA8", "#CBA6F7"]
            for i, (comp, score) in enumerate(comps_to_render.items()):
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
