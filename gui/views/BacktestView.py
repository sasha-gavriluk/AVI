import os
import json
import re
import traceback
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QScrollArea, 
    QGroupBox, QCheckBox, QLabel, QFormLayout, QSpinBox, QDoubleSpinBox, 
    QLineEdit, QPushButton, QTextEdit, QFrame, QFileDialog, QMessageBox, QDialog,
    QComboBox, QListWidget, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from utils.algorithms.backtesting.TradingCopilot import TradingCopilot

# Кастомні віджети введення чисел, які ігнорують прокрутку коліщатка миші,
# щоб запобігти випадковим змінам періодів при скролі сторінки налаштувань
class NonWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class NonWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class BacktestView(QWidget):
    
    # Сигнал для передачі запиту на відображення графіку: db_name, table_name
    request_show_chart = pyqtSignal(str, str)
    
    def __init__(self, meta_config_path: str):
        super().__init__()
        self.meta_config_path = meta_config_path
        self._block_updates = False
        self.meta_data = self._load_meta_data()
        self.param_widgets = {} # Зберігатиме посилання на віджети для зчитування значень
        
        self.copilot = TradingCopilot()
        self.last_run_context = {}
        
        self.setup_ui()
        
    def _load_meta_data(self):
        if not os.path.exists(self.meta_config_path):
            print(f"Попередження: Файл конфігурації {self.meta_config_path} не знайдено.")
            return {"categories": []}
        try:
            with open(self.meta_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Помилка зчитування конфігу: {e}")
            return {"categories": []}

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Головний спліттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- ЛІВА ПАНЕЛЬ (70%) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)  # Відступ справа від роздільника
        
        # Внутрішній спліттер (Верх: Конструктор, Низ: Редактор)
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. Верхня частина (Конструктор зі скролом)
        top_half = QWidget()
        top_layout = QVBoxLayout(top_half)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Конструктор стратегії")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        top_layout.addWidget(title_label)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        # Заповнюємо блоки з JSON по категоріях
        for category in self.meta_data.get("categories", []):
            cat_name = category.get("name", "Інше")
            
            cat_btn = QPushButton(f"▶ {cat_name}")
            
            # Якщо це налаштування копілота, використовуємо фіолетовий колір
            if "Copilot" in cat_name:
                color_main = "#bf5af2"
                color_hover = "#d18ff5"
            else:
                color_main = "#4CAF50"
                color_hover = "#81C784"
                
            cat_btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 16px; 
                    font-weight: bold; 
                    padding-top: 15px; 
                    padding-bottom: 5px;
                    color: {color_main}; 
                    text-align: left;
                    border: none;
                    background: transparent;
                }}
                QPushButton:hover {{
                    color: {color_hover};
                }}
            """)
            self.scroll_layout.addWidget(cat_btn)
            
            cat_container = QWidget()
            cat_layout = QVBoxLayout(cat_container)
            cat_layout.setContentsMargins(10, 0, 0, 0)
            
            for item in category.get("items", []):
                block = self._create_indicator_block(item, cat_name)
                cat_layout.addWidget(block)
                
            self.scroll_layout.addWidget(cat_container)
            cat_container.setVisible(False)
            
            cat_btn.clicked.connect(lambda checked, c=cat_container, b=cat_btn, n=cat_name: self._toggle_category(c, b, n))
            

        self.scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        top_layout.addWidget(scroll_area)
        
        # 2. Нижня частина (Редактор)
        bottom_half = QWidget()
        bottom_layout = QVBoxLayout(bottom_half)
        bottom_layout.setContentsMargins(0, 10, 0, 0)
        
        editor_header = QHBoxLayout()
        editor_title = QLabel("Редактор Стратегії (Rules Engine)")
        editor_title.setStyleSheet("font-weight: bold;")
        editor_header.addWidget(editor_title)
        editor_header.addStretch()
        
        self.btn_save = QPushButton("💾 Зберегти")
        self.btn_load = QPushButton("📂 Відкрити")
        self.btn_info = QPushButton("ℹ️ Довідка")
        
        self.btn_save.clicked.connect(self.save_strategy)
        self.btn_load.clicked.connect(self.load_strategy)
        self.btn_info.clicked.connect(self.show_help_dialog)
        
        editor_header.addWidget(self.btn_info)
        editor_header.addWidget(self.btn_save)
        editor_header.addWidget(self.btn_load)
        
        bottom_layout.addLayout(editor_header)
        
        self.code_editor = QTextEdit()
        self.code_editor.setStyleSheet("font-family: monospace; font-size: 14px; background-color: #1e1e1e; color: #d4d4d4; padding: 10px;")
        
        # Шаблон коду за замовчуванням
        self.default_editor_text = (
            "# --- AUTO-GENERATED VARIABLES (DO NOT EDIT) ---\n"
            "from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy\n"
            "# ----------------------------------------------\n\n"
            "# === ВАША ЛОГІКА ТОРГІВЛІ ===\n"
            "entry = None\n"
            "exit = None\n\n"
            "strategy = Strategy(entry_rule=entry, exit_rule=exit)\n"
        )
        self.code_editor.setText(self.default_editor_text)
        bottom_layout.addWidget(self.code_editor)
        
        # Додаємо половинки у лівий спліттер
        left_splitter.addWidget(top_half)
        left_splitter.addWidget(bottom_half)
        left_splitter.setSizes([600, 400]) # Приблизні пропорції
        left_layout.addWidget(left_splitter)
        
        # --- ПРАВА ПАНЕЛЬ (30%) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)  # Відступ зліва від роздільника
        
        # Блок вибору джерела даних
        data_source_label = QLabel("Джерело даних")
        data_source_label.setStyleSheet("font-weight: bold; padding-top: 8px;")
        right_layout.addWidget(data_source_label)
        
        table_row = QHBoxLayout()
        table_row.addWidget(QLabel("Актив:"))
        self.table_combo = QComboBox()
        table_row.addWidget(self.table_combo, stretch=1)
        right_layout.addLayout(table_row)
        
        name_layout = QHBoxLayout()
        name_label = QLabel("Ім'я тесту:")
        self.test_name_input = QLineEdit()
        self.test_name_input.setPlaceholderText("Залиште пустим для авто-генерації")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.test_name_input)
        right_layout.addLayout(name_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("▶ Розрахувати")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 8px;")
        
        self.btn_show_chart = QPushButton("📈 Відобразити на графіку")
        self.btn_show_chart.setStyleSheet("padding: 8px;")
        self.btn_show_chart.setEnabled(False)
        
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_show_chart)
        right_layout.addLayout(btn_layout)
        
        # --- БЛОК АВТО НАВЧАННЯ ШІ ---
        self.ai_learn_group = QGroupBox("🤖 Авто навчання ШІ")
        self.ai_learn_group.setStyleSheet("""
            QGroupBox { 
                border: 1px solid #bf5af2; 
                border-radius: 5px; 
                margin-top: 15px; 
                padding-top: 15px;
                color: #bf5af2;
                font-weight: bold;
            }
        """)
        ai_learn_layout = QVBoxLayout(self.ai_learn_group)
        
        ai_learn_desc = QLabel("Рандомна генерація унікальних стратегій та їх прогін для накопичення досвіду.")
        ai_learn_desc.setWordWrap(True)
        ai_learn_desc.setStyleSheet("color: #a2a2a6; font-size: 11px;")
        ai_learn_layout.addWidget(ai_learn_desc)
        
        spinbox_layout = QHBoxLayout()
        spinbox_label = QLabel("Кількість генерацій:")
        self.ai_learn_count = QSpinBox()
        self.ai_learn_count.setRange(1, 100000)
        self.ai_learn_count.setValue(1000)
        self.ai_learn_count.setSingleStep(100)
        spinbox_layout.addWidget(spinbox_label)
        spinbox_layout.addWidget(self.ai_learn_count)
        ai_learn_layout.addLayout(spinbox_layout)
        
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Напрямок:")
        self.ai_direction_combo = QComboBox()
        self.ai_direction_combo.addItems(["50/50 (Змішано)", "Тільки BUY", "Тільки SELL"])
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.ai_direction_combo, stretch=1)
        ai_learn_layout.addLayout(dir_layout)
        
        self.btn_auto_learn = QPushButton("🧠 ЗАПУСТИТИ АВТО НАВЧАННЯ")
        self.btn_auto_learn.setStyleSheet("background-color: #bf5af2; color: white; font-weight: bold; padding: 8px;")
        self.btn_auto_learn.clicked.connect(self.on_auto_learn_clicked)
        ai_learn_layout.addWidget(self.btn_auto_learn)
        
        right_layout.addWidget(self.ai_learn_group)
        
        log_label = QLabel("Журнал результатів:")
        log_label.setStyleSheet("font-weight: bold; padding-top: 10px;")
        right_layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Тут відображатимуться деталі розрахунку...")
        right_layout.addWidget(self.log_output)
        
        # Головний спліттер (70 / 30)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 300])
        
        main_layout.addWidget(splitter)
        
        self.btn_run.clicked.connect(self.on_run_clicked)
        self.btn_show_chart.clicked.connect(self.on_show_chart_clicked)
        
        # Завантажуємо бази даних (після створення всіх віджетів)
        self._load_databases()
        
    def _safe_append_html(self, html_content):
        """Вставляє HTML в кінець журналу, не збиваючи виділення тексту користувачем."""
        from PyQt6.QtGui import QTextCursor
        
        # Перевіряємо чи скрол в самому низу
        scrollbar = self.log_output.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        
        # Створюємо копію курсора
        cursor = self.log_output.textCursor()
        # Переміщуємо копію в кінець
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # Вставляємо текст через копію (це не змінить реальний курсор користувача)
        cursor.insertHtml(html_content)
        
        # Якщо до цього ми були в низу, автоматично прокручуємо вниз
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def _load_databases(self):
        # Оновлюємо таблиці для дефолтної бази
        current_table = self.table_combo.currentText()
        self._on_db_changed()
        
        # Відновлюємо вибір активу
        if current_table:
            table_index = self.table_combo.findText(current_table)
            if table_index >= 0:
                self.table_combo.setCurrentIndex(table_index)
            
    def _on_db_changed(self):
        self.table_combo.clear()
            
        from utils.DataBaseManager import DataBaseManager
        try:
            dbm = DataBaseManager(use_default=True)
            tables = dbm.get_all_tables()
            dbm.disconnect()
            
            for t in tables:
                t_lower = t.lower()
                if "backtest" not in t_lower and "auto_learn" not in t_lower and not t.startswith("sqlite_"):
                    self.table_combo.addItem(t)
        except Exception as e:
            self.log_output.append(f"Помилка завантаження таблиць: {e}")
            
    def _toggle_category(self, container, btn, name):
        is_visible = container.isVisible()
        container.setVisible(not is_visible)
        btn.setText(f"▼ {name}" if not is_visible else f"▶ {name}")


    def _create_indicator_block(self, item_meta, cat_name):
        group_box = QGroupBox()
        group_box.setStyleSheet("""
            QGroupBox { 
                border: 1px solid #555; 
                border-radius: 5px; 
                margin-top: 10px; 
                padding-top: 15px;
            }
        """)
        
        layout = QVBoxLayout(group_box)
        
        c_type = item_meta.get("class", "Indicator")
        if c_type == "CopilotSetting":
            title = QLabel(item_meta.get("name", "Unnamed"))
            title.setStyleSheet("font-size: 14px; font-weight: bold; color: #bf5af2;")
            layout.addWidget(title)
            
            cb = QCheckBox()
            cb.setChecked(True)
            cb.hide()
            cb.stateChanged.connect(self.update_editor_code)
        else:
            cb = QCheckBox(item_meta.get("name", "Unnamed"))
            cb.setStyleSheet("font-size: 14px; font-weight: bold;")
            cb.stateChanged.connect(self.update_editor_code) # Підключення синхронізації
            layout.addWidget(cb)
        
        desc = QLabel(item_meta.get("description", ""))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; margin-bottom: 5px;")
        layout.addWidget(desc)
        
        form_layout = QFormLayout()
        widgets_dict = {}
        
        for param in item_meta.get("params", []):
            ptype = param.get("type", "int")
            widget = None
            if ptype == "int":
                widget = NonWheelSpinBox()
                widget.setMinimum(param.get("min", -99999))
                widget.setMaximum(param.get("max", 99999))
                
                default_val = param.get("default", 0)
                if c_type == "CopilotSetting" and hasattr(self, 'copilot'):
                    p_name = param.get("name")
                    if p_name == "half_life_days": default_val = self.copilot.half_life_days
                
                widget.setValue(default_val)
                widget.valueChanged.connect(self.update_editor_code)
            elif ptype == "float":
                widget = NonWheelDoubleSpinBox()
                widget.setMinimum(param.get("min", -99999.0))
                widget.setMaximum(param.get("max", 99999.0))
                widget.setSingleStep(param.get("step", 0.1))
                
                default_val = param.get("default", 0.0)
                if c_type == "CopilotSetting" and hasattr(self, 'copilot'):
                    p_name = param.get("name")
                    if p_name == "update_threshold_weight": default_val = self.copilot.update_threshold_weight
                    elif p_name == "min_score_for_best": default_val = self.copilot.min_score_for_best
                
                widget.setValue(default_val)
                widget.valueChanged.connect(self.update_editor_code)
            else:
                widget = QLineEdit()
                widget.setText(str(param.get("default", "")))
                widget.textChanged.connect(self.update_editor_code)
                
            form_layout.addRow(param.get("label", param.get("name")), widget)
            widgets_dict[param.get("name")] = widget
            
        layout.addLayout(form_layout)
        
        self.param_widgets[item_meta["id"]] = {
            "checkbox": cb,
            "params": widgets_dict,
            "meta": item_meta,
            "category": cat_name
        }
        
        return group_box

    def update_editor_code(self):
        if self._block_updates:
            return
            
        # Формуємо автогенерований блок
        lines = [
            "# --- AUTO-GENERATED VARIABLES (DO NOT EDIT) ---",
            "from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy"
        ]
        
        # Update copilot settings first
        for ind_id, data in self.param_widgets.items():
            meta = data["meta"]
            if meta.get("class") == "CopilotSetting" and hasattr(self, 'copilot') and self.copilot:
                params = data["params"]
                if ind_id == "copilot_time_decay" and "half_life_days" in params:
                    self.copilot.half_life_days = params["half_life_days"].value()
                elif ind_id == "copilot_auto_learn_threshold" and "update_threshold_weight" in params:
                    self.copilot.update_threshold_weight = params["update_threshold_weight"].value()
                elif ind_id == "copilot_best_components_score" and "min_score_for_best" in params:
                    self.copilot.min_score_for_best = params["min_score_for_best"].value()

        has_vars = False
        for ind_id, data in self.param_widgets.items():
            if data["checkbox"].isChecked():
                meta = data["meta"]
                c_type = meta.get("class", "Indicator")
                
                if c_type == "CopilotSetting":
                    continue
                
                has_vars = True
                
                # Читаємо клас з JSON (Indicator / Pattern / Algorithm)
                c_type = meta.get("class", "Indicator")
                
                # Збираємо параметри для суфіксу
                param_vals = []
                for p_name, w in data["params"].items():
                    val = w.value() if hasattr(w, 'value') else w.text()
                    if isinstance(val, float) and val.is_integer():
                        val = int(val)
                    param_vals.append(str(val))
                    
                suffix = "_" + "_".join(param_vals) if param_vals else ""
                var_name = ind_id.lower()
                
                # Формуємо аргумент для конструктора
                if c_type == "Pattern":
                    # CamelCase для патернів: hammer → Hammer, morning_star → Morning_Star
                    arg_name = ind_id.replace("_", " ").title().replace(" ", "_")
                elif c_type == "Algorithm":
                    if ind_id == "ngram" and len(param_vals) > 1:
                        road_val = param_vals[1]
                        arg_name = f"NGRAM_ROAD_{road_val}"
                    else:
                        arg_name = ind_id.upper()
                else:
                    arg_name = ind_id.upper() + suffix
                    
                lines.append(f'{var_name} = {c_type}("{arg_name}")')
                
        if not has_vars:
            lines.append("# (Оберіть індикатори зверху)")
            
        lines.append("# ----------------------------------------------")
        new_header = "\n".join(lines)
        
        current_text = self.code_editor.toPlainText()
        
        # Знаходимо і замінюємо блок за допомогою regex
        pattern = re.compile(r'# --- AUTO-GENERATED VARIABLES \(DO NOT EDIT\) ---.*?# ----------------------------------------------', re.DOTALL)
        
        if pattern.search(current_text):
            new_text = pattern.sub(new_header, current_text)
        else:
            # Якщо користувач випадково видалив шапку, додаємо її на початок
            new_text = new_header + "\n\n" + current_text
            
        # Оновлюємо текст і намагаємось зберегти позицію курсора
        cursor = self.code_editor.textCursor()
        pos = cursor.position()
        
        self.code_editor.setText(new_text)
        
        # Відновлюємо курсор з поправкою на зміну довжини тексту
        diff = len(new_text) - len(current_text)
        new_pos = max(0, pos + diff)
        cursor.setPosition(new_pos)
        self.code_editor.setTextCursor(cursor)

    def save_strategy(self):
        save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'strategies')
        os.makedirs(save_dir, exist_ok=True)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Зберегти стратегію")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Введіть назву стратегії:"))
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("Наприклад: my_super_strategy")
        layout.addWidget(name_input)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Зберегти")
        btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_cancel = QPushButton("Скасувати")
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        def on_save():
            name = name_input.text().strip()
            if not name:
                return
            if not name.endswith(".py"):
                name += ".py"
                
            file_path = os.path.join(save_dir, name)
            text = self.code_editor.toPlainText()
            
            # Збираємо стан UI в JSON для легкого відновлення
            ui_state = {}
            for ind_id, data in self.param_widgets.items():
                if data["checkbox"].isChecked():
                    ui_state[ind_id] = [w.value() if hasattr(w, 'value') else w.text() for w in data["params"].values()]
                    
            state_json = json.dumps(ui_state)
            
            # Зберігаємо файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
                f.write(f"\n\n# UI_STATE_META: {state_json}\n")
                
            self.log_output.append(f"Стратегію збережено: {name}")
            dialog.accept()
            
        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()

    def load_strategy(self):
        load_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'strategies')
        os.makedirs(load_dir, exist_ok=True)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Відкрити стратегію")
        dialog.setMinimumSize(450, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Оберіть файл стратегії (включаючи авто навчання):"))
        
        tree_widget = QTreeWidget()
        tree_widget.setHeaderHidden(True)
        
        # Парсимо файли рекурсивно
        has_files = False
        dir_items = {".": tree_widget.invisibleRootItem()}
        
        for root, dirs, filenames in os.walk(load_dir):
            rel_dir = os.path.relpath(root, load_dir)
            if rel_dir != ".":
                parent_dir = os.path.dirname(rel_dir)
                if not parent_dir:
                    parent_dir = "."
                parent_item = dir_items.get(parent_dir, tree_widget.invisibleRootItem())
                
                dir_item = QTreeWidgetItem(parent_item, [os.path.basename(rel_dir)])
                dir_item.setData(0, Qt.ItemDataRole.UserRole, "dir")
                # Для зручності можемо розгорнути папки за замовчуванням
                # dir_item.setExpanded(True)
                dir_items[rel_dir] = dir_item
                
            for filename in sorted(filenames):
                if filename.endswith('.py') or filename.endswith('.txt'):
                    has_files = True
                    parent_item = dir_items.get(rel_dir, tree_widget.invisibleRootItem())
                    file_item = QTreeWidgetItem(parent_item, [filename])
                    file_item.setData(0, Qt.ItemDataRole.UserRole, "file")
                    # Зберігаємо відносний шлях для завантаження
                    rel_path = filename if rel_dir == "." else os.path.join(rel_dir, filename).replace("\\", "/")
                    file_item.setData(0, Qt.ItemDataRole.UserRole + 1, rel_path)
                    
        if not has_files:
            empty_item = QTreeWidgetItem(tree_widget, ["Немає збережених стратегій"])
            tree_widget.setEnabled(False)
                
        layout.addWidget(tree_widget)
        
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("Завантажити")
        btn_load.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        btn_cancel = QPushButton("Скасувати")
        
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        def on_load():
            selected = tree_widget.currentItem()
            if not selected or not tree_widget.isEnabled():
                return
                
            # Якщо це папка, не робимо нічого (тільки розгортаємо)
            if selected.data(0, Qt.ItemDataRole.UserRole) == "dir":
                selected.setExpanded(not selected.isExpanded())
                return
                
            file_name = selected.data(0, Qt.ItemDataRole.UserRole + 1)
            if not file_name:
                return
                
            file_path = os.path.join(load_dir, file_name)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                    
                # Відновлюємо UI (галочки і повзунки)
                meta_match = re.search(r'# UI_STATE_META: (.*)', text)
                if meta_match:
                    ui_state = json.loads(meta_match.group(1))
                    
                    self._block_updates = True # Блокуємо автооновлення під час зміни галочок
                    
                    # Спочатку знімаємо всі галочки
                    for ind_id, data in self.param_widgets.items():
                        data["checkbox"].setChecked(False)
                        
                    # Відновлюємо потрібні
                    for ind_id, params in ui_state.items():
                        if ind_id in self.param_widgets:
                            data = self.param_widgets[ind_id]
                            data["checkbox"].setChecked(True)
                            
                            for w, val in zip(data["params"].values(), params):
                                if isinstance(w, QSpinBox):
                                    w.setValue(int(float(val)))
                                elif isinstance(w, QDoubleSpinBox):
                                    w.setValue(float(val))
                                else:
                                    w.setText(str(val))
                                    
                    self._block_updates = False
                    
                    # Видаляємо мета-коментар з тексту перед відображенням
                    text = re.sub(r'\n\n# UI_STATE_META: .*', '', text)
                    
                self.code_editor.setText(text.strip() + "\n")
                
                # Примусово синхронізуємо шапку на випадок змін у версіях
                self.update_editor_code()
                
                self.log_output.append(f"Стратегію завантажено: {file_name}")
                dialog.accept()
            except Exception as e:
                self.log_output.append(f"Помилка завантаження: {e}")
                dialog.reject()
                
        btn_load.clicked.connect(on_load)
        tree_widget.itemDoubleClicked.connect(on_load)
        btn_cancel.clicked.connect(dialog.reject)
        
        dialog.exec()

    def show_help_dialog(self):
        from PyQt6.QtGui import QClipboard
        from PyQt6.QtWidgets import QApplication

        dialog = QDialog(self)
        dialog.setWindowTitle("Довідка: Написання Стратегій та ШІ")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("font-size: 14px; background-color: #2b2b2b; color: #e0e0e0; padding: 10px;")
        
        # Генеруємо список всіх доступних індикаторів для ШІ-промпту
        ai_indicators_list = ""
        for cat in self.meta_data.get("categories", []):
            ai_indicators_list += f"\n- {cat.get('name', 'Category')}:\n"
            for item in cat.get("items", []):
                params_desc = []
                for p in item.get("params", []):
                    params_desc.append(f"{p['name']}={p['default']}")
                params_str = ", ".join(params_desc) if params_desc else "no params"
                desc = item.get("description", "").replace("\n", " ")
                ai_indicators_list += f"  * {item.get('id')} (params: {params_str}) - {desc}\n"
        
        # Текст промпту для ШІ (Удосконалений для унікальних стратегій)
        prompt_text = (
            "You are an expert quantitative algorithmic developer.\n"
            "Your task is to generate a UNIQUE and CREATIVE algorithmic trading strategy in Python "
            "for my custom Rules Engine framework.\n\n"
            
            "I want you to randomly select a combination of indicators/patterns/algorithms from the list below, "
            "and create a completely unique trading strategy that has not been overused. Surprise me with a clever combination! "
            "You can use 2 to 4 different indicators/algorithms for your logic.\n\n"
            
            "=== STRICT SYNTAX RULES ===\n"
            "1. You must declare the variables first using Indicator(), Pattern(), or Algorithm() classes.\n"
            "   Example: rsi = Indicator('RSI_14'); sma = Indicator('SMA_20')\n"
            "2. Use ONLY standard Python comparison operators: >, <, >=, <=, ==, !=\n"
            "3. For logical AND, use `&` (NOT `and`). For logical OR, use `|` (NOT `or`).\n"
            "4. CRITICAL: You MUST wrap EVERY single condition in its own parentheses ().\n"
            "   CORRECT:   entry = (rsi < 30) & (sma > close)\n"
            "   INCORRECT: entry = rsi < 30 & sma > close\n"
            "5. For crossovers: variable1.crosses_over(variable2) or variable1.crosses_under(variable2)\n"
            "6. Your output MUST include `entry`, `exit`, and a `strategy` object.\n\n"
            
            "=== WHAT EACH VARIABLE TYPE RETURNS ===\n"
            "- Indicator (e.g. sma, rsi, macd): returns a numeric Series. Compare with numbers or other Indicators.\n"
            "- Pattern (e.g. hammer, engulfing): returns True/False (1-sided) or 1/-1 (2-sided, 1=bullish, -1=bearish).\n"
            "- Algorithm (e.g. order_blocks, market_state_linear): returns 1 (bullish), -1 (bearish), or 0 (neutral).\n\n"
            
            "=== AVAILABLE INDICATORS & ALGORITHMS ===\n"
            f"{ai_indicators_list}\n"
            
            "=== EXAMPLE OUTPUT FORMAT ===\n"
            "from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy\n"
            "sma10 = Indicator('SMA_10')\n"
            "sma50 = Indicator('SMA_50')\n"
            "rsi = Indicator('RSI_14')\n"
            "market = Algorithm('MARKET_STATE_LINEAR')\n\n"
            "entry = (sma10.crosses_over(sma50)) & (market == 1) & (rsi < 70)\n"
            "exit = (sma10.crosses_under(sma50)) | (market == -1)\n"
            "strategy = Strategy(entry_rule=entry, exit_rule=exit)\n\n"
            
            "=== YOUR TURN ===\n"
            "Please generate a unique, logical strategy now. Explain the logic briefly in comments. Output ONLY valid Python code block."
        )
        
        prompt_html = prompt_text.replace("<", "&lt;").replace(">", "&gt;")
        
        # Генеруємо список всіх доступних індикаторів для інтерфейсу
        all_indicators_html = "<ul>"
        for cat in self.meta_data.get("categories", []):
            all_indicators_html += f"<li style='margin-top: 5px;'><b>{cat.get('name', 'Інше')}</b>: "
            items = []
            for item in cat.get("items", []):
                items.append(f"{item.get('name')} (<code>{item.get('id')}</code>)")
            all_indicators_html += ", ".join(items) + "</li>"
        all_indicators_html += "</ul>"

        help_html = f"""
        <h2 style='color: #4CAF50;'>🤖 Генерація унікальних стратегій через ШІ</h2>
        <p>Тепер вам не потрібно вручну обирати індикатори. Ви можете просто попросити ChatGPT або Gemini придумати для вас абсолютно унікальну стратегію!</p>
        
        <div style='background-color: #382c16; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 5px solid #ff9800;'>
            <b style='font-size: 16px;'>💡 Інструкція:</b>
            <ol style='margin-top: 10px; line-height: 1.6;'>
                <li>Натисніть зелену кнопку <b>"📋 Скопіювати промпт для ШІ"</b> внизу цього вікна.</li>
                <li>Відкрийте <b>ChatGPT</b>, <b>Gemini</b> або <b>Claude</b> і просто вставте скопійований текст.</li>
                <li>Промпт вже містить усі правила та всі наявні індикатори нашої системи! ШІ самостійно вибере випадкові індикатори та напише унікальний, повністю сумісний Python-код.</li>
                <li>Скопіюйте код від ШІ, вставте його в наш редактор коду (можете попередньо очистити його повністю) і натисніть <b>"Розрахувати"</b>!</li>
            </ol>
        </div>
        
        <p>Ось текст промпту, який скопіюється в буфер обміну (щоб ви бачили, про що дізнається ШІ):</p>
        <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; white-space: pre-wrap; font-size: 11px;'>{prompt_html}</pre>
        <hr style='border: 1px solid #444; margin: 20px 0;'>
        
        <h2 style='color: #2196F3;'>Для тих, хто пише стратегії вручну</h2>
        
        <h3 style='color: #ff9800;'>1. Довідник усіх доступних індикаторів</h3>
        {all_indicators_html}

        <h3 style='color: #2196F3;'>2. Правила синтаксису</h3>
        <ul style='line-height: 1.5;'>
            <li><b>Математика:</b> Ви можете віднімати, додавати чи множити індикатори:<br>
            <code>candle_size = Indicator("high") - Indicator("low")</code></li>
            <li><b>Об'єднання умов:</b> Використовуйте <code>&amp;</code> (ТА), <code>|</code> (АБО).<br>
            <b style='color: #ff453a;'>КРИТИЧНО ВАЖЛИВО:</b> Завжди беріть кожну окрему умову в дужки! Це специфіка Python.<br>
            <i>Правильно:</i> <code>buy_signal = (hammer == True) &amp; (rsi &lt; 30)</code></li>
            <li><b>Перетин ліній:</b><br>
            <code>golden_cross = sma_10.crosses_over(sma_50)</code></li>
        </ul>

        <h3 style='color: #2196F3;'>3. Приклади стратегій (від простих до просунутих)</h3>
        
        <b>🟢 Рівень 1: Проста (Перетин ковзних середніх)</b>
        <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; font-size: 13px; margin-bottom: 15px;'>
sma_fast = Indicator("SMA_10")
sma_slow = Indicator("SMA_50")
# Вхід: Швидка лінія перетинає повільну знизу вгору
entry = sma_fast.crosses_over(sma_slow)
# Вихід: Зворотний перетин
exit = sma_fast.crosses_under(sma_slow)
strategy = Strategy(entry_rule=entry, exit_rule=exit)
        </pre>

        <b>🟡 Рівень 2: Середня (Осцилятор RSI + MACD)</b>
        <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; font-size: 13px; margin-bottom: 15px;'>
rsi = Indicator("RSI_14")
macd_hist = Indicator("MACD_HIST_12_26_9")
# Вхід: RSI виходить із зони перепроданості (пробиває 30) і MACD росте
entry = (rsi.crosses_over(30)) & (macd_hist > 0)
# Вихід: RSI заходить у зону перекупленості (вище 70)
exit = (rsi > 70)
strategy = Strategy(entry_rule=entry, exit_rule=exit)
        </pre>

        <b>🟠 Рівень 3: Свічкові патерни (Молот + Тренд)</b>
        <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; font-size: 13px; margin-bottom: 15px;'>
hammer = Pattern("Hammer")
market = Algorithm("MARKET_STATE_LINEAR")
# Вхід: З'явився свічковий Молот під час загального висхідного тренду (1)
entry = (hammer == True) & (market == 1)
# Вихід: Алгоритм фіксує зміну тренду на низхідний (-1)
exit = (market == -1)
strategy = Strategy(entry_rule=entry, exit_rule=exit)
        </pre>

        <b>🔴 Рівень 4: Складна (Smart Money Concepts)</b>
        <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; font-size: 13px; margin-bottom: 15px;'>
ob = Algorithm("ORDER_BLOCKS")
bos = Pattern("BoS") # Злам структури
close_price = Indicator("close")
ema = Indicator("EMA_20")
# Вхід: Злам структури (бичий) + відскок від Ордер Блоку + ціна вище EMA
entry = (bos == 1) & (ob == 1) & (close_price > ema)
# Вихід: Формування ведмежого Ордер Блоку
exit = (ob == -1)
strategy = Strategy(entry_rule=entry, exit_rule=exit)
        </pre>

        <b>🟣 Рівень 5: Просунута (Математика волатильності)</b>
        <pre style='background-color: #1e1e1e; color: #d4d4d4; padding: 10px; border-radius: 5px; font-size: 13px;'>
bb_upper = Indicator("BB_UPPER_20_2")
bb_lower = Indicator("BB_LOWER_20_2")
atr = Indicator("ATR_14")
close_price = Indicator("close")

# Самостійно вираховуємо ширину каналу
bb_width = bb_upper - bb_lower

# Вхід: Канал вужчий за поточний ATR (флет), але ціна різко пробиває верхню межу
entry = (bb_width < atr) & (close_price.crosses_over(bb_upper))
# Вихід: Ціна падає нижче центральної лінії каналу
exit = close_price < (bb_lower + (bb_width / 2))
strategy = Strategy(entry_rule=entry, exit_rule=exit)
        </pre>
        """
        
        text_edit.setHtml(help_html)
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("📋 Скопіювати промпт для ШІ")
        copy_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 8px;")
        
        def copy_prompt():
            clipboard = QApplication.clipboard()
            clipboard.setText(prompt_text)
            copy_btn.setText("✅ Промпт скопійовано!")
            
        copy_btn.clicked.connect(copy_prompt)
        btn_layout.addWidget(copy_btn)
        
        close_btn = QPushButton("Закрити")
        close_btn.setStyleSheet("padding: 8px;")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def on_run_clicked(self):
        self.log_output.clear()
        start_html = f"""
        <div style='font-family: monospace; font-size: 13px; line-height: 1.4; margin-bottom: 10px;'>
            <p style='color: #0a84ff; font-weight: bold; margin-bottom: 5px;'>🚀 ЗАПУСК БЕКТЕСТУ</p>
            <hr style='border: 0; border-top: 1px solid #444; margin-top: 2px; margin-bottom: 8px;'/>
        </div>
        """
        self._safe_append_html(start_html)
        
        # Перевіряємо вибір джерела даних
        db_name = "main.duckdb"
        table_name = self.table_combo.currentText()
        
        if not db_name or not table_name:
            self._safe_append_html("<div style='color: #ff453a; font-family: monospace; font-weight: bold;'>❗ Оберіть Базу даних та Актив в блоці 'Джерело даних'!</div><br>")
            return
            
        # Перевіряємо наявність об'єкту strategy в коді
        code = self.code_editor.toPlainText()
        if "strategy = Strategy(" not in code:
            self._safe_append_html("<div style='color: #ff453a; font-family: monospace; font-weight: bold;'>❗ У коді редактора відсутній об'єкт Strategy!<br>Додайте рядок: strategy = Strategy(entry_rule=entry, exit_rule=exit)</div><br>")
            return
            
        try:
            # Оновлюємо шлях до бази для копілота (тепер використовується єдина база)
            self.copilot.db_path = "main.duckdb"
            
            report = self.copilot.analyze(code)
            self._display_audit_report(report)
            
            # -- ІНТЕГРАЦІЯ COPILOT --
            indicators_used = [details['arg'] for var, details in report["variables"].items()]
            
            # Збираємо контекст
            # Витягуємо таймфрейм з назви таблиці (наприклад, EURUSD_15m -> 15m)
            tf = table_name.split("_")[-1] if "_" in table_name else "1h"
            context = {
                "asset": table_name,
                "timeframe": tf,
                "period_start": "Невідомо",
                "period_end": "Невідомо"
            }
            
            # Прогнозуємо шанс
            prediction = self.copilot.predict_success_chance(context["asset"], context["timeframe"], indicators_used)
            self._display_copilot_prediction(prediction)
            
            # Зберігаємо для запису після бектесту
            self.last_run_context = {
                "context": context,
                "indicators": indicators_used,
                "logic_snapshot": report.get("logic_snapshot", {})
            }
            
        except Exception as e:
            self._safe_append_html(f"<div style='color: #ff9f0a; font-family: monospace;'>⚠️ Не вдалося виконати аудит стратегії: {e}</div><br>")
        
        # Отримуємо шлях до БД
        db_path = "main.duckdb"
        
        # Генеруємо назву таблиці результатів з обов'язковим префіксом активу
        user_test_name = self.test_name_input.text().strip()
        if not user_test_name:
            import time
            user_test_name = f"test_{int(time.time())}"
            self.test_name_input.setText(user_test_name)
            
        test_name = f"backtest_{table_name}_{user_test_name}"
        
        # Вимикаємо кнопку на час роботи
        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Розраховується...")
        self.btn_show_chart.setEnabled(False)
        
        params_html = f"""
        <div style='font-family: monospace; font-size: 13px; color: #e5e5ea; background-color: #1e1e1e; padding: 8px; border-radius: 5px; margin-bottom: 10px;'>
            <span style='color: #8e8e93;'>БД:</span> <span style='color: #30d158; font-weight: bold;'>{db_name}</span><br>
            <span style='color: #8e8e93;'>Актив:</span> <span style='color: #64d2ff; font-weight: bold;'>{table_name}</span><br>
            <span style='color: #8e8e93;'>Назва тесту:</span> <span style='color: #ffd60a; font-weight: bold;'>{test_name}</span>
        </div>
        """
        self._safe_append_html(params_html)
        self._safe_append_html("<div style='color: #8e8e93; font-style: italic; font-family: monospace; margin-bottom: 5px;'>⚙️ Збирання стратегії...</div><br>")
        # self.log_output.ensureCursorVisible()
        
        # Запускаємо в потоці
        self._worker = BacktestWorker(code, db_path, table_name, test_name)
        self._worker.log_message.connect(self._on_log_message)
        self._worker.finished_ok.connect(self._on_backtest_done)
        self._worker.finished_error.connect(self._on_backtest_error)
        self._worker.start()
        
    @pyqtSlot(str)
    def _on_log_message(self, msg):
        self._safe_append_html(f"<div style='color: #e5e5ea; font-family: monospace; font-size: 13px;'>{msg}</div><br>")
        # self.log_output.ensureCursorVisible()
        
    @pyqtSlot(str)
    def _on_backtest_done(self, table_name):
        done_html = f"""
        <div style='font-family: monospace; font-size: 13px; margin-top: 15px; margin-bottom: 10px;'>
            <hr style='border: 0; border-top: 1px solid #444; margin-bottom: 8px;'/>
            <span style='color: #32d74b; font-weight: bold;'>✅ Бектест завершено!</span><br>
            <span style='color: #8e8e93;'>Результати збережено в таблицю:</span> <span style='color: #64d2ff; font-weight: bold;'>{table_name}</span>
        </div>
        """
        self._safe_append_html(done_html)
        # self.log_output.ensureCursorVisible()
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶ Розрахувати")
        self.last_table_name = table_name
        self.btn_show_chart.setEnabled(True)
        
        # -- ЗАПИСУЄМО РЕЗУЛЬТАТ В ПАМ'ЯТЬ COPILOT --
        if hasattr(self, "last_run_context") and self.last_run_context:
            try:
                # TODO: Отримати реальний WinRate та ProfitFactor з БД
                mock_performance = {"win_rate": 50.0, "profit_factor": 1.0}
                note = f"Автоматичний запис після тесту на {table_name}"
                
                self.copilot.record_backtest_result(
                    context=self.last_run_context["context"],
                    indicators=self.last_run_context["indicators"],
                    performance=mock_performance,
                    note=note,
                    logic_snapshot=self.last_run_context.get("logic_snapshot", {})
                )
                html_msg = "<div style='font-family: monospace; font-size: 13px; color: #bf5af2; font-style: italic; margin-top: 10px; margin-bottom: 10px;'>🤖 Копілот: Результати тесту успішно збережено в мою пам'ять.</div>"
                self._safe_append_html(html_msg)
                # self.log_output.ensureCursorVisible()
            except Exception as e:
                self._safe_append_html(f"<div style='font-family: monospace; font-size: 13px; color: #ff453a; margin-top: 10px; margin-bottom: 10px;'>⚠️ Копілот: Не вдалося зберегти пам'ять: {e}</div>")
                # self.log_output.ensureCursorVisible()
        
    @pyqtSlot(str)
    def _on_backtest_error(self, error_msg):
        err_html = f"""
        <div style='font-family: monospace; font-size: 13px; margin-top: 15px; margin-bottom: 10px;'>
            <hr style='border: 0; border-top: 1px solid #ff453a; margin-bottom: 8px;'/>
            <span style='color: #ff453a; font-weight: bold;'>❌ Помилка бектесту:</span><br>
            <pre style='color: #ff9f0a; background-color: #1e1e1e; padding: 8px; border-radius: 4px; white-space: pre-wrap;'>{error_msg}</pre>
        </div>
        """
        self._safe_append_html(err_html)
        # self.log_output.ensureCursorVisible()
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶ Розрахувати")

    def _display_copilot_prediction(self, prediction: dict):
        html = []
        html.append("<div style='font-family: monospace; font-size: 13px; line-height: 1.4; margin-top: 10px; margin-bottom: 10px;'>")
        html.append("<p style='color: #bf5af2; font-weight: bold; margin-bottom: 5px;'>🤖 ШІ-КОНСУЛЬТАНТ (Прогноз успіху)</p>")
        html.append("<hr style='border: 0; border-top: 1px dashed #bf5af2; margin-top: 2px; margin-bottom: 8px;'/>")
        
        status = prediction.get("status")
        
        if status == "empty":
            html.append(f"<div style='color: #8e8e93;'>{prediction['message']}</div>")
        elif status == "exact_match":
            html.append("<div style='border-left: 3px solid #30d158; padding-left: 8px;'>")
            html.append("<span style='color: #30d158; font-weight: bold;'>🎯 ТОЧНИЙ ЗБІГ ІСТОРІЇ (Актив + Таймфрейм + Індикатори)</span><br/>")
            html.append(f"<span style='color: #e5e5ea;'>Очікуваний Win Rate:</span> <span style='color: #32d74b; font-weight: bold;'>~{prediction['win_rate']:.1f}%</span><br/>")
            html.append(f"<span style='color: #e5e5ea;'>Очікуваний Profit Factor:</span> <span style='color: #32d74b; font-weight: bold;'>{prediction['profit_factor']:.2f}</span><br/>")
            if prediction.get("note"):
                html.append(f"<span style='color: #ff9f0a;'>📝 Замітка:</span> <span style='color: #ffd60a; font-style: italic;'>{prediction['note']}</span><br/>")
            html.append("</div>")
        elif status == "general_match":
            html.append("<div style='border-left: 3px solid #ff9f0a; padding-left: 8px;'>")
            html.append("<span style='color: #ff9f0a; font-weight: bold;'>📊 ЧАСТКОВИЙ ЗБІГ (Схожі стратегії на інших ринках)</span><br/>")
            html.append(f"<span style='color: #e5e5ea;'>Історичний Win Rate:</span> <span style='color: #ffd60a; font-weight: bold;'>~{prediction['win_rate']:.1f}%</span><br/>")
            html.append("<span style='color: #8e8e93; font-style: italic;'>💡 Порада: Протестуйте обережно, оскільки на поточному активі досвіду ще немає.</span><br/>")
            html.append("</div>")
        elif status == "new":
            html.append("<div style='border-left: 3px solid #64d2ff; padding-left: 8px;'>")
            html.append(f"<span style='color: #64d2ff; font-weight: bold;'>✨ {prediction['message']}</span><br/>")
            html.append("</div>")
            
        html.append("<hr style='border: 0; border-top: 1px dashed #bf5af2; margin-top: 10px; margin-bottom: 12px;'/>")
        html.append("</div>")
        
        self._safe_append_html("".join(html))
        # self.log_output.ensureCursorVisible()

    def on_show_chart_clicked(self):
        db_name = "main.duckdb"
        if not db_name:
            self.log_output.append("Помилка: не обрано базу даних!")
            return
            
        table = getattr(self, "last_table_name", None)
        if not table:
            self.log_output.append("Спочатку потрібно запустити бектест!")
            return
            
        self.log_output.append(f"Передача запиту на графік для {table}...")
        self.request_show_chart.emit(db_name, table)

    def on_auto_learn_clicked(self):
        if hasattr(self, "_auto_worker") and self._auto_worker.isRunning():
            self._auto_worker.stop()
            self.btn_auto_learn.setText("🛑 ЗУПИНКА...")
            self.btn_auto_learn.setEnabled(False)
            return
            
        db_path = "main.duckdb"
        table_name = self.table_combo.currentText()
        
        if not db_path or not table_name:
            self._safe_append_html("<div style='color: #ff453a; font-family: monospace; font-weight: bold;'>❗ Оберіть Базу даних та Актив!</div><br>")
            return
            
        self.log_output.clear()
        self._safe_append_html(f"<div style='color: #bf5af2; font-weight: bold;'>🚀 ЗАПУСК АВТО НАВЧАННЯ ШІ ({self.ai_learn_count.value()} генерацій)...</div><br>")
        
        self.btn_auto_learn.setText("🛑 ЗУПИНИТИ АВТО НАВЧАННЯ")
        self.btn_auto_learn.setStyleSheet("background-color: #ff453a; color: white; font-weight: bold; padding: 8px;")
        
        count = self.ai_learn_count.value()
        
        direction_text = self.ai_direction_combo.currentText()
        if "BUY" in direction_text:
            direction_mode = "BUY"
        elif "SELL" in direction_text:
            direction_mode = "SELL"
        else:
            direction_mode = "MIXED"
            
        self._auto_worker = AutoLearnWorker(db_path, table_name, self.meta_data, total_runs=count, direction_mode=direction_mode)
        self._auto_worker.log_message.connect(self._on_log_message)
        
        def on_finished():
            self.btn_auto_learn.setText("🧠 ЗАПУСТИТИ АВТО НАВЧАННЯ")
            self.btn_auto_learn.setStyleSheet("background-color: #bf5af2; color: white; font-weight: bold; padding: 8px;")
            self.btn_auto_learn.setEnabled(True)
            self._safe_append_html("<div style='color: #32d74b; font-weight: bold;'><br>✅ АВТО НАВЧАННЯ ЗАВЕРШЕНО!</div><br>")
            # self.log_output.ensureCursorVisible()
            
        self._auto_worker.finished.connect(on_finished)
        self._auto_worker.start()

    def _display_audit_report(self, report):
        # Використовуємо HTML для розфарбування виводу в QTextEdit
        html = []
        html.append("<div style='font-family: monospace; font-size: 13px; line-height: 1.4;'>")
        
        # Заголовок аудиту
        html.append("<p style='color: #5ac8fa; font-weight: bold; margin-bottom: 5px;'>🔍 ІНТЕЛЕКТУАЛЬНИЙ АУДИТ СТРАТЕГІЇ</p>")
        html.append("<hr style='border: 0; border-top: 1px solid #444; margin-top: 2px; margin-bottom: 8px;'/>")
        
        # Зчитуємо змінні
        if report["variables"]:
            html.append("<p style='color: #8e8e93; font-weight: bold; margin-top: 5px; margin-bottom: 2px;'>📊 Зчитані індикатори:</p>")
            for var, details in report["variables"].items():
                html.append(f"&nbsp;&nbsp;<span style='color: #64d2ff; font-weight: bold;'>{var}</span> &rarr; {details['class']} (<span style='text-decoration: underline;'>{details['arg']}</span>)<br/>")
            html.append("<br/>")
            
        # Помилки (DANGER)
        dangers = [w for w in report["warnings"] if w["severity"] == "DANGER"]
        if dangers:
            html.append("<p style='color: #ff453a; font-weight: bold; margin-top: 10px; margin-bottom: 5px;'>🔴 КРИТИЧНІ ПОМИЛКИ:</p>")
            for d in dangers:
                msg = d['message'].replace('<', '&lt;').replace('>', '&gt;')
                expl = d['explanation'].replace('<', '&lt;').replace('>', '&gt;')
                html.append(f"<div style='border-left: 3px solid #ff453a; padding-left: 8px; margin-bottom: 8px;'>")
                html.append(f"&nbsp;&nbsp;<span style='color: #ff453a; font-weight: bold;'>❌ {msg}</span><br/>")
                html.append(f"&nbsp;&nbsp;<span style='color: #ff9f0a;'>Пояснення:</span> {expl}<br/>")
                html.append("</div>")
                
        # Попередження (WARNING)
        warnings = [w for w in report["warnings"] if w["severity"] == "WARNING"]
        if warnings:
            html.append("<p style='color: #ff9f0a; font-weight: bold; margin-top: 10px; margin-bottom: 5px;'>🟡 ПОПЕРЕДЖЕННЯ ТА КОНФЛІКТИ:</p>")
            for w in warnings:
                msg = w['message'].replace('<', '&lt;').replace('>', '&gt;')
                expl = w['explanation'].replace('<', '&lt;').replace('>', '&gt;')
                html.append(f"<div style='border-left: 3px solid #ff9f0a; padding-left: 8px; margin-bottom: 8px;'>")
                html.append(f"&nbsp;&nbsp;<span style='color: #ffb340; font-weight: bold;'>⚠️ {msg}</span><br/>")
                html.append(f"&nbsp;&nbsp;<span style='color: #64d2ff;'>Пояснення:</span> {expl}<br/>")
                html.append("</div>")
                
        # Інфо зауваження (INFO)
        infos = [w for w in report["warnings"] if w["severity"] == "INFO"]
        if infos:
            html.append("<p style='color: #0a84ff; font-weight: bold; margin-top: 10px; margin-bottom: 5px;'>🔵 НАДМІРНІСТЬ ТА СТРУКТУРА:</p>")
            for i in infos:
                msg = i['message'].replace('<', '&lt;').replace('>', '&gt;')
                expl = i['explanation'].replace('<', '&lt;').replace('>', '&gt;')
                html.append(f"<div style='border-left: 3px solid #0a84ff; padding-left: 8px; margin-bottom: 8px;'>")
                html.append(f"&nbsp;&nbsp;<span style='color: #64d2ff; font-weight: bold;'>ℹ️ {msg}</span><br/>")
                html.append(f"&nbsp;&nbsp;<span style='color: #a2a2a6;'>Пояснення:</span> {expl}<br/>")
                html.append("</div>")
                
        # Поради (suggestions)
        if report["suggestions"]:
            html.append("<p style='color: #30d158; font-weight: bold; margin-top: 10px; margin-bottom: 5px;'>💡 РЕКОМЕНДАЦІЇ АНАЛІТИКА:</p>")
            for s in report["suggestions"]:
                s_esc = s.replace('<', '&lt;').replace('>', '&gt;')
                html.append(f"&nbsp;&nbsp;<span style='color: #30d158;'>💡 {s_esc}</span><br/>")
                
        # Аналіз історичного досвіду (experience_summary)
        if report.get("experience_summary"):
            html.append("<p style='color: #bf5af2; font-weight: bold; margin-top: 15px; margin-bottom: 5px;'>🧠 ПАМ'ЯТЬ БЕКТЕСТІВ (Детальний досвід):</p>")
            exp_text = report["experience_summary"].replace('<', '&lt;').replace('>', '&gt;').replace("\n", "<br/>&nbsp;&nbsp;")
            html.append(f"<div style='border-left: 3px solid #bf5af2; padding-left: 8px; margin-bottom: 8px; color: #e5e5ea;'>")
            html.append(f"&nbsp;&nbsp;{exp_text}<br/>")
            html.append("</div>")

        if not dangers and not warnings and not infos and not report["suggestions"]:
            html.append("<p style='color: #30d158; font-weight: bold;'>✅ Стратегія пройшла повний аудит без жодних зауважень! Ідеальна структура.</p>")
            
        html.append("<hr style='border: 0; border-top: 1px solid #444; margin-top: 12px; margin-bottom: 12px;'/>")
        html.append("</div>")
        
        # Додаємо HTML до логу
        self._safe_append_html("".join(html))
        # Зсуваємо курсор вниз
        # self.log_output.ensureCursorVisible()


# ============================================================
# Фоновий потік для виконання бектесту
# ============================================================

class BacktestWorker(QThread):
    """Виконує бектест в окремому потоці, щоб GUI не завис"""
    
    log_message = pyqtSignal(str)
    finished_ok = pyqtSignal(str)   # передає назву таблиці з результатами
    finished_error = pyqtSignal(str) # передає повідомлення про помилку
    

    def __init__(self, code: str, db_path: str, table_name: str, result_table: str):
        super().__init__()
        self.code = code
        self.db_path = db_path
        self.table_name = table_name
        self.result_table = result_table
    
    def run(self):
        import io, sys
        try:
            from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy
            from utils.algorithms.backtesting.MarketRunner import MarketRunner
            
            # Отримуємо тільки ім'я файлу БД (без шляху)
            db_name = os.path.basename(self.db_path)
            
            # Виконуємо код з редактора в ізольованому середовищі
            local_ns = {
                "Indicator": Indicator,
                "Pattern": Pattern,
                "Algorithm": Algorithm,
                "Strategy": Strategy,
            }
            
            self.log_message.emit("Виконую код стратегії...")
            exec(self.code, local_ns)
            
            strategy = local_ns.get("strategy")
            if strategy is None:
                self.finished_error.emit("Об'єкт 'strategy' не було створено після exec().\nПеревірте рядок: strategy = Strategy(...)")
                return
            
            self.log_message.emit(f"Стратегію створено. Запускаю MarketRunner...")
            self.log_message.emit(f"Таблиця з даними: '{self.table_name}'")
            
            # Запускаємо MarketRunner
            runner = MarketRunner(
                strategy=strategy,
                db_path=db_name,
                db_table_path=self.table_name,
            )
            
            # Перехоплюємо stdout, щоб перехопити print() виведення MarketRunner
            old_stdout = sys.stdout
            sys.stdout = StringCapture(self.log_message)
            try:
                trades_df = runner.run(self.result_table)
                
                # Додаємо детальну статистику в лог
                total_trades = len(trades_df) if trades_df is not None else 0
                if total_trades > 0:
                    winning_trades = len(trades_df[trades_df['Profit'] > 0])
                    win_rate = (winning_trades / total_trades) * 100.0
                    
                    gross_profit = trades_df[trades_df['Profit'] > 0]['Profit'].sum()
                    gross_loss = abs(trades_df[trades_df['Profit'] < 0]['Profit'].sum())
                    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
                    total_profit = trades_df['Profit'].sum()
                    
                    self.log_message.emit(f"<br><span style='color: #32d74b; font-weight: bold;'>📊 ПІДСУМОК БЕКТЕСТУ:</span>")
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Всього угод: <b>{total_trades}</b></span>")
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Успішних: <b>{winning_trades} ({win_rate:.1f}%)</b></span>")
                    profit_color = "#32d74b" if total_profit >= 0 else "#ff453a"
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Чистий прибуток: <b style='color: {profit_color};'>{total_profit:.2f}</b></span>")
                    self.log_message.emit(f"<span style='color: #e5e5ea;'>&nbsp;&nbsp;• Profit Factor: <b>{profit_factor:.2f}</b></span><br>")
                else:
                    self.log_message.emit(f"<br><span style='color: #ff9f0a; font-weight: bold;'>📊 ПІДСУМОК БЕКТЕСТУ:</span> <span style='color: #e5e5ea;'>Угод не знайдено.</span><br>")
                    
            finally:
                sys.stdout = old_stdout
            
            self.finished_ok.emit(self.result_table)
            
        except Exception as e:
            self.finished_error.emit(traceback.format_exc())


class StringCapture:
    """Перехоплює sys.stdout, передаючи рядки в Qt-сигнал"""
    def __init__(self, signal):
        self.signal = signal
    def write(self, text):
        stripped = text.strip()
        if stripped:
            self.signal.emit(stripped)
    def flush(self):
        pass

class AutoLearnWorker(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    finished = pyqtSignal()
    
    def __init__(self, db_path, table_name, meta_data, total_runs=1000, direction_mode="MIXED"):
        super().__init__()
        self.db_path = db_path
        self.table_name = table_name
        self.meta_data = meta_data
        self.total_runs = total_runs
        self.direction_mode = direction_mode
        self.is_running = True
        
    def run(self):
        try:
            import random
            from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy
            from utils.algorithms.backtesting.MarketRunner import MarketRunner
            from utils.algorithms.backtesting.TradingCopilot import TradingCopilot
            import time
            import os
            import json
            import shutil
            
            copilot = TradingCopilot(db_path=self.db_path)
            current_run_results = []
            db_name = os.path.basename(self.db_path)
            
            all_items = []
            for cat in self.meta_data.get("categories", []):
                all_items.extend(cat.get("items", []))
                
            if not all_items:
                self.log_message.emit("Помилка: Немає доступних індикаторів.")
                return
                
            total_runs = self.total_runs
            for i in range(total_runs):
                if not self.is_running:
                    break
                    
                self.log_message.emit(f"<br><b>--- Генерація стратегії {i+1}/{total_runs} ---</b>")
                
                from utils.algorithms.backtesting.StrategyGenerator import StrategyGenerator
                generator = StrategyGenerator(copilot=copilot)
                
                if self.direction_mode == "MIXED":
                    direction = random.choice(["BUY", "SELL"])
                else:
                    direction = self.direction_mode
                    
                code_str = generator.generate(direction=direction)
                
                if code_str.startswith("# Помилка"):
                    self.log_message.emit(f"Пропуск: {code_str}")
                    continue
                    
                local_ns = {
                    "Indicator": Indicator,
                    "Pattern": Pattern,
                    "Algorithm": Algorithm,
                    "Strategy": Strategy,
                }
                
                try:
                    exec(code_str, local_ns)
                    strategy = local_ns.get("strategy")
                except Exception as e:
                    self.log_message.emit(f"Помилка генерації коду: {e}")
                    continue
                    
                # Аналізуємо код, щоб дістати logic_snapshot та індикатори
                report = copilot.analyze(code_str)
                indicators_used = [details['arg'] for var, details in report.get("variables", {}).items() if details.get('arg')]
                logic_snapshot = report.get("logic_snapshot", {})
                
                test_name = f"auto_learn_{int(time.time())}_{i}"
                
                # Зберігаємо код стратегії у файл
                save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'strategies', 'auto_learn')
                os.makedirs(save_dir, exist_ok=True)
                file_path = os.path.join(save_dir, f"{test_name}.py")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(code_str)
                
                runner = MarketRunner(
                    strategy=strategy,
                    db_path=db_name,
                    db_table_path=self.table_name,
                )
                
                # Приглушуємо стандартний вивід
                import sys
                old_stdout = sys.stdout
                from io import StringIO
                sys.stdout = StringIO()
                
                try:
                    trades_df = runner.run(test_name)
                    sys.stdout = old_stdout
                    
                    # Розрахунок реальної статистики
                    total_trades = len(trades_df) if trades_df is not None else 0
                    if total_trades > 0:
                        winning_trades = len(trades_df[trades_df['Profit'] > 0])
                        win_rate = (winning_trades / total_trades) * 100.0
                        
                        gross_profit = trades_df[trades_df['Profit'] > 0]['Profit'].sum()
                        gross_loss = abs(trades_df[trades_df['Profit'] < 0]['Profit'].sum())
                        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
                    else:
                        win_rate = 0.0
                        profit_factor = 0.0
                        
                    perf = {"win_rate": win_rate, "profit_factor": profit_factor, "total_trades": total_trades}
                    
                    tf = self.table_name.split("_")[-1] if "_" in self.table_name else "1h"
                    copilot.record_backtest_result(
                        context={"asset": self.table_name, "timeframe": tf},
                        indicators=indicators_used,
                        performance=perf,
                        note=f"Авто навчання {i+1}/{total_runs} [{direction}]",
                        logic_snapshot=logic_snapshot
                    )
                    
                    self.log_message.emit(f"✅ Успіх. Угод: {total_trades}, PF: {profit_factor:.2f}, WR: {win_rate:.1f}%")
                    current_run_results.append({
                        "name": test_name,
                        "path": file_path,
                        "profit_factor": profit_factor,
                        "win_rate": win_rate,
                        "total_trades": total_trades
                    })
                except Exception as e:
                    sys.stdout = old_stdout
                    self.log_message.emit(f"❌ Помилка: {str(e)[:100]}")
                    
                self.progress_update.emit(i+1, total_runs)
                
            # --- ОБРОБКА ТОП-5 СТРАТЕГІЙ ---
            if current_run_results:
                self.log_message.emit("<b>🔄 Аналіз та збереження Топ-5 стратегій...</b>")
                top5_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'strategies', 'top5')
                os.makedirs(top5_dir, exist_ok=True)
                metadata_file = os.path.join(top5_dir, 'top5_metadata.json')
                
                global_top5 = []
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            global_top5 = json.load(f)
                    except:
                        pass
                        
                import math
                def goldilocks_score(x):
                    pf = x.get('profit_factor', 0)
                    wr = x.get('win_rate', 0)
                    trades = x.get('total_trades', 0)
                    if trades < 10 or pf < 1.0:
                        return 0
                    return pf * (wr / 100.0) * math.log10(trades)
                    
                global_top5.extend(current_run_results)
                
                # Відкидаємо стратегії з малим числом угод та збиткові
                global_top5 = [x for x in global_top5 if x.get('total_trades', 0) >= 10 and x.get('profit_factor', 0) >= 1.0]
                
                # Сортуємо за Goldilocks score (баланс PF, WR та об'єму угод)
                global_top5.sort(key=goldilocks_score, reverse=True)
                
                # Беремо тільки топ 5
                global_top5 = global_top5[:5]
                
                # Копіюємо файли в top5
                valid_basenames = []
                for strat in global_top5:
                    src_path = strat.get("path")
                    if src_path and os.path.exists(src_path):
                        base_name = os.path.basename(src_path)
                        dst_path = os.path.join(top5_dir, base_name)
                        valid_basenames.append(base_name)
                        if src_path != dst_path:
                            try:
                                shutil.copy2(src_path, dst_path)
                                strat["path"] = dst_path
                            except Exception as e:
                                self.log_message.emit(f"❌ Помилка копіювання топу: {e}")
                                
                # Очищаємо папку top5 від старих стратегій, які випали з рейтингу
                for f_name in os.listdir(top5_dir):
                    if f_name.endswith('.py') and f_name not in valid_basenames:
                        try:
                            os.remove(os.path.join(top5_dir, f_name))
                        except:
                            pass
                                
                # Зберігаємо оновлену мету
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(global_top5, f, indent=4, ensure_ascii=False)
                    
                if global_top5:
                    self.log_message.emit(f"🏆 Топ-5 оновлено: найвищий Profit Factor {global_top5[0]['profit_factor']:.2f} (Угод: {global_top5[0]['total_trades']})")
                else:
                    self.log_message.emit("ℹ️ Жодна стратегія не пройшла фільтр Топ-5 (потрібно PF > 1.0 та Угод >= 10)")

                
                # Видаляємо папку auto_learn з усіма іншими стратегіями
                auto_learn_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'strategies', 'auto_learn')
                if os.path.exists(auto_learn_dir):
                    try:
                        shutil.rmtree(auto_learn_dir)
                        self.log_message.emit("🧹 Папку auto_learn очищено від непотрібних скриптів.")
                    except Exception as e:
                        self.log_message.emit(f"❌ Помилка видалення auto_learn: {e}")
            
            self.finished.emit()
            
        except Exception as e:
            import traceback
            self.log_message.emit(f"❌ Фатальна помилка: {traceback.format_exc()}")
            self.finished.emit()

    def stop(self):
        self.is_running = False
