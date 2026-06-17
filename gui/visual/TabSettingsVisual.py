from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QComboBox, 
                             QDoubleSpinBox, QSpinBox, QCheckBox, QListWidget, 
                             QPushButton, QHBoxLayout, QLabel, QScrollArea, 
                             QDialog, QTextEdit, QLineEdit, QStackedWidget, 
                             QSplitter, QFrame, QListWidgetItem, QGridLayout,
                             QTreeWidget, QTreeWidgetItem)
from PyQt6.QtCore import Qt, QSize
from gui.visual.UiElements import TitleLabel, StyledGroupBox, PasswordLineEdit

#==================================
# TabSettingsVisual
#==================================
class TabSettingsVisual(QWidget):
    # ----------------------------------
    # __init__, ініціалізація вкладки налаштувань
    # ----------------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def _create_setting_row(self, title, description, widget):
        row = QFrame()
        row.setStyleSheet("""
            QFrame {
                border-bottom: 1px solid #313244;
                border-radius: 0px;
                background-color: transparent;
            }
            QFrame:hover {
                background-color: #181825;
            }
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(15, 15, 15, 15)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-weight: bold; color: #CDD6F4; font-size: 14px; border: none; background-color: transparent;")
        
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("color: #A6ADC8; font-size: 12px; border: none; background-color: transparent;")
        desc_lbl.setWordWrap(True)
        
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(desc_lbl)
        
        layout.addLayout(text_layout, stretch=1)
        
        if widget:
            # Check if it's a QCheckBox
            if isinstance(widget, QCheckBox):
                widget.setStyleSheet("QCheckBox { color: #CDD6F4; font-size: 14px; }")
            elif isinstance(widget, QPushButton):
                pass
            else:
                widget.setStyleSheet("background-color: #11111B; color: #CDD6F4; border: 1px solid #45475A; border-radius: 4px; padding: 4px;")
            layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
        return row

    def _add_page(self, title, icon):
        item = QListWidgetItem(f"{icon}  {title}")
        self.sidebar.addItem(item)
        
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #1E1E2E;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(0)
        
        page_title = QLabel(title)
        page_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #F9E2AF; margin-bottom: 20px; border: none;")
        content_layout.addWidget(page_title)
        
        scroll.setWidget(content_widget)
        page_layout.addWidget(scroll)
        
        self.stacked_widget.addWidget(page)
        
        return content_layout

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter for sidebar and content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #313244; width: 1px; }")
        
        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: #11111B;
                border: none;
                outline: none;
                padding: 10px;
            }
            QListWidget::item {
                color: #A6ADC8;
                padding: 12px 15px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            QListWidget::item:hover {
                background-color: #181825;
                color: #CDD6F4;
            }
            QListWidget::item:selected {
                background-color: #313244;
                color: #89B4FA;
            }
        """)
        self.sidebar.setFixedWidth(260)
        
        # Content Area
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background-color: #1E1E2E; border: none;")
        
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.stacked_widget)
        main_layout.addWidget(splitter)
        
        self.sidebar.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        
        # Build Pages
        self._build_trading_mode_page()
        self._build_risk_management_page()
        self._build_copilot_page()
        self._build_downloader_page()
        self._build_notifications_page()
        self._build_api_keys_page()
        
        self.sidebar.setCurrentRow(0)

    def _build_trading_mode_page(self):
        layout = self._add_page("Режим Торгівлі", "💼")
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Standard", "Futures", "Binary Options"])
        self.mode_combo.setMinimumWidth(150)
        
        # Standard Settings
        self.std_sizing_combo = QComboBox()
        self.std_sizing_combo.addItems(["Фіксована сума ($)", "% від балансу", "Фіксована кількість"])
        self.std_sizing_combo.setMinimumWidth(150)
        
        self.std_sizing_value = QDoubleSpinBox()
        self.std_sizing_value.setRange(0.01, 1000000.0)
        self.std_sizing_value.setDecimals(4)
        
        self.std_commission = QDoubleSpinBox()
        self.std_commission.setRange(0.0, 100.0)
        self.std_commission.setDecimals(3)
        self.std_commission.setSuffix(" %")

        # Futures Settings
        self.fut_sizing_combo = QComboBox()
        self.fut_sizing_combo.addItems(["Фіксована маржа ($)", "% від балансу", "Фіксована кількість"])
        self.fut_sizing_combo.setMinimumWidth(150)
        
        self.fut_sizing_value = QDoubleSpinBox()
        self.fut_sizing_value.setRange(0.01, 1000000.0)
        self.fut_sizing_value.setDecimals(4)

        self.fut_leverage = QSpinBox()
        self.fut_leverage.setRange(1, 125)
        self.fut_leverage.setSuffix("x")

        self.fut_taker_fee = QDoubleSpinBox()
        self.fut_taker_fee.setRange(0.0, 100.0)
        self.fut_taker_fee.setDecimals(3)
        self.fut_taker_fee.setSuffix(" %")

        self.fut_maker_fee = QDoubleSpinBox()
        self.fut_maker_fee.setRange(0.0, 100.0)
        self.fut_maker_fee.setDecimals(3)
        self.fut_maker_fee.setSuffix(" %")
        
        self.bo_payout_input = QDoubleSpinBox()
        self.bo_payout_input.setRange(1.0, 100.0)
        self.bo_payout_input.setSingleStep(1.0)
        self.bo_payout_input.setSuffix(" %")
        
        self.bo_bet_input = QDoubleSpinBox()
        self.bo_bet_input.setRange(1.0, 100000.0)
        self.bo_bet_input.setPrefix("$ ")
        
        self.bo_exp_input = QSpinBox()
        self.bo_exp_input.setRange(1, 1000)
        self.bo_exp_input.setSuffix(" барів")
        
        self.bo_fixed_time_cb = QCheckBox()
        
        self.bo_fixed_time_input = QSpinBox()
        self.bo_fixed_time_input.setRange(1, 1440)
        self.bo_fixed_time_input.setSuffix(" хвилин")
        
        def add_section(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #89B4FA; margin-top: 25px; margin-bottom: 5px; border: none;")
            layout.addWidget(lbl)

        layout.addWidget(self._create_setting_row("Тип ринку", "Вибір між стандартним ринком (форекс/крипта) та бінарними опціонами.", self.mode_combo))
        
        add_section("Налаштування Standard (Спот)")
        layout.addWidget(self._create_setting_row("Тип сайзингу", "Як розраховувати розмір позиції.", self.std_sizing_combo))
        layout.addWidget(self._create_setting_row("Значення сайзингу", "Сума в $ або %, залежно від типу.", self.std_sizing_value))
        layout.addWidget(self._create_setting_row("Комісія", "Відсоток комісії за одну сторону.", self.std_commission))

        add_section("Налаштування Futures")
        layout.addWidget(self._create_setting_row("Тип сайзингу маржі", "Як розраховувати розмір маржі.", self.fut_sizing_combo))
        layout.addWidget(self._create_setting_row("Значення сайзингу", "Сума в $ або %, залежно від типу.", self.fut_sizing_value))
        layout.addWidget(self._create_setting_row("Кредитне плече", "Множник для об'єму (Notional = Маржа * Плече).", self.fut_leverage))
        layout.addWidget(self._create_setting_row("Комісія Taker", "Відсоток комісії для ринкових ордерів.", self.fut_taker_fee))
        layout.addWidget(self._create_setting_row("Комісія Maker", "Відсоток комісії для лімітних ордерів.", self.fut_maker_fee))

        add_section("Налаштування Бінарних Опціонів")
        layout.addWidget(self._create_setting_row("БО - Виплата (Payout)", "Відсоток виплати у разі успішної угоди (для БО).", self.bo_payout_input))
        layout.addWidget(self._create_setting_row("БО - Розмір ставки", "Фіксована сума для кожної угоди (для БО).", self.bo_bet_input))
        layout.addWidget(self._create_setting_row("БО - Експірація (барів)", "Тривалість угоди у свічках.", self.bo_exp_input))
        layout.addWidget(self._create_setting_row("Фіксований час експірації", "Використовувати абсолютний час замість барів.", self.bo_fixed_time_cb))
        layout.addWidget(self._create_setting_row("БО - Час експірації", "Абсолютний час в хвилинах замість свічок.", self.bo_fixed_time_input))
        layout.addStretch()

    def _build_risk_management_page(self):
        layout = self._add_page("Ризик Менеджмент", "🛡️")
        
        self.initial_balance_input = QDoubleSpinBox()
        self.initial_balance_input.setRange(1.0, 100000000.0)
        self.initial_balance_input.setPrefix("$ ")
        self.initial_balance_input.setSingleStep(100.0)
        
        self.stop_loss_input = QDoubleSpinBox()
        self.stop_loss_input.setRange(0.1, 100.0)
        self.stop_loss_input.setSingleStep(0.1)
        self.stop_loss_input.setSuffix(" %")
        
        self.max_drawdown_input = QDoubleSpinBox()
        self.max_drawdown_input.setRange(0.1, 100.0)
        self.max_drawdown_input.setSingleStep(0.5)
        self.max_drawdown_input.setSuffix(" %")
        
        self.daily_loss_input = QDoubleSpinBox()
        self.daily_loss_input.setRange(0.0, 100000.0)
        self.daily_loss_input.setPrefix("$ ")
        
        layout.addWidget(self._create_setting_row("Початковий баланс", "Сума, з якої починається тестування або торгівля.", self.initial_balance_input))
        layout.addWidget(self._create_setting_row("Стоп-лосс на угоду", "Максимальний ризик втрати в одній угоді.", self.stop_loss_input))
        layout.addWidget(self._create_setting_row("Макс. просадка за сесію", "Ліміт втрат від максимального балансу.", self.max_drawdown_input))
        layout.addWidget(self._create_setting_row("Денний ліміт втрат", "Сума в доларах, після втрати якої торгівля зупиняється на день.", self.daily_loss_input))
        layout.addStretch()

    def _build_copilot_page(self):
        layout = self._add_page("Налаштування Копілота", "🧠")
        
        self.top_strategies_count_input = QSpinBox()
        self.top_strategies_count_input.setRange(1, 100)
        self.top_strategies_count_input.setSuffix(" стратегій")
        
        self.min_pf_input = QDoubleSpinBox()
        self.min_pf_input.setRange(0.1, 10.0)
        self.min_pf_input.setSingleStep(0.1)

        self.min_score_input = QDoubleSpinBox()
        self.min_score_input.setRange(0.1, 1.0)
        self.min_score_input.setSingleStep(0.05)

        self.half_life_input = QSpinBox()
        self.half_life_input.setRange(1, 365)
        self.half_life_input.setSuffix(" днів")
        
        self.update_threshold_input = QDoubleSpinBox()
        self.update_threshold_input.setRange(1.0, 100.0)
        self.update_threshold_input.setSingleStep(1.0)

        # Фільтри
        self.min_trades_mode = QComboBox()
        self.min_trades_mode.addItems(["Глобальний (вся довжина)", "Віконний (стабільність)"])
        self.min_trades_mode.setMinimumWidth(180)
        
        self.min_trades_base_candles = QSpinBox()
        self.min_trades_base_candles.setRange(10, 100000)
        self.min_trades_base_candles.setSingleStep(100)
        self.min_trades_base_candles.setSuffix(" свічок")
        
        self.min_trades_input = QSpinBox()
        self.min_trades_input.setRange(1, 1000)
        self.min_trades_input.setSuffix(" угод")
        
        self.min_trades_tolerance = QSpinBox()
        self.min_trades_tolerance.setRange(1, 100)
        self.min_trades_tolerance.setSuffix(" % вікон")

        # Сканування
        self.target_assets_input = QLineEdit()
        self.target_assets_input.setPlaceholderText("Наприклад: BTC_USDT (пусто - всі)")
        self.target_timeframes_input = QLineEdit()
        self.target_timeframes_input.setPlaceholderText("Наприклад: 1m, 15m (пусто - всі)")

        # Section labels helper
        def add_section(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #89B4FA; margin-top: 25px; margin-bottom: 5px; border: none;")
            layout.addWidget(lbl)

        add_section("Критерії Відбору в Топ та Пам'ять")
        layout.addWidget(self._create_setting_row("Кількість Топ стратегій", "Скільки найкращих алгоритмів Копілот зберігає в 'Топ'. Зменшення змусить швидше відкидати слабші варіанти.", self.top_strategies_count_input))
        layout.addWidget(self._create_setting_row("Мін. Profit Factor для Топ", "Головний критерій якості. Стратегія не потрапить в Топ, якщо її прибутковість нижча за цей показник.", self.min_pf_input))
        layout.addWidget(self._create_setting_row("Мін. Score для успіху", "Комплексний бал (0-1), що поєднує Win Rate, прибуток та кількість угод. Якщо стратегія слабка і не набирає цей бал, вона ігнорується.", self.min_score_input))
        layout.addWidget(self._create_setting_row("Період напіврозпаду пам'яті", "Час у днях, за який Копілот 'забуває' старі алгоритми. Зменшіть, якщо він зациклюється на одних індикаторах.", self.half_life_input))
        layout.addWidget(self._create_setting_row("Мін. вага для оновлення", "Скільки успішних тестів потрібно зібрати, щоб Копілот був впевнений і автоматично оновив глобальні правила (rules.json).", self.update_threshold_input))
        
        add_section("Обмеження даних для Авто Навчання")
        self.auto_learn_limits_layout = QGridLayout()
        
        headers = ["Таймфрейм", "Кількість свічок", "Орієнтовний час", "Всі дані"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet("color: #89B4FA; font-weight: bold;")
            self.auto_learn_limits_layout.addWidget(lbl, 0, col)
            
        self.auto_learn_limit_widgets = {}
        tfs = ["1m", "5m", "15m", "1h", "4h", "1d"]
        tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
        
        class SwitchButton(QPushButton):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setCheckable(True)
                self.setFixedSize(50, 24)
                self.toggled.connect(self._update_style)
                self._update_style(self.isChecked())
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                
            def _update_style(self, checked):
                if checked:
                    self.setText("ВКЛ")
                    self.setStyleSheet("background-color: #A6E3A1; color: #11111B; font-weight: bold; border-radius: 12px; border: none;")
                else:
                    self.setText("ВИКЛ")
                    self.setStyleSheet("background-color: #313244; color: #CDD6F4; font-weight: bold; border-radius: 12px; border: none;")
        
        for row, tf in enumerate(tfs, start=1):
            lbl_tf = QLabel(tf)
            lbl_tf.setStyleSheet("font-weight: bold; color: #CDD6F4;")
            
            spin_candles = QSpinBox()
            spin_candles.setRange(10, 1000000)
            spin_candles.setSingleStep(100)
            spin_candles.setValue(1000)
            
            lbl_time = QLabel("-")
            lbl_time.setStyleSheet("color: #A6ADC8;")
            
            cb_all = SwitchButton()
            cb_all.setChecked(True)
            
            def make_connections(tf_name, spin, lbl, cb, minutes):
                def update_time_label():
                    if cb.isChecked():
                        lbl.setText("Макс.")
                    else:
                        total_min = spin.value() * minutes
                        if total_min < 60:
                            lbl.setText(f"{total_min} хв")
                        elif total_min < 1440:
                            lbl.setText(f"{total_min / 60:.1f} год")
                        else:
                            lbl.setText(f"{total_min / 1440:.1f} днів")
                            
                cb.toggled.connect(lambda checked: [spin.setEnabled(not checked), lbl.setEnabled(not checked), update_time_label()])
                spin.valueChanged.connect(lambda val: update_time_label())
                update_time_label() # initialize
                
            make_connections(tf, spin_candles, lbl_time, cb_all, tf_minutes[tf])
            
            self.auto_learn_limits_layout.addWidget(lbl_tf, row, 0)
            self.auto_learn_limits_layout.addWidget(spin_candles, row, 1)
            self.auto_learn_limits_layout.addWidget(lbl_time, row, 2)
            self.auto_learn_limits_layout.addWidget(cb_all, row, 3)
            
            self.auto_learn_limit_widgets[tf] = {
                "candles": spin_candles,
                "all_data": cb_all
            }
            
        limits_widget = QWidget()
        limits_widget.setLayout(self.auto_learn_limits_layout)
        desc_text = ("Вкажіть, скільки свічок використовувати для кожного таймфрейму під час авто-навчання.\n\n"
                     "💡 Щоб змінити кількість, перемкніть кнопку з 'ВКЛ' на 'ВИКЛ'.\n"
                     "Редагувати можна лише стовпчик зі свічками (час розраховується автоматично).")
        layout.addWidget(self._create_setting_row("Дані для навчання", desc_text, limits_widget))
        
        add_section("Фільтри Активності")
        layout.addWidget(self._create_setting_row("Підхід до оцінки активності", "Глобальний: рахує всі угоди. Віконний: перевіряє, чи торгує стратегія стабільно в кожному проміжку часу.", self.min_trades_mode))
        layout.addWidget(self._create_setting_row("Базовий період", "Розмір вікна (або масштаб) у свічках для перевірки активності.", self.min_trades_base_candles))
        layout.addWidget(self._create_setting_row("Мінімум угод", "Відсіює стратегії, які роблять занадто мало входів і можуть бути випадковістю.", self.min_trades_input))
        layout.addWidget(self._create_setting_row("Допуск (успішних вікон)", "Відсоток вікон, де стратегія виконала план по угодах. Дозволяє іноді 'мовчати'.", self.min_trades_tolerance))

        add_section("Параметри Сканування")
        layout.addWidget(self._create_setting_row("Активи для пошуку", "Список валютних пар або символів для генерації.", self.target_assets_input))
        
        self.assets_presets = QHBoxLayout()
        self.assets_presets.setContentsMargins(0, 0, 0, 0)
        presets_widget = QWidget()
        presets_widget.setStyleSheet("background-color: transparent;")
        presets_widget.setLayout(self.assets_presets)
        layout.addWidget(self._create_setting_row("Прісети активів", "Швидке додавання популярних пар.", presets_widget))
        
        layout.addWidget(self._create_setting_row("Таймфрейми для пошуку", "На яких часових інтервалах створювати стратегії.", self.target_timeframes_input))
        
        tf_presets = QHBoxLayout()
        tf_presets.setContentsMargins(0, 0, 0, 0)
        for p in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
            btn = QPushButton(p)
            btn.setStyleSheet("QPushButton { background-color: #313244; color: #CDD6F4; font-size: 11px; padding: 4px 8px; border-radius: 4px; border: none; } QPushButton:hover { background-color: #45475A; }")
            btn.clicked.connect(lambda checked, s=p, le=self.target_timeframes_input: self._append_to_lineedit(le, s))
            tf_presets.addWidget(btn)
        tf_presets.addStretch()
        
        tf_presets_widget = QWidget()
        tf_presets_widget.setStyleSheet("background-color: transparent;")
        tf_presets_widget.setLayout(tf_presets)
        layout.addWidget(self._create_setting_row("Прісети таймфреймів", "Швидке додавання робочих інтервалів.", tf_presets_widget))

        add_section("Активні Стратегії (Сигнали та Мутація)")
        
        strat_container = QFrame()
        strat_container.setStyleSheet("""
            QFrame {
                border-bottom: 1px solid #313244;
                border-radius: 0px;
                background-color: transparent;
            }
            QFrame:hover {
                background-color: #181825;
            }
        """)
        strat_layout = QVBoxLayout(strat_container)
        strat_layout.setContentsMargins(15, 15, 15, 15)
        strat_layout.setSpacing(10)
        
        lbl_desc = QLabel("Це робочі шаблони, які прямо зараз сканують ринок і дають сигнали. Також Копілот використовує їх як ДНК для мутацій та створення нових підходів.")
        lbl_desc.setStyleSheet("color: #A6ADC8; font-size: 12px; border: none; background-color: transparent;")
        lbl_desc.setWordWrap(True)
        
        self.active_strategies_tree = QTreeWidget()
        self.active_strategies_tree.setHeaderHidden(True)
        self.active_strategies_tree.setStyleSheet("background-color: #11111B; border: 1px solid #313244; border-radius: 6px; color: #CDD6F4; min-height: 150px; padding: 5px;")
        
        # Ініціалізація кореневих вузлів таймфреймів
        tfs = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        for tf in tfs:
            item = QTreeWidgetItem([f"⏱️ {tf}"])
            item.setData(0, Qt.ItemDataRole.UserRole, tf)
            self.active_strategies_tree.addTopLevelItem(item)
        
        self.btn_add_strategy = QPushButton("+ Додати до вибраного ТФ")
        self.btn_add_strategy.setStyleSheet("QPushButton { background-color: #A6E3A1; color: #11111B; font-weight: bold; padding: 8px 16px; border-radius: 4px; border: none; } QPushButton:hover { background-color: #94E2D5; }")
        self.btn_remove_strategy = QPushButton("- Видалити стратегію")
        self.btn_remove_strategy.setStyleSheet("QPushButton { background-color: #F38BA8; color: #11111B; font-weight: bold; padding: 8px 16px; border-radius: 4px; border: none; } QPushButton:hover { background-color: #EBA0AC; }")
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.btn_add_strategy)
        btn_layout.addWidget(self.btn_remove_strategy)
        btn_layout.addStretch()
        
        strat_layout.addWidget(lbl_desc)
        strat_layout.addWidget(self.active_strategies_tree)
        strat_layout.addLayout(btn_layout)
        
        layout.addWidget(strat_container)

        layout.addStretch()

    def _build_downloader_page(self):
        layout = self._add_page("Завантаження Даних", "⬇️")
        self.update_mode_combo = QComboBox()
        self.update_mode_combo.addItems(["polling", "websockets"])
        self.update_mode_combo.setItemText(0, "Скачування (Polling)")
        self.update_mode_combo.setItemText(1, "Трансляція (WebSockets)")
        
        self.massive_free_tier_cb = QCheckBox()
        self.massive_requests_input = QSpinBox()
        self.massive_requests_input.setRange(1, 1000)
        self.massive_requests_input.setSuffix(" запитів")
        
        self.massive_wait_input = QSpinBox()
        self.massive_wait_input.setRange(1, 1440)
        self.massive_wait_input.setSuffix(" хв очікування")
        
        self.massive_delay_input = QSpinBox()
        self.massive_delay_input.setRange(0, 1440)
        self.massive_delay_input.setSuffix(" хв затримки")
        
        def on_free_tier_toggled(checked):
            self.massive_requests_input.setEnabled(checked)
            self.massive_wait_input.setEnabled(checked)
            
        self.massive_free_tier_cb.toggled.connect(on_free_tier_toggled)

        layout.addWidget(self._create_setting_row("Режим оновлення даних", "Оберіть 'Трансляція (WebSockets)' для отримання свічок в реальному часі.", self.update_mode_combo))
        layout.addWidget(self._create_setting_row("Режим Massive API Free Tier", "Увімкніть, щоб дотримуватися безкоштовних лімітів API та уникати бану.", self.massive_free_tier_cb))
        layout.addWidget(self._create_setting_row("Затримка API Massive", "Пауза між запитами.", self.massive_delay_input))
        layout.addWidget(self._create_setting_row("Кількість запитів підряд", "Скільки запитів робити до досягнення ліміту.", self.massive_requests_input))
        layout.addWidget(self._create_setting_row("Час очікування після ліміту", "Перерва для скидання ліміту перед наступними запитами.", self.massive_wait_input))
        layout.addStretch()

    def _build_notifications_page(self):
        layout = self._add_page("Сповіщення", "🔔")
        
        self.cb_telegram_enabled = QCheckBox()
        self.telegram_token_input = PasswordLineEdit()
        self.telegram_chat_id_input = PasswordLineEdit()
        self.telegram_token_input.setMinimumWidth(250)
        self.telegram_chat_id_input.setMinimumWidth(250)
        
        self.btn_instruction = QPushButton("ℹ️ Інструкція")
        self.btn_instruction.setStyleSheet("background-color: #F9E2AF; color: #11111B; font-weight: bold; padding: 8px 16px; border-radius: 4px; border: none;")
        
        self.btn_test_telegram = QPushButton("Тестове сповіщення")
        self.btn_test_telegram.setStyleSheet("background-color: #89B4FA; color: #11111B; font-weight: bold; padding: 8px 16px; border-radius: 4px; border: none;")
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(self.btn_instruction)
        btn_layout.addWidget(self.btn_test_telegram)
        btn_widget = QWidget()
        btn_widget.setStyleSheet("background-color: transparent;")
        btn_widget.setLayout(btn_layout)

        layout.addWidget(self._create_setting_row("Увімкнути Telegram", "Дозволяє Копілоту автоматично надсилати результати в месенджер.", self.cb_telegram_enabled))
        layout.addWidget(self._create_setting_row("Bot Token", "Токен доступу до вашого бота від @BotFather.", self.telegram_token_input))
        layout.addWidget(self._create_setting_row("Chat ID", "ID вашого чату (отримати через @userinfobot).", self.telegram_chat_id_input))
        layout.addWidget(self._create_setting_row("Керування", "Налаштування та тестування Telegram-бота.", btn_widget))
        layout.addStretch()

    def _build_api_keys_page(self):
        layout = self._add_page("API Ключі", "🔑")
        
        self.bybit_key_input = PasswordLineEdit()
        self.bybit_secret_input = PasswordLineEdit()
        self.binance_key_input = PasswordLineEdit()
        self.binance_secret_input = PasswordLineEdit()
        self.massive_key_input = PasswordLineEdit()
        
        # Задаємо ширину для краси
        for w in [self.bybit_key_input, self.bybit_secret_input, self.binance_key_input, self.binance_secret_input, self.massive_key_input]:
            w.setMinimumWidth(300)
        
        layout.addWidget(self._create_setting_row("Bybit API Key", "Ключ доступу Bybit.", self.bybit_key_input))
        layout.addWidget(self._create_setting_row("Bybit Secret", "Секретний ключ Bybit.", self.bybit_secret_input))
        layout.addWidget(self._create_setting_row("Binance API Key", "Ключ доступу Binance.", self.binance_key_input))
        layout.addWidget(self._create_setting_row("Binance Secret", "Секретний ключ Binance.", self.binance_secret_input))
        layout.addWidget(self._create_setting_row("Massive API Key", "Ключ доступу до даних Massive.", self.massive_key_input))
        layout.addStretch()

    def update_asset_presets(self, assets):
        while self.assets_presets.count() > 0:
            item = self.assets_presets.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        if len(assets) <= 5:
            for p in assets:
                btn = QPushButton(p)
                btn.setStyleSheet("QPushButton { background-color: #313244; color: #CDD6F4; font-size: 11px; padding: 4px 8px; border-radius: 4px; border: none; } QPushButton:hover { background-color: #45475A; }")
                btn.clicked.connect(lambda checked, s=p, le=self.target_assets_input: self._append_to_lineedit(le, s))
                self.assets_presets.addWidget(btn)
        else:
            combo = QComboBox()
            combo.setStyleSheet("""
                QComboBox {
                    background-color: #313244;
                    color: #CDD6F4;
                    font-size: 11px;
                    padding: 4px 8px;
                    border-radius: 4px;
                    border: none;
                    min-width: 120px;
                }
                QComboBox:hover {
                    background-color: #45475A;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox QAbstractItemView {
                    background-color: #1E1E2E;
                    color: #CDD6F4;
                    border: 1px solid #313244;
                    selection-background-color: #313244;
                }
            """)
            combo.addItem("Вибрати актив...")
            combo.addItems(assets)
            
            def on_activated(index, c=combo):
                if index > 0:
                    asset = c.itemText(index)
                    self._append_to_lineedit(self.target_assets_input, asset)
                    c.setCurrentIndex(0)
                    
            combo.activated.connect(on_activated)
            self.assets_presets.addWidget(combo)

        self.assets_presets.addStretch()

    def _append_to_lineedit(self, line_edit, text):
        current = line_edit.text().strip()
        if not current:
            line_edit.setText(text)
        else:
            items = [s.strip() for s in current.split(",") if s.strip()]
            if text not in items:
                items.append(text)
                line_edit.setText(", ".join(items))

    def show_telegram_instruction(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Інструкція: Налаштування Telegram")
        dialog.setMinimumSize(600, 480)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("font-size: 14px; background-color: #1E1E2E; color: #CDD6F4; padding: 10px; border: 1px solid #313244; border-radius: 6px;")
        
        help_html = """
        <h2 style='color: #A6E3A1;'>🤖 Як підключити Telegram сповіщення</h2>
        <h3 style='color: #F9E2AF;'>Крок 1: Отримання Telegram Bot Token</h3>
        <ol style='line-height: 1.6;'>
            <li>Відкрийте Telegram та знайдіть бота <b>@BotFather</b>.</li>
            <li>Напишіть команду <code>/newbot</code> для створення нового бота.</li>
            <li>Дотримуйтесь інструкцій (вкажіть ім'я бота та його username).</li>
            <li>По завершенню @BotFather надішле вам повідомлення з текстом <b>Use this token to access the HTTP API:</b></li>
            <li>Скопіюйте довгий рядок (наприклад, <code>123456:ABC-DEF...</code>). Це ваш <b>Bot Token</b>. Вставте його у відповідне поле в налаштуваннях.</li>
        </ol>
        <h3 style='color: #F9E2AF;'>Крок 2: Запуск вашого бота</h3>
        <ol style='line-height: 1.6;'>
            <li>Перейдіть у чат з вашим новоствореним ботом у Telegram.</li>
            <li>Натисніть кнопку <b>Start</b> (або напишіть <code>/start</code>).</li>
        </ol>
        <h3 style='color: #F9E2AF;'>Крок 3: Отримання Telegram Chat ID</h3>
        <ol style='line-height: 1.6;'>
            <li>Знайдіть бота <b>@userinfobot</b> (або @getmyid_bot) у Telegram.</li>
            <li>Напишіть йому команду <code>/start</code>.</li>
            <li>Бот надішле вам ваш унікальний ідентифікатор (Id), який складається з цифр (наприклад, <code>123456789</code>).</li>
            <li>Скопіюйте цей номер та вставте його в поле <b>Telegram Chat ID</b>.</li>
        </ol>
        <h3 style='color: #F9E2AF;'>Крок 4: Тестування</h3>
        <p>Натисніть кнопку "Надіслати тестове сповіщення". Якщо ви все зробили правильно, ваш бот надішле вам повідомлення!</p>
        """
        
        text_edit.setHtml(help_html)
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Зрозуміло")
        close_btn.setStyleSheet("padding: 8px 16px; font-weight: bold; background-color: #89B4FA; color: #11111B; border-radius: 6px; border: none;")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        dialog.exec()
