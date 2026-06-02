from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QComboBox, 
                             QDoubleSpinBox, QSpinBox, QCheckBox, QListWidget, 
                             QPushButton, QHBoxLayout, QLabel, QScrollArea, 
                             QDialog, QTextEdit, QLineEdit)
from gui.visual.UiElements import TitleLabel, StyledGroupBox, PasswordLineEdit

#==================================
# TabSettingsVisual
#==================================
class TabSettingsVisual(QWidget):
    # ----------------------------------
    # __init__, ініціалізація вкладки налаштувань
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
        main_layout = QVBoxLayout()
        main_layout.addWidget(TitleLabel("⚙️ Налаштування Платформи"))

        # 1. Trading Mode Group
        trading_mode_group = StyledGroupBox("Режим Торгівлі (Бектест)")
        trading_mode_layout = QFormLayout()
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Standard", "Binary Options"])
        
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
        
        trading_mode_layout.addRow("Тип ринку:", self.mode_combo)
        trading_mode_layout.addRow("БО - Виплата (Payout):", self.bo_payout_input)
        trading_mode_layout.addRow("БО - Розмір ставки:", self.bo_bet_input)
        trading_mode_layout.addRow("БО - Експірація (барів):", self.bo_exp_input)
        trading_mode_group.setLayout(trading_mode_layout)
        main_layout.addWidget(trading_mode_group)
        
        # 2. Risk Management Group
        risk_group = StyledGroupBox("Ризик Менеджмент (Live Trading)")
        risk_layout = QFormLayout()
        
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
        
        risk_layout.addRow("Стоп-лосс на угоду:", self.stop_loss_input)
        risk_layout.addRow("Макс. просадка за сесію:", self.max_drawdown_input)
        risk_layout.addRow("Денний ліміт втрат:", self.daily_loss_input)
        risk_group.setLayout(risk_layout)
        main_layout.addWidget(risk_group)
        
        # 3. Copilot Settings Group
        copilot_group = StyledGroupBox("Налаштування Копілота")
        copilot_layout = QFormLayout()
        
        self.half_life_input = QSpinBox()
        self.half_life_input.setRange(1, 365)
        self.half_life_input.setSuffix(" днів")
        
        self.min_score_input = QDoubleSpinBox()
        self.min_score_input.setRange(0.1, 1.0)
        self.min_score_input.setSingleStep(0.05)
        
        self.routine_interval_input = QSpinBox()
        self.routine_interval_input.setRange(1, 1440)
        self.routine_interval_input.setSingleStep(1)
        self.routine_interval_input.setSuffix(" хв")
        
        self.update_threshold_input = QDoubleSpinBox()
        self.update_threshold_input.setRange(1.0, 100.0)
        self.update_threshold_input.setSingleStep(1.0)
        
        self.target_assets_input = QLineEdit()
        self.target_assets_input.setPlaceholderText("Наприклад: BTC_USDT, EURUSD (пусто - всі)")
        
        self.assets_presets = QHBoxLayout()
        self.assets_presets.addStretch()
        
        self.target_timeframes_input = QLineEdit()
        self.target_timeframes_input.setPlaceholderText("Наприклад: 1m, 15m (пусто - всі)")
        
        tf_presets = QHBoxLayout()
        for p in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]:
            btn = QPushButton(p)
            btn.setStyleSheet("QPushButton { background-color: #313244; color: #CDD6F4; font-size: 11px; padding: 3px 6px; border-radius: 3px; }")
            btn.clicked.connect(lambda checked, s=p, le=self.target_timeframes_input: self._append_to_lineedit(le, s))
            tf_presets.addWidget(btn)
        tf_presets.addStretch()
        
        copilot_layout.addRow("Період напіврозпаду пам'яті (decay):", self.half_life_input)
        copilot_layout.addRow("Мін. score для успішної стратегії:", self.min_score_input)
        copilot_layout.addRow("Інтервал автоматичного циклу:", self.routine_interval_input)
        copilot_layout.addRow("Мін. вага для оновлення правил:", self.update_threshold_input)
        
        copilot_layout.addRow("Активи для пошуку:", self.target_assets_input)
        copilot_layout.addRow("", self.assets_presets)
        
        copilot_layout.addRow("Таймфрейми для пошуку:", self.target_timeframes_input)
        copilot_layout.addRow("", tf_presets)
        
        self.active_strategies_list = QListWidget()
        self.active_strategies_list.setStyleSheet("background-color: transparent; border: 1px solid #45475A; border-radius: 4px; color: #CDD6F4; min-height: 100px;")
        
        self.btn_add_strategy = QPushButton("+ Додати стратегію")
        self.btn_add_strategy.setStyleSheet("""
            QPushButton {
                background-color: #A6E3A1; 
                color: #11111B; 
                font-weight: bold; 
                padding: 6px; 
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #94E2D5;
            }
        """)
        
        self.btn_remove_strategy = QPushButton("- Видалити")
        self.btn_remove_strategy.setStyleSheet("""
            QPushButton {
                background-color: #F38BA8; 
                color: #11111B; 
                font-weight: bold; 
                padding: 6px; 
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #EBA0AC;
            }
        """)
        
        strat_btn_layout = QHBoxLayout()
        strat_btn_layout.addWidget(self.btn_add_strategy)
        strat_btn_layout.addWidget(self.btn_remove_strategy)
        
        strat_layout = QVBoxLayout()
        strat_layout.addWidget(QLabel("Активні стратегії для сканування:"))
        strat_layout.addWidget(self.active_strategies_list)
        strat_layout.addLayout(strat_btn_layout)
        
        copilot_layout.addRow(strat_layout)
        
        copilot_group.setLayout(copilot_layout)
        main_layout.addWidget(copilot_group)
        
        # 4. Downloader Settings Group
        download_group = StyledGroupBox("Завантаження")
        download_layout = QFormLayout()
        
        self.massive_free_tier_cb = QCheckBox("Massive API - Використовувати обмеження (Free Tier)")
        
        self.massive_requests_input = QSpinBox()
        self.massive_requests_input.setRange(1, 1000)
        self.massive_requests_input.setSuffix(" запитів")
        
        self.massive_wait_input = QSpinBox()
        self.massive_wait_input.setRange(1, 1440)
        self.massive_wait_input.setSuffix(" хв очікування")
        
        download_layout.addRow(self.massive_free_tier_cb)
        download_layout.addRow("Кількість запитів підряд:", self.massive_requests_input)
        download_layout.addRow("Час очікування після ліміту:", self.massive_wait_input)
        
        def on_free_tier_toggled(checked):
            self.massive_requests_input.setEnabled(checked)
            self.massive_wait_input.setEnabled(checked)
            
        self.massive_free_tier_cb.toggled.connect(on_free_tier_toggled)
        
        download_group.setLayout(download_layout)
        main_layout.addWidget(download_group)
        
        # 4.5. Notifications Group
        notifications_group = StyledGroupBox("Сповіщення")
        notifications_layout = QFormLayout()
        
        self.cb_telegram_enabled = QCheckBox("Увімкнути Telegram сповіщення")
        self.telegram_token_input = PasswordLineEdit()
        self.telegram_chat_id_input = PasswordLineEdit()
        
        btn_layout = QHBoxLayout()
        
        self.btn_instruction = QPushButton("ℹ️ Інструкція")
        self.btn_instruction.setStyleSheet("background-color: #F9E2AF; color: #11111B; font-weight: bold; padding: 5px; border-radius: 4px;")
        
        self.btn_test_telegram = QPushButton("Надіслати тестове сповіщення")
        self.btn_test_telegram.setStyleSheet("background-color: #89B4FA; color: #11111B; font-weight: bold; padding: 5px; border-radius: 4px;")
        
        btn_layout.addWidget(self.btn_instruction)
        btn_layout.addWidget(self.btn_test_telegram)
        
        notifications_layout.addRow(self.cb_telegram_enabled)
        notifications_layout.addRow("Telegram Bot Token:", self.telegram_token_input)
        notifications_layout.addRow("Telegram Chat ID:", self.telegram_chat_id_input)
        notifications_layout.addRow("", btn_layout)
        
        notifications_group.setLayout(notifications_layout)
        main_layout.addWidget(notifications_group)
        
        # 5. API Keys Group
        api_group = StyledGroupBox("🔑 API Ключі (Біржі та Дані)")
        api_layout = QFormLayout()
        
        self.bybit_key_input = PasswordLineEdit()
        self.bybit_secret_input = PasswordLineEdit()
        self.binance_key_input = PasswordLineEdit()
        self.binance_secret_input = PasswordLineEdit()
        self.massive_key_input = PasswordLineEdit()
        
        api_layout.addRow("Bybit API Key:", self.bybit_key_input)
        api_layout.addRow("Bybit Secret:", self.bybit_secret_input)
        api_layout.addRow("Binance API Key:", self.binance_key_input)
        api_layout.addRow("Binance Secret:", self.binance_secret_input)
        api_layout.addRow("Massive API Key:", self.massive_key_input)
        api_group.setLayout(api_layout)
        main_layout.addWidget(api_group)
        
        main_layout.addStretch()
        
        container = QWidget()
        container.setLayout(main_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.addWidget(scroll_area)

    def update_asset_presets(self, assets):
        from PyQt6.QtWidgets import QPushButton
        while self.assets_presets.count() > 0:
            item = self.assets_presets.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        for p in assets:
            btn = QPushButton(p)
            btn.setStyleSheet("QPushButton { background-color: #313244; color: #CDD6F4; font-size: 11px; padding: 3px 6px; border-radius: 3px; }")
            btn.clicked.connect(lambda checked, s=p, le=self.target_assets_input: self._append_to_lineedit(le, s))
            self.assets_presets.addWidget(btn)
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
        text_edit.setStyleSheet("font-size: 14px; background-color: #2b2b2b; color: #e0e0e0; padding: 10px;")
        
        help_html = """
        <h2 style='color: #4CAF50;'>🤖 Як підключити Telegram сповіщення</h2>
        
        <h3 style='color: #ff9800;'>Крок 1: Отримання Telegram Bot Token</h3>
        <ol style='line-height: 1.6;'>
            <li>Відкрийте Telegram та знайдіть бота <b>@BotFather</b>.</li>
            <li>Напишіть команду <code>/newbot</code> для створення нового бота.</li>
            <li>Дотримуйтесь інструкцій (вкажіть ім'я бота та його username).</li>
            <li>По завершенню @BotFather надішле вам повідомлення з текстом <b>Use this token to access the HTTP API:</b></li>
            <li>Скопіюйте довгий рядок (наприклад, <code>123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11</code>). Це ваш <b>Bot Token</b>. Вставте його у відповідне поле в налаштуваннях.</li>
        </ol>
        
        <h3 style='color: #ff9800;'>Крок 2: Запуск вашого бота</h3>
        <ol style='line-height: 1.6;'>
            <li>Перейдіть у чат з вашим новоствореним ботом у Telegram (посилання на нього є у повідомленні від @BotFather).</li>
            <li>Натисніть кнопку <b>Start</b> (або напишіть <code>/start</code>). Це обов'язково, інакше бот не зможе надсилати вам повідомлення!</li>
        </ol>

        <h3 style='color: #ff9800;'>Крок 3: Отримання Telegram Chat ID</h3>
        <ol style='line-height: 1.6;'>
            <li>Знайдіть бота <b>@userinfobot</b> (або @getmyid_bot) у Telegram.</li>
            <li>Напишіть йому команду <code>/start</code>.</li>
            <li>Бот надішле вам ваш унікальний ідентифікатор (Id), який складається з цифр (наприклад, <code>123456789</code>).</li>
            <li>Скопіюйте цей номер та вставте його в поле <b>Telegram Chat ID</b> у налаштуваннях.</li>
        </ol>
        
        <h3 style='color: #ff9800;'>Крок 4: Тестування</h3>
        <p>Після введення обох полів натисніть кнопку "Надіслати тестове сповіщення". Якщо ви все зробили правильно, ваш бот надішле вам повідомлення!</p>
        """
        
        text_edit.setHtml(help_html)
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Зрозуміло")
        close_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #4CAF50; color: white; border-radius: 4px;")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        dialog.exec()
