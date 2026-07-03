# ==================================================================
# ВІДКЛЮЧЕНО (BACKTEST): вкладка "Тестер стратегій" тимчасово знята з
# системи, підлягає повному рефакторингу й оновленню разом із вкладкою
# "Графік" (див. gui/visual/TabChartVisual.py). Ніде не імпортується —
# весь код нижче загорнутий у рядковий літерал і не виконується, лишений
# як довідка для майбутнього переписування. Пов'язані файли, де ця
# вкладка "виходить" за межі себе (позначені !_!_!...!_!_!):
# gui/visual/VisualRegistry.py, gui/logic/LogicRegistry.py,
# gui/GuiBinder.py, gui/MainWindow.py.
# ==================================================================

_DISABLED_TAB_BACKTEST_VISUAL_SOURCE = r'''
import os
import json
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QScrollArea, 
    QGroupBox, QCheckBox, QLabel, QFormLayout, QSpinBox, QDoubleSpinBox, 
    QLineEdit, QPushButton, QTextEdit, QFrame, QFileDialog, QMessageBox, QDialog,
    QComboBox, QListWidget, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QTextCursor, QClipboard
from gui.visual.UiElements import NonWheelSpinBox, NonWheelDoubleSpinBox, CheckableComboBox

#==================================
# TabBacktestVisual
#==================================
class TabBacktestVisual(QWidget):
    request_show_chart = pyqtSignal(str, str, str)
    
    # ----------------------------------
    # __init__, ініціалізація вкладки
    # ----------------------------------
    # Параметри:
    # parent (QWidget): Батьківський віджет
    def __init__(self, parent=None):
        super().__init__(parent)
        self._block_updates = False
        self.param_widgets = {}
        self.meta_data = {}
        self.setup_ui()

    # ----------------------------------
    # setup_ui, створення елементів
    # ----------------------------------
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- ЛІВА ПАНЕЛЬ ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        
        top_half = QWidget()
        top_layout = QVBoxLayout(top_half)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Конструктор стратегії")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        top_layout.addWidget(title_label)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        
        top_layout.addWidget(self.scroll_area)
        
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
        self.btn_delete = QPushButton("🗑️ Видалити")
        self.btn_delete.setStyleSheet("color: #ff453a;")
        self.btn_info = QPushButton("ℹ️ Довідка")
        
        editor_header.addWidget(self.btn_info)
        editor_header.addWidget(self.btn_save)
        editor_header.addWidget(self.btn_load)
        editor_header.addWidget(self.btn_delete)
        
        bottom_layout.addLayout(editor_header)
        
        self.code_editor = QTextEdit()
        self.code_editor.setStyleSheet("font-family: monospace; font-size: 14px; background-color: #1e1e1e; color: #d4d4d4; padding: 10px;")
        
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
        
        left_splitter.addWidget(top_half)
        left_splitter.addWidget(bottom_half)
        left_splitter.setSizes([600, 400])
        left_layout.addWidget(left_splitter)
        
        # --- ПРАВА ПАНЕЛЬ ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        data_source_label = QLabel("Джерело даних")
        data_source_label.setStyleSheet("font-weight: bold; padding-top: 8px;")
        right_layout.addWidget(data_source_label)
        
        table_row = QHBoxLayout()
        table_row.addWidget(QLabel("Актив:"))
        self.table_combo = CheckableComboBox()
        table_row.addWidget(self.table_combo, stretch=1)
        
        table_row.addWidget(QLabel("ТФ:"))
        self.timeframe_combo = QComboBox()
        table_row.addWidget(self.timeframe_combo, stretch=1)
        
        right_layout.addLayout(table_row)
        
        name_layout = QHBoxLayout()
        name_label = QLabel("Ім'я тесту:")
        self.test_name_input = QLineEdit()
        self.test_name_input.setPlaceholderText("Залиште пустим для авто-генерації")
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.test_name_input)
        right_layout.addLayout(name_layout)
        
        strat_layout = QHBoxLayout()
        strat_label = QLabel("Файли Стратегій:")
        self.strat_combo = CheckableComboBox()
        self.strat_combo.setPlaceholderText("Використовувати код з редактора")
        strat_layout.addWidget(strat_label)
        strat_layout.addWidget(self.strat_combo, stretch=1)
        right_layout.addLayout(strat_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("▶ Розрахувати")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 8px;")
        
        self.btn_show_chart = QPushButton("📈 Відобразити на графіку")
        self.btn_show_chart.setStyleSheet("padding: 8px;")
        self.btn_show_chart.setEnabled(False)
        
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_show_chart)
        right_layout.addLayout(btn_layout)
        
        wfv_layout = QHBoxLayout()
        self.btn_run_wfv = QPushButton("🔄 Walk-Forward Validation")
        self.btn_run_wfv.setStyleSheet(
            "QPushButton { background-color: #313244; color: #A6ADC8; padding: 8px; font-weight: bold; border: 1px solid #45475a; border-radius: 4px; } "
            "QPushButton:hover { background-color: #45475a; color: #cdd6f4; }"
            "QPushButton:pressed { background-color: #1e1e2e; }"
        )
        wfv_layout.addWidget(self.btn_run_wfv)
        right_layout.addLayout(wfv_layout)
        
        self.ai_learn_group = QGroupBox("🤖 Авто навчання ШІ")
        self.ai_learn_group.setStyleSheet("QGroupBox { border: 1px solid #bf5af2; border-radius: 5px; margin-top: 15px; padding-top: 15px; color: #bf5af2; font-weight: bold; }")
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
        ai_learn_layout.addWidget(self.btn_auto_learn)
        right_layout.addWidget(self.ai_learn_group)
        
        log_label = QLabel("Журнал результатів:")
        log_label.setStyleSheet("font-weight: bold; padding-top: 10px;")
        right_layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Тут відображатимуться деталі розрахунку...")
        right_layout.addWidget(self.log_output)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 300])
        main_layout.addWidget(splitter)

    # ----------------------------------
    # build_categories, побудова лівого меню
    # ----------------------------------
    def build_categories(self, meta_data, copilot_instance):
        self.meta_data = meta_data
        
        # Видаляємо всі старі віджети
        for i in reversed(range(self.scroll_layout.count())): 
            w = self.scroll_layout.itemAt(i).widget()
            if w: w.deleteLater()
            
        for category in self.meta_data.get("categories", []):
            cat_name = category.get("name", "Інше")
            cat_btn = QPushButton(f"▶ {cat_name}")
            
            if "Copilot" in cat_name:
                color_main, color_hover = "#bf5af2", "#d18ff5"
            else:
                color_main, color_hover = "#4CAF50", "#81C784"
                
            cat_btn.setStyleSheet(f"QPushButton {{ font-size: 16px; font-weight: bold; padding-top: 15px; padding-bottom: 5px; color: {color_main}; text-align: left; border: none; background: transparent; }} QPushButton:hover {{ color: {color_hover}; }}")
            self.scroll_layout.addWidget(cat_btn)
            
            cat_container = QWidget()
            cat_layout = QVBoxLayout(cat_container)
            cat_layout.setContentsMargins(10, 0, 0, 0)
            
            for item in category.get("items", []):
                block = self._create_indicator_block(item, cat_name, copilot_instance)
                cat_layout.addWidget(block)
                
            self.scroll_layout.addWidget(cat_container)
            cat_container.setVisible(False)
            
            # Закриття, щоб не зберігати пізнє зв'язування
            def make_toggle(c, b, n):
                return lambda checked: self._toggle_category(c, b, n)
            cat_btn.clicked.connect(make_toggle(cat_container, cat_btn, cat_name))

        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_content)

    def _toggle_category(self, container, btn, name):
        is_visible = container.isVisible()
        container.setVisible(not is_visible)
        btn.setText(f"▼ {name}" if not is_visible else f"▶ {name}")

    def _create_indicator_block(self, item_meta, cat_name, copilot):
        group_box = QGroupBox()
        group_box.setStyleSheet("QGroupBox { border: 1px solid #555; border-radius: 5px; margin-top: 10px; padding-top: 15px; }")
        layout = QVBoxLayout(group_box)
        
        c_type = item_meta.get("class", "Indicator")
        if c_type == "CopilotSetting":
            title = QLabel(item_meta.get("name", "Unnamed"))
            title.setStyleSheet("font-size: 14px; font-weight: bold; color: #bf5af2;")
            layout.addWidget(title)
            cb = QCheckBox()
            cb.setChecked(True)
            cb.hide()
            # Подія буде підключена в GuiBinder
        else:
            cb = QCheckBox(item_meta.get("name", "Unnamed"))
            cb.setStyleSheet("font-size: 14px; font-weight: bold;")
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
                if c_type == "CopilotSetting" and copilot:
                    p_name = param.get("name")
                    if p_name == "half_life_days": default_val = copilot.half_life_days
                widget.setValue(default_val)
            elif ptype == "float":
                widget = NonWheelDoubleSpinBox()
                widget.setMinimum(param.get("min", -99999.0))
                widget.setMaximum(param.get("max", 99999.0))
                widget.setSingleStep(param.get("step", 0.1))
                default_val = param.get("default", 0.0)
                if c_type == "CopilotSetting" and copilot:
                    p_name = param.get("name")
                    if p_name == "update_threshold_weight": default_val = copilot.update_threshold_weight
                    elif p_name == "min_score_for_best": default_val = copilot.min_score_for_best
                widget.setValue(default_val)
            else:
                widget = QLineEdit()
                widget.setText(str(param.get("default", "")))
                
            form_layout.addRow(param.get("label", param.get("name")), widget)
            widgets_dict[param.get("name")] = widget
            
        layout.addLayout(form_layout)
        self.param_widgets[item_meta["id"]] = {
            "checkbox": cb, "params": widgets_dict, "meta": item_meta, "category": cat_name
        }
        return group_box

    def safe_append_html(self, html_content):
        scrollbar = self.log_output.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html_content)
        if at_bottom: scrollbar.setValue(scrollbar.maximum())

    def update_editor_code(self, copilot):
        if self._block_updates: return
        
        lines = [
            "# --- AUTO-GENERATED VARIABLES (DO NOT EDIT) ---",
            "from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy"
        ]
        
        for ind_id, data in self.param_widgets.items():
            meta = data["meta"]
            if meta.get("class") == "CopilotSetting" and copilot:
                params = data["params"]
                if ind_id == "copilot_time_decay" and "half_life_days" in params:
                    copilot.half_life_days = params["half_life_days"].value()
                elif ind_id == "copilot_auto_learn_threshold" and "update_threshold_weight" in params:
                    copilot.update_threshold_weight = params["update_threshold_weight"].value()
                elif ind_id == "copilot_best_components_score" and "min_score_for_best" in params:
                    copilot.min_score_for_best = params["min_score_for_best"].value()

        has_vars = False
        for ind_id, data in self.param_widgets.items():
            if data["checkbox"].isChecked():
                meta = data["meta"]
                c_type = meta.get("class", "Indicator")
                if c_type == "CopilotSetting": continue
                
                has_vars = True
                param_vals = []
                for p_name, w in data["params"].items():
                    val = w.value() if hasattr(w, 'value') else w.text()
                    if isinstance(val, float) and val.is_integer(): val = int(val)
                    param_vals.append(str(val))
                    
                suffix = "_" + "_".join(param_vals) if param_vals else ""
                var_name = ind_id.lower()
                
                if c_type == "Pattern":
                    arg_name = ind_id.replace("_", " ").title().replace(" ", "_")
                elif c_type == "Algorithm":
                    if ind_id == "ngram" and len(param_vals) > 1:
                        arg_name = f"NGRAM_ROAD_{param_vals[1]}"
                    else:
                        arg_name = ind_id.upper()
                else:
                    arg_name = ind_id.upper() + suffix
                    
                lines.append(f'{var_name} = {c_type}("{arg_name}")')
                
        if not has_vars: lines.append("# (Оберіть індикатори зверху)")
        lines.append("# ----------------------------------------------")
        new_header = "\n".join(lines)
        
        current_text = self.code_editor.toPlainText()
        pattern = re.compile(r'# --- AUTO-GENERATED VARIABLES \(DO NOT EDIT\) ---.*?# ----------------------------------------------', re.DOTALL)
        
        if pattern.search(current_text):
            new_text = pattern.sub(new_header, current_text)
        else:
            new_text = new_header + "\n\n" + current_text
            
        cursor = self.code_editor.textCursor()
        pos = cursor.position()
        self.code_editor.setText(new_text)
        
        diff = len(new_text) - len(current_text)
        new_pos = max(0, pos + diff)
        cursor.setPosition(new_pos)
        self.code_editor.setTextCursor(cursor)

    def save_strategy(self, save_dir):
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
            if not name: return
            if not name.endswith(".py"): name += ".py"
            file_path = os.path.join(save_dir, name)
            text = self.code_editor.toPlainText()
            
            ui_state = {}
            for ind_id, data in self.param_widgets.items():
                if data["checkbox"].isChecked():
                    ui_state[ind_id] = [w.value() if hasattr(w, 'value') else w.text() for w in data["params"].values()]
                    
            state_json = json.dumps(ui_state)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
                f.write(f"\n\n# UI_STATE_META: {state_json}\n")
                
            self.safe_append_html(f"Стратегію збережено: {name}")
            dialog.accept()
            
        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def load_strategy(self, load_dir, copilot):
        os.makedirs(load_dir, exist_ok=True)
        dialog = QDialog(self)
        dialog.setWindowTitle("Відкрити стратегію")
        dialog.setMinimumSize(450, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Оберіть файл стратегії (включаючи авто навчання):"))
        
        tree_widget = QTreeWidget()
        tree_widget.setHeaderHidden(True)
        
        has_files = False
        dir_items = {".": tree_widget.invisibleRootItem()}
        
        for root, dirs, filenames in os.walk(load_dir):
            rel_dir = os.path.relpath(root, load_dir)
            if rel_dir != ".":
                parent_dir = os.path.dirname(rel_dir)
                if not parent_dir: parent_dir = "."
                parent_item = dir_items.get(parent_dir, tree_widget.invisibleRootItem())
                dir_item = QTreeWidgetItem(parent_item, [os.path.basename(rel_dir)])
                dir_item.setData(0, Qt.ItemDataRole.UserRole, "dir")
                dir_items[rel_dir] = dir_item
                
            for filename in sorted(filenames):
                if filename.endswith('.py') or filename.endswith('.txt'):
                    has_files = True
                    parent_item = dir_items.get(rel_dir, tree_widget.invisibleRootItem())
                    file_item = QTreeWidgetItem(parent_item, [filename])
                    file_item.setData(0, Qt.ItemDataRole.UserRole, "file")
                    rel_path = filename if rel_dir == "." else os.path.join(rel_dir, filename).replace("\\", "/")
                    file_item.setData(0, Qt.ItemDataRole.UserRole + 1, rel_path)
                    
        if not has_files:
            QTreeWidgetItem(tree_widget, ["Немає збережених стратегій"])
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
            if not selected or not tree_widget.isEnabled(): return
            if selected.data(0, Qt.ItemDataRole.UserRole) == "dir":
                selected.setExpanded(not selected.isExpanded())
                return
                
            file_name = selected.data(0, Qt.ItemDataRole.UserRole + 1)
            if not file_name: return
            file_path = os.path.join(load_dir, file_name)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                    
                meta_match = re.search(r'# UI_STATE_META: (.*)', text)
                if meta_match:
                    ui_state = json.loads(meta_match.group(1))
                    self._block_updates = True
                    for ind_id, data in self.param_widgets.items():
                        data["checkbox"].setChecked(False)
                        
                    for ind_id, params in ui_state.items():
                        if ind_id in self.param_widgets:
                            data = self.param_widgets[ind_id]
                            data["checkbox"].setChecked(True)
                            for w, val in zip(data["params"].values(), params):
                                if isinstance(w, QSpinBox): w.setValue(int(float(val)))
                                elif isinstance(w, QDoubleSpinBox): w.setValue(float(val))
                                else: w.setText(str(val))
                                
                    self._block_updates = False
                    text = re.sub(r'\n\n# UI_STATE_META: .*', '', text)
                    
                self.code_editor.setText(text.strip() + "\n")
                self.update_editor_code(copilot)
                self.safe_append_html(f"Стратегію завантажено: {file_name}")
                dialog.accept()
            except Exception as e:
                self.safe_append_html(f"Помилка завантаження: {e}")
                dialog.reject()
                
        btn_load.clicked.connect(on_load)
        tree_widget.itemDoubleClicked.connect(on_load)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def delete_strategy(self, load_dir):
        os.makedirs(load_dir, exist_ok=True)
        dialog = QDialog(self)
        dialog.setWindowTitle("Видалити стратегію")
        dialog.setMinimumSize(450, 400)
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Оберіть файл стратегії для видалення:"))
        
        tree_widget = QTreeWidget()
        tree_widget.setHeaderHidden(True)
        
        has_files = False
        dir_items = {".": tree_widget.invisibleRootItem()}
        
        for root, dirs, filenames in os.walk(load_dir):
            rel_dir = os.path.relpath(root, load_dir)
            if rel_dir != ".":
                parent_dir = os.path.dirname(rel_dir)
                if not parent_dir: parent_dir = "."
                parent_item = dir_items.get(parent_dir, tree_widget.invisibleRootItem())
                dir_item = QTreeWidgetItem(parent_item, [os.path.basename(rel_dir)])
                dir_item.setData(0, Qt.ItemDataRole.UserRole, "dir")
                dir_items[rel_dir] = dir_item
                
            for filename in sorted(filenames):
                if filename.endswith('.py') or filename.endswith('.txt'):
                    has_files = True
                    parent_item = dir_items.get(rel_dir, tree_widget.invisibleRootItem())
                    file_item = QTreeWidgetItem(parent_item, [filename])
                    file_item.setData(0, Qt.ItemDataRole.UserRole, "file")
                    rel_path = filename if rel_dir == "." else os.path.join(rel_dir, filename).replace("\\", "/")
                    file_item.setData(0, Qt.ItemDataRole.UserRole + 1, rel_path)
                    
        if not has_files:
            QTreeWidgetItem(tree_widget, ["Немає збережених стратегій"])
            tree_widget.setEnabled(False)
                
        layout.addWidget(tree_widget)
        
        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("Видалити")
        btn_delete.setStyleSheet("background-color: #ff453a; color: white; font-weight: bold;")
        btn_cancel = QPushButton("Скасувати")
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        def on_delete():
            selected = tree_widget.currentItem()
            if not selected or not tree_widget.isEnabled(): return
            if selected.data(0, Qt.ItemDataRole.UserRole) == "dir":
                selected.setExpanded(not selected.isExpanded())
                return
                
            file_name = selected.data(0, Qt.ItemDataRole.UserRole + 1)
            if not file_name: return
            file_path = os.path.join(load_dir, file_name)
            
            confirm = QMessageBox.question(
                dialog, 
                "Підтвердження видалення", 
                f"Ви впевнені, що хочете видалити стратегію:\n{file_name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    os.remove(file_path)
                    self.safe_append_html(f"<span style='color: #ff453a;'>Стратегію видалено: {file_name}</span>")
                    if selected.parent():
                        selected.parent().removeChild(selected)
                    else:
                        tree_widget.invisibleRootItem().removeChild(selected)
                except Exception as e:
                    self.safe_append_html(f"Помилка видалення: {e}")
                
        btn_delete.clicked.connect(on_delete)
        tree_widget.itemDoubleClicked.connect(on_delete)
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
        
        ai_indicators_list = ""
        for cat in self.meta_data.get("categories", []):
            ai_indicators_list += f"\n- {cat.get('name', 'Category')}:\n"
            for item in cat.get("items", []):
                params_desc = [f"{p['name']}={p['default']}" for p in item.get("params", [])]
                params_str = ", ".join(params_desc) if params_desc else "no params"
                desc = item.get("description", "").replace("\n", " ")
                ai_indicators_list += f"  * {item.get('id')} (params: {params_str}) - {desc}\n"
        
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
            "6. You can OPTIONALLY specify TARGET_ASSETS or TARGET_TIMEFRAMES lists at the top of the file to restrict where the strategy runs.\n"
            "7. Your output MUST include `entry`, `exit`, and a `strategy` object.\n\n"
            "=== WHAT EACH VARIABLE TYPE RETURNS ===\n"
            "- Indicator (e.g. sma, rsi, macd): returns a numeric Series. Compare with numbers or other Indicators.\n"
            "- Pattern (e.g. hammer, engulfing): returns True/False (1-sided) or 1/-1 (2-sided, 1=bullish, -1=bearish).\n"
            "- Algorithm (e.g. order_blocks, market_state_linear): returns 1 (bullish), -1 (bearish), or 0 (neutral).\n\n"
            "=== AVAILABLE INDICATORS & ALGORITHMS ===\n"
            f"{ai_indicators_list}\n"
            "=== EXAMPLE OUTPUT FORMAT ===\n"
            "from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy\n"
            "TARGET_ASSETS = ['BTC_USDT', 'EURUSD']  # Optional restriction\n"
            "TARGET_TIMEFRAMES = ['15m', '1h']       # Optional restriction\n\n"
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
        
        all_indicators_html = "<ul>"
        for cat in self.meta_data.get("categories", []):
            all_indicators_html += f"<li style='margin-top: 5px;'><b>{cat.get('name', 'Інше')}</b>: "
            items = [f"{item.get('name')} (<code>{item.get('id')}</code>)" for item in cat.get("items", [])]
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

'''
