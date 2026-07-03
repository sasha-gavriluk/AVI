from PyQt6.QtWidgets import QTabWidget, QMessageBox, QPushButton, QComboBox
from PyQt6.QtCore import QDateTime
from gui.visual.VisualRegistry import VisualRegistry
from gui.logic.LogicRegistry import LogicRegistry

#==================================
# GuiBinder
#==================================
class GuiBinder:
    # ----------------------------------
    # __init__, ініціалізація зв'язувача GUI
    # ----------------------------------
    # Параметри:
    # visual (VisualRegistry): Реєстр всіх візуальних вкладок
    # logic (LogicRegistry): Реєстр всіх логічних модулів
    def __init__(self, visual: VisualRegistry, logic: LogicRegistry):
        self.v = visual
        self.l = logic
        self.is_db_locked_callback = None
        self.switch_to_downloader_callback = None

    # ----------------------------------
    # bind_all, виклик всіх методів зв'язування
    # ----------------------------------
    # Параметри: немає
    def bind_all(self):
        self._bind_settings()
        self._bind_explorer()
        self._bind_downloader()
        # ВІДКЛЮЧЕНО: вкладка "Графік" тимчасово знята з системи, підлягає
        # рефакторингу й оновленню. Метод _bind_chart() лишається нижче
        # незмінним (код збережено), але більше не викликається.
        # self._bind_chart()
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # ВІДКЛЮЧЕНО (BACKTEST): вкладка "Тестер стратегій" тимчасово знята
        # з системи, підлягає рефакторингу й оновленню. Метод _bind_backtest()
        # лишається нижче незмінним (код збережено), але більше не
        # викликається. Пов'язані блоки: gui/visual/VisualRegistry.py,
        # gui/logic/LogicRegistry.py, gui/MainWindow.py.
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # self._bind_backtest()
        self._bind_copilot()
        self._bind_live_algo()
        
    # ----------------------------------
    # _bind_explorer, зв'язування вкладки провідника
    # ----------------------------------
    # Параметри: немає
    def _bind_explorer(self):
        tab = self.v.explorer_tab
        logic = self.l.explorer
        
        def load_databases():
            tab.tree_view.clear()
            tab.tree_view.addTopLevelItem(__import__("PyQt6").QtWidgets.QTreeWidgetItem(["Завантаження..."]))
            logic.request_databases_async(self.is_db_locked_callback)
            
        logic.db_loaded.connect(tab.tree_view.populate)
        tab.btn_refresh.clicked.connect(load_databases)
        
        def on_table_selected(db_path, table_name):
            if self.is_db_locked_callback and self.is_db_locked_callback(db_path):
                if self.switch_to_downloader_callback:
                    self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nПерегляд тимчасово недоступний.")
                return
            
            tab.lbl_page.setText("Завантаження...")
            logic.request_table_data_async(db_path, table_name, reset_offset=True)

        tab.tree_view.table_selected.connect(on_table_selected)
        
        def on_table_data_loaded(data, total_rows):
            if data is not None:
                tab.table_view.set_data(data)
                current_rows = len(data)
                start_row = logic.current_offset + 1 if current_rows > 0 else 0
                end_row = logic.current_offset + current_rows
                tab.lbl_page.setText(f"Рядки: {start_row} - {end_row} із {total_rows}")
                tab.btn_prev.setEnabled(logic.current_offset > 0)
                tab.btn_next.setEnabled((logic.current_offset + logic.limit) < total_rows)
                
                tab.btn_open_chart.setEnabled(True)
                tab.btn_disconnect.setEnabled(True)
                tab.btn_clean_db.setEnabled(True)
                tab.btn_delete_table.setEnabled(True)
                
        logic.table_loaded.connect(on_table_data_loaded)

        # ----------------------------------
        # update_pagination_labels, запит оновлених сторінок
        # ----------------------------------
        # Параметри: немає
        def update_pagination_labels():
            tab.lbl_page.setText("Завантаження...")
            logic.request_table_data_async(logic.db_service.current_db_path, logic.current_table_name, reset_offset=False)

        # ----------------------------------
        # on_prev_page, попередня сторінка
        # ----------------------------------
        # Параметри: немає
        def on_prev_page():
            if logic.current_offset >= logic.limit:
                logic.current_offset -= logic.limit
                update_pagination_labels()

        # ----------------------------------
        # on_next_page, наступна сторінка
        # ----------------------------------
        # Параметри: немає
        def on_next_page():
            logic.current_offset += logic.limit
            update_pagination_labels()

        tab.btn_prev.clicked.connect(on_prev_page)
        tab.btn_next.clicked.connect(on_next_page)

        # ----------------------------------
        # on_disconnect, відключення від БД
        # ----------------------------------
        # Параметри: немає
        def on_disconnect():
            db_path = logic.db_service.current_db_path
            if db_path and self.is_db_locked_callback and self.is_db_locked_callback(db_path):
                if self.switch_to_downloader_callback:
                    self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nВідключення або модифікація тимчасово недоступні.")
                return
            logic.db_service.disconnect()
            tab.table_view.set_data(None)
            tab.lbl_page.setText("БД Відключена")
            tab.btn_open_chart.setEnabled(False)
            tab.btn_disconnect.setEnabled(False)
            tab.btn_clean_db.setEnabled(False)
            tab.btn_delete_table.setEnabled(False)
            tab.btn_prev.setEnabled(False)
            tab.btn_next.setEnabled(False)

        tab.btn_disconnect.clicked.connect(on_disconnect)

        # ----------------------------------
        # on_clean_db, очищення тестових таблиць
        # ----------------------------------
        # Параметри: немає
        def on_clean_db():
            db_path = logic.db_service.current_db_path
            if db_path and self.is_db_locked_callback and self.is_db_locked_callback(db_path):
                if self.switch_to_downloader_callback:
                    self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nОчищення неможливе.")
                return
            reply = QMessageBox.question(tab, 'Підтвердження', 'Ви дійсно хочете видалити всі таблиці результатів тестування?\nЦя дія незворотна!', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    count = logic.clean_tests()
                    QMessageBox.information(tab, "Успіх", f"Видалено {count} таблиць з результатами тестів.")
                    load_databases()
                    tab.table_view.set_data(None)
                    tab.btn_open_chart.setEnabled(False)
                except Exception as e:
                    QMessageBox.critical(tab, "Помилка", f"Помилка при очищенні: {e}")

        tab.btn_clean_db.clicked.connect(on_clean_db)

        # ----------------------------------
        # on_delete_table, видалення таблиці
        # ----------------------------------
        # Параметри: немає
        def on_delete_table():
            if not logic.current_table_name: return
            db_path = logic.db_service.current_db_path
            if db_path and self.is_db_locked_callback and self.is_db_locked_callback(db_path):
                if self.switch_to_downloader_callback:
                    self.switch_to_downloader_callback("Ця база даних зараз зайнята завантаженням.\nВидалення неможливе.")
                return
            reply = QMessageBox.question(tab, 'Підтвердження', f'Ви дійсно хочете безповоротно видалити таблицю "{logic.current_table_name}"?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    logic.delete_table(logic.current_table_name)
                    QMessageBox.information(tab, "Успіх", f"Таблиця {logic.current_table_name} успішно видалена.")
                    load_databases()
                    tab.table_view.set_data(None)
                    tab.btn_open_chart.setEnabled(False)
                    tab.btn_delete_table.setEnabled(False)
                    tab.lbl_page.setText("Оберіть іншу таблицю")
                except Exception as e:
                    QMessageBox.critical(tab, "Помилка", f"Помилка при видаленні: {e}")

        tab.btn_delete_table.clicked.connect(on_delete_table)

    # ----------------------------------
    # _bind_settings, зв'язування вкладки налаштувань
    # ----------------------------------
    # Параметри: немає
    def _bind_settings(self):
        tab = self.v.settings_tab
        logic = self.l.settings
        
        data = logic.load_settings()
        tab.mode_combo.setCurrentText(data["trading_mode"].get("type", "Standard"))
        
        # Standard Settings
        tab.std_sizing_combo.setCurrentText(data["trading_mode"].get("standard_sizing_type", "Фіксована сума ($)"))
        tab.std_sizing_value.setValue(data["trading_mode"].get("standard_sizing_value", 1000.0))
        tab.std_commission.setValue(data["trading_mode"].get("standard_commission_percent", 0.1))
        
        # Futures Settings
        tab.fut_sizing_combo.setCurrentText(data["trading_mode"].get("futures_sizing_type", "Фіксована маржа ($)"))
        tab.fut_sizing_value.setValue(data["trading_mode"].get("futures_sizing_value", 100.0))
        tab.fut_leverage.setValue(data["trading_mode"].get("futures_leverage", 10))
        tab.fut_taker_fee.setValue(data["trading_mode"].get("futures_taker_fee", 0.05))
        tab.fut_maker_fee.setValue(data["trading_mode"].get("futures_maker_fee", 0.02))
        
        # Binary Options Settings
        tab.bo_payout_input.setValue(data["trading_mode"].get("bo_payout_percent", 80.0))
        tab.bo_bet_input.setValue(data["trading_mode"].get("bo_bet_size", 10.0))
        tab.bo_exp_input.setValue(data["trading_mode"].get("bo_expiration_bars", 1))
        tab.bo_fixed_time_cb.setChecked(data["trading_mode"].get("bo_fixed_time_enabled", False))
        tab.bo_fixed_time_input.setValue(data["trading_mode"].get("bo_fixed_time_minutes", 60))
        tab.bo_fixed_time_input.setEnabled(tab.bo_fixed_time_cb.isChecked())
        tab.bo_exp_input.setEnabled(not tab.bo_fixed_time_cb.isChecked())
        
        tab.initial_balance_input.setValue(data["risk_management"].get("initial_balance", 10000.0))
        tab.stop_loss_input.setValue(data["risk_management"]["stop_loss_percent"])
        tab.max_drawdown_input.setValue(data["risk_management"]["max_drawdown_session"])
        tab.daily_loss_input.setValue(data["risk_management"]["daily_loss_limit"])
        
        tab.half_life_input.setValue(data["copilot"]["half_life_days"])
        tab.min_score_input.setValue(data["copilot"]["min_score_for_best"])
        tab.update_threshold_input.setValue(data["copilot"].get("update_threshold_weight", 15.0))
        tab.top_strategies_count_input.setValue(data["copilot"].get("top_strategies_count", 5))
        tab.min_trades_input.setValue(data["copilot"].get("min_trades", 10))
        mode_idx = 0 if data["copilot"].get("min_trades_mode", "Global") == "Global" else 1
        tab.min_trades_mode.setCurrentIndex(mode_idx)
        tab.min_trades_base_candles.setValue(data["copilot"].get("min_trades_base_candles", 1000))
        tab.min_trades_tolerance.setValue(data["copilot"].get("min_trades_tolerance", 80))
        tab.min_pf_input.setValue(data["copilot"].get("min_profit_factor", 1.0))
        tab.target_assets_input.setText(", ".join(data["copilot"].get("target_assets", [])))
        tab.target_timeframes_input.setText(", ".join(data["copilot"].get("target_timeframes", [])))
        
        limit_data = data["copilot"].get("auto_learn_data_limits", {})
        for tf, widgets in tab.auto_learn_limit_widgets.items():
            saved = limit_data.get(tf, {"all_data": True, "candles": 1000})
            widgets["all_data"].setChecked(saved.get("all_data", True))
            widgets["candles"].setValue(saved.get("candles", 1000))
        
        # New load logic for strategies tree
        tree_data = data["copilot"].get("active_strategies_tree", {})
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTreeWidgetItem
        for i in range(tab.active_strategies_tree.topLevelItemCount()):
            tf_item = tab.active_strategies_tree.topLevelItem(i)
            tf = tf_item.data(0, Qt.ItemDataRole.UserRole)
            tf_item.takeChildren()
            strats = tree_data.get(tf, [])
            for strat in strats:
                child = QTreeWidgetItem([strat])
                child.setData(0, Qt.ItemDataRole.UserRole, strat)
                tf_item.addChild(child)
            tf_item.setExpanded(True)
        
        mode = data.get("downloader", {}).get("update_mode", "polling")
        tab.update_mode_combo.setCurrentIndex(0 if mode == "polling" else 1)
        tab.massive_free_tier_cb.setChecked(data.get("downloader", {}).get("massive_free_tier", True))
        tab.massive_requests_input.setValue(data.get("downloader", {}).get("massive_free_requests", 5))
        tab.massive_wait_input.setValue(data.get("downloader", {}).get("massive_free_wait_minutes", 3))
        tab.massive_delay_input.setValue(data.get("downloader", {}).get("massive_api_delay_minutes", 15))
        # Ініціалізація активності полів
        tab.massive_requests_input.setEnabled(tab.massive_free_tier_cb.isChecked())
        tab.massive_wait_input.setEnabled(tab.massive_free_tier_cb.isChecked())
        tab.cb_telegram_enabled.setChecked(data.get("notifications", {}).get("telegram_enabled", False))
        
        keys = logic.load_api_keys()
        tab.bybit_key_input.setText(keys.get("BYBIT_KEY", ""))
        tab.bybit_secret_input.setText(keys.get("BYBIT_SECRET_KEY", ""))
        tab.binance_key_input.setText(keys.get("BINANCE_KEY", ""))
        tab.binance_secret_input.setText(keys.get("BINANCE_SECRET_KEY", ""))
        tab.massive_key_input.setText(keys.get("MASSIVE_KEY", ""))
        tab.telegram_token_input.setText(keys.get("TELEGRAM_BOT_TOKEN", ""))
        tab.telegram_chat_id_input.setText(keys.get("TELEGRAM_CHAT_ID", ""))
        
        def refresh_settings_assets():
            try:
                raw_assets = self.l.chart.get_available_assets()
                unique_assets = set()
                for db, tbl in raw_assets:
                    if tbl.startswith("copilot") or tbl.startswith("temp") or tbl.startswith("rules") or tbl.startswith("sqlite") or tbl.startswith("backtest"):
                        continue
                    parts = tbl.split('_')
                    if len(parts) >= 2:
                        asset_raw = "_".join(parts[:-1])
                    else:
                        asset_raw = tbl
                    unique_assets.add(asset_raw)
                tab.update_asset_presets(sorted(list(unique_assets))[:12])
            except Exception as e:
                print(f"Помилка завантаження пресетів активів: {e}")
                
        tab.refresh_settings_assets = refresh_settings_assets
        tab.refresh_settings_assets()

        # ----------------------------------
        # save_from_ui, локальна функція для збору даних і збереження
        # ----------------------------------
        # Параметри: немає
        def save_from_ui():
            new_data = {
                "trading_mode": {
                    "type": tab.mode_combo.currentText(),
                    "bo_payout_percent": tab.bo_payout_input.value(),
                    "bo_bet_size": tab.bo_bet_input.value(),
                    "bo_expiration_bars": tab.bo_exp_input.value(),
                    "bo_fixed_time_enabled": tab.bo_fixed_time_cb.isChecked(),
                    "bo_fixed_time_minutes": tab.bo_fixed_time_input.value(),
                    
                    "standard_sizing_type": tab.std_sizing_combo.currentText(),
                    "standard_sizing_value": tab.std_sizing_value.value(),
                    "standard_commission_percent": tab.std_commission.value(),
                    
                    "futures_sizing_type": tab.fut_sizing_combo.currentText(),
                    "futures_sizing_value": tab.fut_sizing_value.value(),
                    "futures_leverage": tab.fut_leverage.value(),
                    "futures_taker_fee": tab.fut_taker_fee.value(),
                    "futures_maker_fee": tab.fut_maker_fee.value()
                },
                "risk_management": {
                    "initial_balance": tab.initial_balance_input.value(),
                    "stop_loss_percent": tab.stop_loss_input.value(),
                    "max_drawdown_session": tab.max_drawdown_input.value(),
                    "daily_loss_limit": tab.daily_loss_input.value()
                },
                "copilot": {
                    "half_life_days": tab.half_life_input.value(),
                    "min_score_for_best": tab.min_score_input.value(),
                    "update_threshold_weight": tab.update_threshold_input.value(),
                    "top_strategies_count": tab.top_strategies_count_input.value(),
                    "min_trades": tab.min_trades_input.value(),
                    "min_trades_mode": "Global" if tab.min_trades_mode.currentIndex() == 0 else "Window",
                    "min_trades_base_candles": tab.min_trades_base_candles.value(),
                    "min_trades_tolerance": tab.min_trades_tolerance.value(),
                    "min_profit_factor": tab.min_pf_input.value(),
                    "target_assets": [s.strip() for s in tab.target_assets_input.text().split(',') if s.strip()],
                    "target_timeframes": [s.strip() for s in tab.target_timeframes_input.text().split(',') if s.strip()],
                    "active_strategies_tree": {
                        tab.active_strategies_tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole): [
                            tab.active_strategies_tree.topLevelItem(i).child(j).data(0, Qt.ItemDataRole.UserRole)
                            for j in range(tab.active_strategies_tree.topLevelItem(i).childCount())
                        ]
                        for i in range(tab.active_strategies_tree.topLevelItemCount())
                    },
                    "auto_learn_data_limits": {
                        tf: {
                            "all_data": widgets["all_data"].isChecked(),
                            "candles": widgets["candles"].value()
                        }
                        for tf, widgets in tab.auto_learn_limit_widgets.items()
                    }
                },
                "downloader": {
                    "update_mode": "polling" if tab.update_mode_combo.currentIndex() == 0 else "websockets",
                    "massive_free_tier": tab.massive_free_tier_cb.isChecked(),
                    "massive_free_requests": tab.massive_requests_input.value(),
                    "massive_free_wait_minutes": tab.massive_wait_input.value(),
                    "massive_api_delay_minutes": tab.massive_delay_input.value()
                },
                "notifications": {
                    "telegram_enabled": tab.cb_telegram_enabled.isChecked()
                }
            }
            logic.save_settings(new_data)
            
            new_keys = {
                "BYBIT_KEY": tab.bybit_key_input.text(),
                "BYBIT_SECRET_KEY": tab.bybit_secret_input.text(),
                "BINANCE_KEY": tab.binance_key_input.text(),
                "BINANCE_SECRET_KEY": tab.binance_secret_input.text(),
                "MASSIVE_KEY": tab.massive_key_input.text(),
                "TELEGRAM_BOT_TOKEN": tab.telegram_token_input.text(),
                "TELEGRAM_CHAT_ID": tab.telegram_chat_id_input.text()
            }
            logic.save_api_keys(new_keys)

        tab.mode_combo.currentTextChanged.connect(save_from_ui)
        tab.std_sizing_combo.currentTextChanged.connect(save_from_ui)
        tab.std_sizing_value.valueChanged.connect(save_from_ui)
        tab.std_commission.valueChanged.connect(save_from_ui)
        
        tab.fut_sizing_combo.currentTextChanged.connect(save_from_ui)
        tab.fut_sizing_value.valueChanged.connect(save_from_ui)
        tab.fut_leverage.valueChanged.connect(save_from_ui)
        tab.fut_taker_fee.valueChanged.connect(save_from_ui)
        tab.fut_maker_fee.valueChanged.connect(save_from_ui)

        tab.bo_payout_input.valueChanged.connect(save_from_ui)
        tab.bo_bet_input.valueChanged.connect(save_from_ui)
        tab.bo_exp_input.valueChanged.connect(save_from_ui)
        
        def on_fixed_time_toggled(checked):
            tab.bo_fixed_time_input.setEnabled(checked)
            tab.bo_exp_input.setEnabled(not checked)
            save_from_ui()
            
        tab.bo_fixed_time_cb.toggled.connect(on_fixed_time_toggled)
        tab.bo_fixed_time_input.valueChanged.connect(save_from_ui)
        tab.initial_balance_input.valueChanged.connect(save_from_ui)
        tab.stop_loss_input.valueChanged.connect(save_from_ui)
        tab.max_drawdown_input.valueChanged.connect(save_from_ui)
        tab.daily_loss_input.valueChanged.connect(save_from_ui)
        tab.half_life_input.valueChanged.connect(save_from_ui)
        tab.min_score_input.valueChanged.connect(save_from_ui)
        tab.update_threshold_input.valueChanged.connect(save_from_ui)
        tab.top_strategies_count_input.valueChanged.connect(save_from_ui)
        tab.min_trades_input.valueChanged.connect(save_from_ui)
        tab.min_trades_mode.currentIndexChanged.connect(save_from_ui)
        tab.min_trades_base_candles.valueChanged.connect(save_from_ui)
        tab.min_trades_tolerance.valueChanged.connect(save_from_ui)
        tab.min_pf_input.valueChanged.connect(save_from_ui)
        tab.target_assets_input.textChanged.connect(save_from_ui)
        tab.target_timeframes_input.textChanged.connect(save_from_ui)
        
        for tf, widgets in tab.auto_learn_limit_widgets.items():
            widgets["all_data"].toggled.connect(save_from_ui)
            widgets["candles"].valueChanged.connect(save_from_ui)
            
        tab.massive_free_tier_cb.stateChanged.connect(save_from_ui)
        tab.massive_requests_input.valueChanged.connect(save_from_ui)
        tab.massive_wait_input.valueChanged.connect(save_from_ui)
        tab.massive_delay_input.valueChanged.connect(save_from_ui)
        tab.bybit_key_input.textChanged.connect(save_from_ui)
        tab.bybit_secret_input.textChanged.connect(save_from_ui)
        tab.binance_key_input.textChanged.connect(save_from_ui)
        tab.binance_secret_input.textChanged.connect(save_from_ui)
        tab.massive_key_input.textChanged.connect(save_from_ui)
        tab.cb_telegram_enabled.stateChanged.connect(save_from_ui)
        tab.telegram_token_input.textChanged.connect(save_from_ui)
        tab.telegram_chat_id_input.textChanged.connect(save_from_ui)
        
        def test_telegram():
            save_from_ui()
            from utils.notification_service import TelegramNotifier
            notifier = TelegramNotifier()
            from PyQt6.QtWidgets import QMessageBox
            if notifier.send_message("✅ Це тестове повідомлення з платформи AVI!"):
                QMessageBox.information(tab, "Успіх", "Тестове повідомлення успішно надіслано в Telegram!")
            else:
                QMessageBox.warning(tab, "Помилка", "Не вдалося надіслати повідомлення. Перевірте токен та Chat ID.")
                
        tab.btn_test_telegram.clicked.connect(test_telegram)
        tab.btn_instruction.clicked.connect(tab.show_telegram_instruction)
        
        def add_strategy():
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            import os
            from utils.PathManager import PathManager
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QTreeWidgetItem
            
            selected_items = tab.active_strategies_tree.selectedItems()
            if not selected_items:
                QMessageBox.warning(tab, "Увага", "Спочатку виділіть таймфрейм (наприклад, 1m) куди додати стратегію.")
                return
                
            target_item = selected_items[0]
            # Якщо вибрано стратегію, беремо її батька (таймфрейм)
            if target_item.parent():
                target_item = target_item.parent()
                
            start_dir = PathManager.get_strategies_dir()
            os.makedirs(start_dir, exist_ok=True)
            files, _ = QFileDialog.getOpenFileNames(tab, f"Оберіть стратегії для {target_item.data(0, Qt.ItemDataRole.UserRole)}", start_dir, "Python Files (*.py)")
            if files:
                existing_children = [target_item.child(i).data(0, Qt.ItemDataRole.UserRole) for i in range(target_item.childCount())]
                for f in files:
                    rel = os.path.relpath(f, PathManager.get_user_data_dir())
                    if rel not in existing_children:
                        child = QTreeWidgetItem([rel])
                        child.setData(0, Qt.ItemDataRole.UserRole, rel)
                        target_item.addChild(child)
                target_item.setExpanded(True)
                save_from_ui()
                
        def remove_strategy():
            selected_items = tab.active_strategies_tree.selectedItems()
            if not selected_items: return
            item = selected_items[0]
            # Не можна видалити кореневий вузол таймфрейму
            if not item.parent(): return
            
            item.parent().removeChild(item)
            save_from_ui()
            
        tab.btn_add_strategy.clicked.connect(add_strategy)
        tab.btn_remove_strategy.clicked.connect(remove_strategy)

    # ----------------------------------
    # _bind_downloader, зв'язування завантажувача
    # ----------------------------------
    # Параметри: немає
    def _bind_downloader(self):
        tab = self.v.downloader_tab
        logic = self.l.downloader

        def append_symbol(symbol: str):
            current = tab.symbols_input.text().strip()
            if not current:
                tab.symbols_input.setText(symbol)
            else:
                symbols = [s.strip().upper() for s in current.split(",") if s.strip()]
                if symbol not in symbols:
                    symbols.append(symbol)
                    tab.symbols_input.setText(", ".join(symbols))

        def update_symbol_presets():
            while tab.presets_row.count() > 1:
                item = tab.presets_row.takeAt(1)
                widget = item.widget()
                if widget: widget.deleteLater()
                    
            is_massive = tab.radio_massive.isChecked()
            is_crypto_mode = not is_massive or tab.massive_market_combo.currentIndex() == 1
            
            top_presets = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT"] if is_crypto_mode else ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
            
            for p in top_presets:
                btn = QPushButton(p)
                btn.setStyleSheet("QPushButton { background-color: #313244; color: #CDD6F4; font-size: 11px; padding: 3px 6px; border-radius: 3px; }")
                btn.clicked.connect(lambda checked, symbol=p: append_symbol(symbol))
                tab.presets_row.addWidget(btn)
                
            all_presets = [
                "BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT", "ADA_USDT", "AVAX_USDT", 
                "DOT_USDT", "DOGE_USDT", "SHIB_USDT", "LINK_USDT", "LTC_USDT", "UNI_USDT", 
                "NEAR_USDT", "FIL_USDT", "ATOM_USDT", "ICP_USDT", "APT_USDT", "OP_USDT", 
                "ARB_USDT", "INJ_USDT", "BTC_USD", "ETH_USD", "SOL_USD"
            ] if is_crypto_mode else [
                "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", 
                "EURGBP", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD", "SPX500", "NAS100", 
                "US30", "GER30", "UK100"
            ]
            
            combo = QComboBox()
            combo.addItem("➕ Обрати зі списку (20+)...")
            combo.addItems(all_presets)
            combo.setStyleSheet("QComboBox { background-color: #313244; color: #CDD6F4; padding: 2px; }")
            
            def on_combo_act(index):
                if index > 0:
                    append_symbol(combo.itemText(index))
                    combo.setCurrentIndex(0)
            combo.activated.connect(on_combo_act)
            tab.presets_row.addWidget(combo)
            tab.presets_row.addStretch()

        def on_source_changed():
            is_massive = tab.radio_massive.isChecked()
            tab.exchange_group.setEnabled(not is_massive)
            tab.massive_market_combo.setEnabled(is_massive)
            
            if is_massive:
                tab.exchange_group.setTitle("Вибір Біржі 🔒 (Недоступно для Massive)")
                if tab.massive_market_combo.currentIndex() == 0:
                    tab.symbols_input.setText("EURUSD, GBPUSD")
                else:
                    tab.symbols_input.setText("BTC_USD, ETH_USD")
            else:
                tab.exchange_group.setTitle("Вибір Біржі")
                tab.symbols_input.setText("BTC_USDT, ETH_USDT")
            update_symbol_presets()

        tab.radio_massive.toggled.connect(on_source_changed)
        tab.massive_market_combo.currentIndexChanged.connect(on_source_changed)
        update_symbol_presets()

        quick_times = [("7д", -7), ("1м", -30), ("3м", -90), ("1р", -365)]
        for label, days in quick_times:
            btn = QPushButton(label)
            btn.setStyleSheet("QPushButton { background-color: #313244; color: #CDD6F4; font-size: 11px; padding: 3px 8px; }")
            def make_set_date(d):
                def set_quick_date(checked):
                    tab.date_end.setDateTime(QDateTime.currentDateTime())
                    tab.date_start.setDateTime(QDateTime.currentDateTime().addDays(d))
                return set_quick_date
            btn.clicked.connect(make_set_date(days))
            tab.quick_time_layout.addWidget(btn)
        tab.quick_time_layout.addStretch()

        def on_log_message(msg):
            tab.log_console.append(msg)
            tab.log_console.ensureCursorVisible()

        def on_progress(val): tab.progress_bar.setValue(val)
        def on_candles(val): tab.card_candles.value_label.setText(f"{val:,}")
        
        def reset_start_btn():
            tab.btn_start.setEnabled(True)
            tab.btn_start.setText("🚀 РОЗПОЧАТИ ЗАВАНТАЖЕННЯ")
            tab.btn_start.setStyleSheet("QPushButton { background-color: #A6E3A1; color: #11111B; font-size: 14px; font-weight: bold; padding: 12px; border-radius: 6px; margin-top: 15px; }")

        def on_finished_ok(total):
            tab.card_candles.value_label.setText(f"{total:,}")
            tab.card_status.value_label.setText("COMPLETED (Успішно)")
            tab.card_status.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #A6E3A1;")
            tab.log_console.append("<br/><span style='color: #A6E3A1; font-weight: bold;'>🎉 ЗАВАНТАЖЕННЯ УСПІШНЕ!</span>")
            reset_start_btn()
            
            if hasattr(self.v.settings_tab, 'refresh_settings_assets'):
                self.v.settings_tab.refresh_settings_assets()
            # ВІДКЛЮЧЕНО: chart_tab тимчасово знятий з системи (див. VisualRegistry.py)
            # if hasattr(self.v.chart_tab, 'refresh_menus'):
            #     self.v.chart_tab.refresh_menus()

        def on_error(err):
            tab.card_status.value_label.setText("ERROR (Помилка)")
            tab.card_status.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #F38BA8;")
            tab.log_console.append(f"<br/><span style='color: #F38BA8; font-weight: bold;'>❌ Помилка:</span><br/>{err}")
            reset_start_btn()

        def start_downloading():
            if logic.worker and logic.worker.isRunning():
                tab.btn_start.setEnabled(False)
                tab.btn_start.setText("⏳ Зупинка...")
                logic.stop_download()
                return

            source = "massive" if tab.radio_massive.isChecked() else "exchange"
            exchange = tab.exchange_combo.currentText()
            symbols = tab.symbols_input.text().strip()
            
            tfs = [tf for tf, cb in tab.tf_checkboxes.items() if cb.isChecked()]
            start_ms = tab.date_start.dateTime().toMSecsSinceEpoch()
            end_ms = tab.date_end.dateTime().toMSecsSinceEpoch()

            if not symbols or not tfs or start_ms >= end_ms:
                tab.log_console.append("<span style='color: #F38BA8;'>❌ Помилка валідації!</span>")
                return

            tab.log_console.clear()
            tab.progress_bar.setValue(0)
            tab.card_candles.value_label.setText("0")
            db_name = "main.duckdb"
            tab.card_db.value_label.setText(db_name)
            tab.card_status.value_label.setText("ACTIVE (Завантаження)")
            tab.card_status.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #A6E3A1;")
            
            tab.btn_start.setText("🛑 ЗУПИНИТИ")
            tab.btn_start.setStyleSheet("QPushButton { background-color: #F38BA8; color: #11111B; font-size: 14px; font-weight: bold; padding: 12px; border-radius: 6px; margin-top: 15px; }")

            downloader_settings = self.l.settings.load_settings().get("downloader", {})
            massive_free_tier = downloader_settings.get("massive_free_tier", True)
            massive_free_requests = downloader_settings.get("massive_free_requests", 5)
            massive_free_wait_minutes = downloader_settings.get("massive_free_wait_minutes", 3)
            
            s = {
                "source_type": source, 
                "exchange": exchange, 
                "symbols": symbols, 
                "timeframes": tfs, 
                "start_ms": start_ms, 
                "end_ms": end_ms, 
                "massive_free_tier": massive_free_tier,
                "massive_free_requests": massive_free_requests,
                "massive_free_wait_minutes": massive_free_wait_minutes
            }
            worker = logic.start_download(s)
            worker.log_message.connect(on_log_message)
            worker.progress_update.connect(on_progress)
            worker.candles_updated.connect(on_candles)
            worker.finished_ok.connect(on_finished_ok)
            worker.finished_error.connect(on_error)
            worker.start()

        tab.btn_start.clicked.connect(start_downloading)

    # ----------------------------------
    # _bind_chart, зв'язування графіка
    # ----------------------------------
    # ВІДКЛЮЧЕНО: вкладка "Графік" тимчасово знята з системи (не викликається
    # з bind_all(), self.v.chart_tab більше не існує). Код нижче лишається
    # незмінним як довідка для майбутнього рефакторингу/оновлення вкладки.
    # Параметри: немає
    def _bind_chart(self):
        tab = self.v.chart_tab
        logic = self.l.chart
        self.initializing_chart = False
        self.locked_zoom_width = 210
        
        from PyQt6.QtGui import QAction
        import pandas as pd
        import os
        
        def load_chart(db_path, table_name):
            if hasattr(tab, 'chart') and tab.chart is not None:
                tab.chart.clear_markers()
            self.initializing_chart = True
            logic.request_initial_data_async(db_path, table_name)
            
        def on_reset_cam(sync=False):
            if hasattr(tab, 'chart') and tab.chart is not None:
                tab.chart.plot_item.autoBtnClicked()

        def on_chart_loaded(success):
            if success:
                tab.setup_chart(logic.df)
                update_trades_menu()
                
                # Підключаємо підгрузку свічок
                if hasattr(tab, 'chart') and tab.chart is not None:
                    tab.chart.request_more_data.connect(logic.request_more_data_async)
                    
                on_reset_cam(sync=False)
                # Safely reset initializing flag
                setattr(self, 'initializing_chart', False)
                
        logic.chart_loaded.connect(on_chart_loaded)
                
        def update_trades_menu():
            tab.show_trades_menu.clear()
            tables = logic.get_backtest_tables()
            if not tables:
                act = QAction(f"Немає бектестів", tab)
                act.setEnabled(False)
                tab.show_trades_menu.addAction(act)
                return
            
            for tbl in tables:
                act = QAction(f"{tbl.replace('backtest_', '')}", tab)
                act.triggered.connect(lambda checked, t=tbl: show_trades(t))
                tab.show_trades_menu.addAction(act)
                
        def show_trades(trades_table):
            if not logic.load_trades(trades_table):
                return

            import pandas as pd
            entries = pd.Series(index=logic.df.index, dtype=float)
            exits = pd.Series(index=logic.df.index, dtype=float)
            
            trades_list = []
            
            for _, trade in logic.trades_df.iterrows():
                try:
                    # parse entry safely
                    if pd.isna(trade.get('EntryTimestamp')): continue
                    entry_time = pd.to_datetime(trade['EntryTimestamp'], unit='ms')
                    
                    # parse exit safely
                    exit_time_val = trade.get('ExitTimestamp')
                    exit_time = pd.to_datetime(exit_time_val, unit='ms') if pd.notna(exit_time_val) and exit_time_val > 0 else pd.NaT
                    
                    # calculate duration
                    dur = 0
                    if pd.notna(exit_time_val) and exit_time_val > 0:
                        dur = exit_time_val - trade.get('EntryTimestamp', 0)
                        
                    t_dict = {
                        'entry_time': entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'exit_time': exit_time.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(exit_time) else "-",
                        'type': str(trade.get('TradeType', '')).upper(),
                        'status': 'CLOSED' if pd.notna(exit_time) else 'OPEN',
                        'pnl': float(trade.get('Profit', 0.0)) if pd.notna(trade.get('Profit')) else 0.0,
                        'id': str(trade.get('TradeNumber', '')),
                        'duration': int(dur / 60000)
                    }
                    trades_list.append(t_dict)
                    
                    if entry_time in logic.df.index:
                        high = logic.df.loc[entry_time, 'high']
                        entries.loc[entry_time] = high + (high * 0.0005)
                    if pd.notna(exit_time) and exit_time in logic.df.index:
                        low = logic.df.loc[exit_time, 'low']
                        exits.loc[exit_time] = low - (low * 0.0005)
                except Exception as e:
                    print(f"Skipped trade: {e}")
            tab.draw_trades(entries, exits)
            
            tab.sim_panel.update_trades(trades_list)
            tab.right_panel.show()
            tab.sim_panel.show()
            tab.detail_panel.hide()
            
        def on_x_range_changed(vb, xrange):
            pass # Panning is handled natively by Lightweight Charts
                
        def on_more_loaded(added):
            if added > 0:
                tab.update_chart_data(logic.df, added, logic.is_simulating)
                if tab.trades_drawn:
                    show_trades(logic.current_trades_table)
                # Ми більше не скидаємо камеру жорстко, бо update_chart_data тепер
                # плавно рухає камеру на added_count з підлаштуванням по Y.
                    
        logic.chart_more_loaded.connect(on_more_loaded)
                        
        def on_chart_clicked(time_str):
            if logic.trades_df is None or logic.df is None: return
            if not time_str: return
            
            try:
                click_time = pd.to_datetime(time_str)
            except:
                return
            
            trade = logic.find_nearest_trade(click_time)
            if trade is not None:
                dur_m = int((trade['ExitTimestamp'] - trade['EntryTimestamp']) / 60000)
                
                entry_time_str = pd.to_datetime(trade['EntryTimestamp'], unit='ms').strftime("%Y-%m-%d %H:%M:%S")
                exit_time_val = trade.get('ExitTimestamp')
                if pd.notna(exit_time_val) and exit_time_val > 0:
                    exit_time_str = pd.to_datetime(exit_time_val, unit='ms').strftime("%Y-%m-%d %H:%M:%S")
                else:
                    exit_time_str = "-"
                    
                tab.detail_panel.set_trade_details(
                    str(trade.get('TradeNumber', '-')),
                    str(trade.get('TradeType', '-')).upper(),
                    entry_time_str,
                    exit_time_str,
                    float(trade.get('Profit', 0)),
                    dur_m,
                    str(trade.get('Log', ''))
                )
                tab.detail_panel.show()
                tab.right_panel.show()
            else:
                tab.detail_panel.hide()
                
        tab.x_range_changed.connect(on_x_range_changed)
        tab.chart_clicked.connect(on_chart_clicked)
        
        def on_trade_selected_from_table(trade_dict):
            e_t = trade_dict.get('entry_time', '-')
            if isinstance(e_t, pd.Timestamp): e_t = e_t.strftime("%Y-%m-%d %H:%M:%S")
            x_t = trade_dict.get('exit_time', '-')
            if isinstance(x_t, pd.Timestamp): x_t = x_t.strftime("%Y-%m-%d %H:%M:%S")
            
            tab.detail_panel.set_trade_details(
                str(trade_dict.get('id', '-')),
                str(trade_dict.get('type', '-')),
                str(e_t),
                str(x_t),
                float(trade_dict.get('pnl', 0.0)),
                int(trade_dict.get('duration', 0)) if str(trade_dict.get('duration', '0')).replace('.','',1).isdigit() else 0,
                "Угода вибрана з таблиці"
            )
            tab.detail_panel.lbl_duration.setText(f"Статус: {trade_dict.get('status', '-')}")
            tab.detail_panel.show()
            tab.right_panel.show()
            
            # center chart
            if hasattr(tab.chart, 'go_to_time'):
                tab.chart.go_to_time(trade_dict.get('entry_time'))

        tab.sim_panel.trade_selected.connect(on_trade_selected_from_table)

        def on_lock_cam_toggled(checked):
            pass # Handled internally if needed
                
        tab.lock_cam_action.toggled.connect(on_lock_cam_toggled)

        def on_appearance_settings():
            from gui.visual.TabChartVisual import AppearanceSettingsDialog
            current_config = {
                'up_color': getattr(tab.chart, 'up_color', '#26a69a'),
                'down_color': getattr(tab.chart, 'down_color', '#ef5350'),
                'bg_color': getattr(tab.chart, 'bg_color', '#1e1f22'),
                'grid_color': getattr(tab.chart, 'grid_color', '#404040')
            }
            dialog = AppearanceSettingsDialog(current_config, tab)
            if dialog.exec():
                if hasattr(tab, 'chart') and tab.chart is not None:
                    tab.chart.apply_settings(dialog.config)
                    
        tab.appearance_action.triggered.connect(on_appearance_settings)
        
        from gui.visual.TabChartVisual import SimulationSettingsDialog
        tab.sim_dialog = SimulationSettingsDialog(tab)
        
        def on_clear_tests_clicked():
            count = logic.clear_temp_sim_tables()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(tab, "Очищення завершено", f"Успішно видалено {count} тимчасових таблиць тестів з бази даних.")
            
        tab.sim_dialog.btn_clear_tests.clicked.connect(on_clear_tests_clicked)
        
        def on_sim_settings():
            tab.sim_dialog.exec()
            
        def on_sim_toggle():
            if logic.is_simulating:
                logic.stop_simulation()
                tab.sim_toggle_action.setText("▶ Запустити симуляцію")
                tab.right_panel.hide()
                tab.sim_panel.hide()
            else:
                db_path = None
                table_name = None
                if tab._current_asset_nice and tab._current_tf:
                    db_path, table_name = tab.grouped_assets[tab._current_asset_nice][tab._current_tf]

                if db_path and table_name:
                    settings = tab.sim_dialog.get_settings()
                    strat_name = settings.get("strategy")
                    
                    success = logic.start_simulation(db_path, table_name, settings["range"], settings["multiplier"], strat_name)
                    if success:
                        tab.sim_toggle_action.setText("🛑 Зупинити симуляцію")
                        if strat_name and strat_name != "Без стратегії":
                            tab.right_panel.show()
                            tab.sim_panel.show()
                            tab.detail_panel.hide()

        tab.sim_settings_action.triggered.connect(on_sim_settings)
        tab.sim_toggle_action.triggered.connect(on_sim_toggle)
        
        def on_screenshot_requested():
            text = ""
            if getattr(tab, '_current_asset_nice', None) and getattr(tab, '_current_tf', None):
                text = f"{tab._current_asset_nice}, {tab._current_tf}"
                
            pixmap = tab.grab()
            if text:
                from PyQt6.QtGui import QPainter, QFont, QColor
                from PyQt6.QtCore import Qt
                painter = QPainter(pixmap)
                font = QFont("Arial", 26, QFont.Weight.Bold)
                painter.setFont(font)
                
                # Малюємо тінь тексту для контрасту
                painter.setPen(QColor(0, 0, 0, 180))
                painter.drawText(22, 62, text)
                
                # Малюємо основний текст
                painter.setPen(QColor(255, 255, 255, 230))
                painter.drawText(20, 60, text)
                
                painter.end()
                
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            import os
            from utils.PathManager import PathManager
            
            safe_text = text.replace(' ', '_').replace(',', '').replace('/', '_') if text else "chart"
            default_name = f"screenshot_{safe_text}.png"
            save_dir = os.path.join(PathManager.get_user_data_dir(), "screenshots")
            os.makedirs(save_dir, exist_ok=True)
            
            path, _ = QFileDialog.getSaveFileName(tab, "Зберегти скріншот", os.path.join(save_dir, default_name), "Images (*.png *.jpg)")
            if path:
                pixmap.save(path)
                QMessageBox.information(tab, "Успіх", f"Скріншот успішно збережено у:\n{path}")
                
        tab.screenshot_requested.connect(on_screenshot_requested)
        
        logic.sim_trades_updated.connect(tab.sim_panel.update_trades)
        
        import pandas as pd
        def on_sim_trade_event(event_type, timestamp, trade_type):
            dt = pd.to_datetime(timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
            if event_type == "OPEN":
                color = 'green' if trade_type == 'BUY' else 'red'
                shape = 'arrowUp' if trade_type == 'BUY' else 'arrowDown'
                tab.chart.add_marker(time_str, 'bottom' if trade_type=='BUY' else 'top', color, shape, 'ВХІД')
            else:
                color = 'purple'
                shape = 'circle'
                tab.chart.add_marker(time_str, 'top' if trade_type=='BUY' else 'bottom', color, shape, 'ВИХІД')
                
        logic.sim_trade_event.connect(on_sim_trade_event)
        
        def refresh_menus():
            tab.asset_menu.clear()
            tab.tf_menu.clear()
            
            assets = logic.get_available_assets()
            grouped_assets = {}
            for db, t in assets:
                parts = t.split('_')
                if len(parts) >= 2:
                    tf = parts[-1]
                    asset_raw = "_".join(parts[:-1])
                else:
                    tf = "1m"
                    asset_raw = t
                    
                if "_" in asset_raw:
                    asset_nice = asset_raw.replace("_", "/")
                else:
                    if len(asset_raw) == 6:
                        asset_nice = f"{asset_raw[:3]}/{asset_raw[3:]}"
                    else:
                        asset_nice = asset_raw
                        
                if asset_nice not in grouped_assets:
                    grouped_assets[asset_nice] = {}
                grouped_assets[asset_nice][tf] = (db, t)
                
            tab._current_asset_nice = None
            tab._current_tf = None
            
            def select_tf(tf):
                if not tab._current_asset_nice: return
                tab._current_tf = tf
                db, tbl = grouped_assets[tab._current_asset_nice][tf]
                load_chart(db, tbl)
                
                tab.tf_menu.clear()
                for available_tf in sorted(grouped_assets[tab._current_asset_nice].keys()):
                    act = QAction(available_tf, tab)
                    act.setCheckable(True)
                    act.setChecked(available_tf == tf)
                    act.triggered.connect(lambda checked, t=available_tf: select_tf(t))
                    tab.tf_menu.addAction(act)
                    
                for act in tab.asset_menu.actions():
                    act.setChecked(act.text() == tab._current_asset_nice)
            
            def select_asset(asset_nice):
                tab._current_asset_nice = asset_nice
                tfs = grouped_assets[asset_nice]
                if "15m" in tfs:
                    pref_tf = "15m"
                elif "1m" in tfs:
                    pref_tf = "1m"
                else:
                    pref_tf = list(tfs.keys())[0]
                select_tf(pref_tf)
                
            tab.grouped_assets = grouped_assets
            
            for asset_nice in sorted(grouped_assets.keys()):
                act = QAction(asset_nice, tab)
                act.setCheckable(True)
                act.triggered.connect(lambda checked, a=asset_nice: select_asset(a))
                tab.asset_menu.addAction(act)
                
            if grouped_assets:
                first_asset = sorted(grouped_assets.keys())[0]
                select_asset(first_asset)
                
        tab.refresh_menus = refresh_menus
        tab.refresh_menus()

    # ----------------------------------
    # _bind_backtest, зв'язування бектесту
    # ----------------------------------
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    # ВІДКЛЮЧЕНО (BACKTEST): вкладка "Тестер стратегій" тимчасово знята з
    # системи, підлягає рефакторингу й оновленню. Цей метод більше НЕ
    # викликається з bind_all() (виклик закоментовано вище) — код тіла
    # лишається незмінним нижче як довідка на майбутнє. Пов'язані блоки:
    # gui/visual/VisualRegistry.py, gui/logic/LogicRegistry.py, gui/MainWindow.py.
    # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
    def _bind_backtest(self):
        tab = self.v.backtest_tab
        logic = self.l.backtest
        
        import os
        import time
        from PyQt6.QtWidgets import QDialog
        from gui.logic.BacktestLogic import BacktestWorker, AutoLearnWorker, WfvWorker
        
        # Ініціалізація UI меню
        tab.build_categories(logic.meta_data, logic.copilot)
        
        for ind_id, data in tab.param_widgets.items():
            if data["meta"].get("class") == "CopilotSetting":
                data["checkbox"].stateChanged.connect(lambda checked: tab.update_editor_code(logic.copilot))
            else:
                data["checkbox"].stateChanged.connect(lambda checked: tab.update_editor_code(logic.copilot))
            for w in data["params"].values():
                if hasattr(w, 'valueChanged'): w.valueChanged.connect(lambda val: tab.update_editor_code(logic.copilot))
                elif hasattr(w, 'textChanged'): w.textChanged.connect(lambda text: tab.update_editor_code(logic.copilot))

        # Завантаження таблиць
        def refresh_backtest_menus():
            tab.table_combo.blockSignals(True)
            tab.table_combo.clear()
            tab.timeframe_combo.clear()
            
            assets = self.l.chart.get_available_assets()
            grouped_assets = {}
            for db, t in assets:
                parts = t.split('_')
                if len(parts) >= 2:
                    tf = parts[-1]
                    asset_raw = "_".join(parts[:-1])
                else:
                    tf = "1m"
                    asset_raw = t
                    
                if "_" in asset_raw:
                    asset_nice = asset_raw.replace("_", "/")
                else:
                    if len(asset_raw) == 6:
                        asset_nice = f"{asset_raw[:3]}/{asset_raw[3:]}"
                    else:
                        asset_nice = asset_raw
                        
                if asset_nice not in grouped_assets:
                    grouped_assets[asset_nice] = {}
                grouped_assets[asset_nice][tf] = t
                
            tab._backtest_grouped = grouped_assets
            
            for asset_nice in sorted(grouped_assets.keys()):
                tab.table_combo.addItem(asset_nice, checked=False)
            tab.table_combo.blockSignals(False)
            on_asset_changed()
                
        def on_asset_changed():
            checked = tab.table_combo.checkedItems()
            if not checked:
                asset_nice = tab.table_combo.currentText()
                if not asset_nice or asset_nice not in getattr(tab, '_backtest_grouped', {}):
                    return
            else:
                asset_nice = checked[0]
                
            if not hasattr(tab, '_backtest_grouped') or asset_nice not in tab._backtest_grouped:
                return
            
            tab.timeframe_combo.blockSignals(True)
            tab.timeframe_combo.clear()
            tfs = tab._backtest_grouped[asset_nice]
            for tf in sorted(tfs.keys()):
                tab.timeframe_combo.addItem(tf)
                
            if "15m" in tfs:
                tab.timeframe_combo.setCurrentText("15m")
            elif "1m" in tfs:
                tab.timeframe_combo.setCurrentText("1m")
            
            tab.timeframe_combo.blockSignals(False)

        tab.table_combo.currentTextChanged.connect(on_asset_changed)
        tab.refresh_menus = refresh_backtest_menus
        tab.refresh_menus()
        
        from utils.PathManager import PathManager
        strat_dir = PathManager.get_strategies_dir()
        
        def refresh_strategies_combo():
            tab.strat_combo.blockSignals(True)
            tab.strat_combo.clear()
            tab.strat_combo.blockSignals(False)
            tab._strategies_map = {}
            for root, dirs, files in os.walk(strat_dir):
                for file in files:
                    if file.endswith('.py') and not file.startswith('__'):
                        rel_path = os.path.relpath(os.path.join(root, file), strat_dir)
                        rel_path = rel_path.replace("\\", "/")
                        tab.strat_combo.addItem(rel_path, checked=False)
                        tab._strategies_map[rel_path] = os.path.join(root, file)
                        
        refresh_strategies_combo()
        
        tab.btn_save.clicked.connect(lambda: [tab.save_strategy(strat_dir), refresh_strategies_combo()])
        tab.btn_load.clicked.connect(lambda: tab.load_strategy(strat_dir, logic.copilot))
        tab.btn_delete.clicked.connect(lambda: [tab.delete_strategy(strat_dir), refresh_strategies_combo()])
        tab.btn_info.clicked.connect(tab.show_help_dialog)
        
        def run_backtest():
            tab.log_output.clear()
            tab.safe_append_html("<div style='font-family: monospace; font-size: 13px; line-height: 1.4; margin-bottom: 10px;'><p style='color: #0a84ff; font-weight: bold; margin-bottom: 5px;'>🚀 ЗАПУСК БЕКТЕСТУ</p><hr style='border: 0; border-top: 1px solid #444; margin-top: 2px; margin-bottom: 8px;'/></div>")
            
            db_name = "main.duckdb"
            checked_assets = tab.table_combo.checkedItems()
            tf = tab.timeframe_combo.currentText()
            
            if not checked_assets:
                if hasattr(tab, '_backtest_grouped') and len(tab._backtest_grouped) > 0:
                    # Якщо нічого не обрано, беремо перший доступний актив
                    checked_assets = [list(tab._backtest_grouped.keys())[0]]
                else:
                    tab.safe_append_html("<div style='color: #ff453a; font-family: monospace; font-weight: bold;'>❗ Оберіть хоча б один Актив!</div><br>")
                    return
                    
            if not tf and hasattr(tab, '_backtest_grouped') and tab._backtest_grouped.get(checked_assets[0]):
                tf = list(tab._backtest_grouped[checked_assets[0]].keys())[0]
                
            if not tf or not hasattr(tab, '_backtest_grouped'):
                return
                
            table_names = []
            for asset in checked_assets:
                if asset in tab._backtest_grouped and tf in tab._backtest_grouped[asset]:
                    table_names.append(tab._backtest_grouped[asset][tf])
                    
            if not table_names: return
                
            checked_strats = tab.strat_combo.checkedItems()
            codes = {}
            
            if checked_strats:
                for strat_name in checked_strats:
                    path = tab._strategies_map.get(strat_name)
                    if path and os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            codes[strat_name.replace('.py', '').replace('/', '_')] = f.read()
            else:
                code = tab.code_editor.toPlainText()
                if "strategy = Strategy(" not in code:
                    tab.safe_append_html("<div style='color: #ff453a; font-family: monospace; font-weight: bold;'>❗ У коді редактора відсутній об'єкт Strategy!</div><br>")
                    return
                codes["custom_code"] = code
                
            user_test_name = tab.test_name_input.text().strip()
            if not user_test_name:
                user_test_name = f"test_{int(time.time())}"
                tab.test_name_input.setText(user_test_name)
            test_name = f"backtest_{user_test_name}"
            
            tab.btn_run.setEnabled(False)
            tab.btn_run.setText("⏳ Розраховується...")
            tab.btn_show_chart.setEnabled(False)
            
            assets_str = ", ".join(checked_assets)
            strats_str = ", ".join(codes.keys())
            tab.safe_append_html(f"<div style='font-family: monospace; font-size: 13px; color: #e5e5ea;'><span style='color: #30d158; font-weight: bold;'>{db_name}</span> | <span style='color: #64d2ff; font-weight: bold;'>{assets_str}</span> | <span style='color: #ffd60a; font-weight: bold;'>{strats_str}</span> | <span style='color: #ff9f0a; font-weight: bold;'>{test_name}</span></div>")
            
            tab._worker = BacktestWorker(codes, "main.duckdb", table_names, test_name, copilot=logic.copilot, parent=tab)
            tab._worker.log_message.connect(lambda m: tab.safe_append_html(f"<div style='color: #e5e5ea; font-family: monospace; font-size: 13px;'>{m}</div>"))
            tab._worker.finished_ok.connect(lambda t, a: on_backtest_done(t, a, tab._worker.prediction_context))
            tab._worker.finished_error.connect(lambda e: on_backtest_error(e))
            tab._worker.start()
            
        def on_backtest_done(table_name, asset_name, prediction_context):
            tab.safe_append_html(f"<div style='font-family: monospace; font-size: 13px;'><hr style='border: 0; border-top: 1px solid #444;'/><span style='color: #32d74b; font-weight: bold;'>✅ Бектест завершено!</span><br><span style='color: #8e8e93;'>Результати збережено в таблицю:</span> <span style='color: #64d2ff; font-weight: bold;'>{table_name}</span></div>")
            tab.btn_run.setEnabled(True)
            tab.btn_run.setText("▶ Розрахувати")
            tab.last_table_name = table_name
            tab.last_asset_name = asset_name
            tab.btn_show_chart.setEnabled(True)
            
            if prediction_context:
                logic.last_run_context = {
                    "context": {"asset": prediction_context.get("asset"), "timeframe": prediction_context.get("asset", "").split("_")[-1] if "_" in prediction_context.get("asset", "") else "1h"},
                    "indicators": prediction_context.get("indicators_used", []),
                    "logic_snapshot": prediction_context.get("logic_snapshot", {})
                }
                try:
                    mock_perf = {"win_rate": 50.0, "profit_factor": 1.0}
                    logic.copilot.record_backtest_result(
                        context=logic.last_run_context["context"], indicators=logic.last_run_context["indicators"],
                        performance=mock_perf, note=f"Запис після тесту на {table_name}",
                        logic_snapshot=logic.last_run_context.get("logic_snapshot", {})
                    )
                except: pass
                
        def on_backtest_error(error_msg):
            tab.safe_append_html(f"<div style='font-family: monospace; font-size: 13px;'><hr style='border: 0; border-top: 1px solid #ff453a;'/><span style='color: #ff453a; font-weight: bold;'>❌ Помилка бектесту:</span><br><pre style='color: #ff9f0a;'>{error_msg}</pre></div>")
            tab.btn_run.setEnabled(True)
            tab.btn_run.setText("▶ Розрахувати")
            
        def show_chart():
            table = getattr(tab, "last_table_name", None)
            asset = getattr(tab, "last_asset_name", None)
            if table and asset: tab.request_show_chart.emit("main.duckdb", table, asset)
            
        tab.btn_run.clicked.connect(run_backtest)
        tab.btn_show_chart.clicked.connect(show_chart)
        
        # Підключення Auto Learn
        def on_auto_learn_clicked():
            if hasattr(tab, "_auto_worker") and tab._auto_worker.isRunning():
                tab._auto_worker.stop()
                tab.btn_auto_learn.setText("🛑 ЗУПИНКА...")
                tab.btn_auto_learn.setEnabled(False)
                return
                
            checked_assets = tab.table_combo.checkedItems()
            if not checked_assets:
                if hasattr(tab, '_backtest_grouped') and len(tab._backtest_grouped) > 0:
                    # Якщо нічого не обрано, беремо перший доступний актив
                    checked_assets = [list(tab._backtest_grouped.keys())[0]]
                else:
                    tab.safe_append_html("<div style='color: #ff453a; font-weight: bold;'>❗ Оберіть хоча б один Актив для Авто-навчання!</div><br>")
                    return
            
            # Для Auto Learn беремо тільки перший вибраний актив як основний для генерації (оскільки він сам мультитестує)
            asset_nice = checked_assets[0]
            tf = tab.timeframe_combo.currentText()
            if not tf and tab._backtest_grouped.get(asset_nice):
                tf = list(tab._backtest_grouped[asset_nice].keys())[0]
                
            table_name = tab._backtest_grouped[asset_nice].get(tf)
            if not table_name: return
            
            tab.log_output.clear()
            tab.btn_auto_learn.setText("🛑 ЗУПИНИТИ АВТО НАВЧАННЯ")
            tab.btn_auto_learn.setStyleSheet("background-color: #ff453a; color: white; font-weight: bold; padding: 8px;")
            
            count = tab.ai_learn_count.value()
            direction = "MIXED"
            if "BUY" in tab.ai_direction_combo.currentText(): direction = "BUY"
            elif "SELL" in tab.ai_direction_combo.currentText(): direction = "SELL"
            
            tab._auto_worker = AutoLearnWorker("main.duckdb", table_name, logic.meta_data, total_runs=count, direction_mode=direction, parent=tab)
            tab._auto_worker.log_message.connect(lambda m: tab.safe_append_html(f"<div style='color: #e5e5ea; font-family: monospace; font-size: 13px;'>{m}</div><br>"))
            
            def on_finished():
                tab.btn_auto_learn.setText("🧠 ЗАПУСТИТИ АВТО НАВЧАННЯ")
                tab.btn_auto_learn.setStyleSheet("background-color: #bf5af2; color: white; font-weight: bold; padding: 8px;")
                tab.btn_auto_learn.setEnabled(True)
                tab.safe_append_html("<div style='color: #32d74b; font-weight: bold;'><br>✅ АВТО НАВЧАННЯ ЗАВЕРШЕНО!</div><br>")
                
            tab._auto_worker.finished.connect(on_finished)
            tab._auto_worker.start()
            
        tab.btn_auto_learn.clicked.connect(on_auto_learn_clicked)
        
        # Підключення WFV
        def on_wfv_clicked():
            tab.log_output.clear()
            
            # Отримуємо таблиці
            checked_assets = tab.table_combo.checkedItems()
            tf = tab.timeframe_combo.currentText()
            
            if not checked_assets:
                if hasattr(tab, '_backtest_grouped') and len(tab._backtest_grouped) > 0:
                    checked_assets = [list(tab._backtest_grouped.keys())[0]]
                else:
                    tab.safe_append_html("<div style='color: #ff453a; font-weight: bold;'>❗ Оберіть хоча б один Актив!</div><br>")
                    return
            
            if not tf and hasattr(tab, '_backtest_grouped') and tab._backtest_grouped.get(checked_assets[0]):
                tf = list(tab._backtest_grouped[checked_assets[0]].keys())[0]
                
            table_names = []
            for asset in checked_assets:
                if asset in tab._backtest_grouped and tf in tab._backtest_grouped[asset]:
                    table_names.append(tab._backtest_grouped[asset][tf])
                    
            if not table_names: return
            
            # Отримуємо коди стратегій
            checked_strats = tab.strat_combo.checkedItems()
            codes = {}
            if checked_strats:
                for strat_name in checked_strats:
                    path = tab._strategies_map.get(strat_name)
                    if path and os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            codes[strat_name.replace('.py', '').replace('/', '_')] = f.read()
            else:
                code = tab.code_editor.toPlainText()
                if "strategy = Strategy(" not in code:
                    tab.safe_append_html("<div style='color: #ff453a; font-weight: bold;'>❗ У коді редактора відсутній об'єкт Strategy!</div><br>")
                    return
                codes["custom_code"] = code

            assets_str = ", ".join(checked_assets)
            strats_str = ", ".join(codes.keys())
            tab.safe_append_html(f"<div style='color: #A6ADC8; font-family: monospace; font-weight: bold;'>🔄 Запуск WFV для: {assets_str} | Стратегії: {strats_str}</div><br>")
            
            tab.btn_run_wfv.setEnabled(False)
            tab.btn_run.setEnabled(False)
            
            tab._wfv_worker = WfvWorker(codes, "main.duckdb", table_names, parent=tab)
            tab._wfv_worker.log_message.connect(lambda m: tab.safe_append_html(m))
            
            def on_finished():
                tab.btn_run_wfv.setEnabled(True)
                tab.btn_run.setEnabled(True)
                
            tab._wfv_worker.finished.connect(on_finished)
            tab._wfv_worker.start()
            
        tab.btn_run_wfv.clicked.connect(on_wfv_clicked)

    # ----------------------------------

    # ----------------------------------
    # _bind_copilot, зв'язування вкладки Copilot
    # ----------------------------------
    def _bind_copilot(self):
        tab = self.v.copilot_tab
        logic = self.l.copilot
        
        from PyQt6.QtCore import QTimer
        
        logic.service.log_update.connect(lambda text: tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] {text}"))
        
        def on_start_auto():
            tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] 🚀 Запуск автономного планувальника Копілота...")
            tab.btn_active.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #11111B; background-color: #F9E2AF; border-radius: 6px; padding: 8px 16px; }")
            tab.btn_active.setText("⏳ RUNNING")
            
            config_states = {
                "cb_auto_mode": tab.cb_auto_mode.isChecked(),
                "cb_auto_gen": tab.cb_auto_gen.isChecked(),
                "cb_download_ccxt": tab.cb_download_ccxt.isChecked(),
                "cb_download_massive": tab.cb_download_massive.isChecked(),
                "cb_gen_signals": tab.cb_gen_signals.isChecked()
            }
            
            logic.start_auto_routine(config_states)
            
        def on_stop_auto():
            tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] 🛑 Зупинка автономного планувальника...")
            tab.btn_active.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #11111B; background-color: #A6E3A1; border-radius: 6px; padding: 8px 16px; } QPushButton:hover { background-color: #94E2D5; }")
            tab.btn_active.setText("● ACTIVE")
            logic.stop_auto_routine()
            
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction

        def add_task_to_list(task_name):
            tab.tasks_list.addItem(task_name)
            tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] Додано задачу: {task_name}")

        def show_add_task_menu():
            menu = QMenu(tab)
            for t in ["Аналіз прогалин", "Авто-завантаження", "Генерація стратегій", "Очищення бази"]:
                act = QAction(t, tab)
                act.triggered.connect(lambda checked, name=t: add_task_to_list(name))
                menu.addAction(act)
            menu.exec(tab.btn_add_task.mapToGlobal(tab.btn_add_task.rect().bottomLeft()))

        def run_next_task():
            if tab.tasks_list.count() == 0:
                tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] 🎉 Усі задачі в черзі виконано.")
                tab.btn_start_task.setEnabled(True)
                return
            
            item = tab.tasks_list.takeItem(0)
            task_name = item.text()
            tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] ▶ Виконується задача: {task_name}")
            
            use_ccxt = tab.cb_download_ccxt.isChecked()
            use_massive = tab.cb_download_massive.isChecked()
            
            if task_name == "Аналіз прогалин":
                logic.analyze_database(False, False)
            elif task_name == "Авто-завантаження":
                logic.analyze_database(use_ccxt, use_massive)
            elif task_name == "Генерація стратегій":
                config_states = {
                    "cb_auto_mode": False,
                    "cb_auto_gen": True,
                    "cb_download_ccxt": False,
                    "cb_download_massive": False,
                    "cb_gen_signals": False
                }
                logic.start_auto_routine(config_states)
                logic.service.task_finished.emit("strategy_gen")
            elif task_name == "Очищення бази":
                tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] Очищення бази успішно імітовано.")
                logic.service.task_finished.emit("cleanup")
            else:
                logic.service.task_finished.emit("unknown")

        def start_task_queue():
            if tab.tasks_list.count() > 0:
                tab.btn_start_task.setEnabled(False)
                run_next_task()
            
        tab.btn_active.clicked.connect(on_start_auto)
        tab.btn_stop.clicked.connect(on_stop_auto)
        tab.btn_start_task.clicked.connect(start_task_queue)
        tab.btn_add_task.clicked.connect(show_add_task_menu)
        logic.service.task_finished.connect(lambda task_type: run_next_task())
        
        # Оновлення статистики
        logic.stats_ready.connect(tab.update_stats_ui)
        
        tab.stats_timer = QTimer(tab)
        tab.stats_timer.timeout.connect(logic.request_stats_async)
        tab.stats_timer.start(10000)
        QTimer.singleShot(500, logic.request_stats_async)

    # ----------------------------------
    # _bind_live_algo, зв'язування вкладки Авто-Трейдінг
    # ----------------------------------
    def _bind_live_algo(self):
        tab = self.v.live_algo_tab
        logic = self.l.live_algo
        
        def on_analyze():
            assets = [a.strip() for a in tab.assets_input.text().split(',') if a.strip()]
            if not assets:
                return
            tab.show_loading()
            logic.request_analysis(assets, tab.display_results)
            
        tab.btn_analyze.clicked.connect(on_analyze)

    # ----------------------------------
    # attach_to_tabs, додавання вкладок до QTabWidget
    # ----------------------------------
    # Параметри:
    # tabs_widget (QTabWidget): Віджет вкладок для додавання створених сторінок
    def attach_to_tabs(self, tabs_widget: QTabWidget):
        tabs_widget.addTab(self.v.explorer_tab, "Провідник БД")
        tabs_widget.addTab(self.v.downloader_tab, "Завантаження даних")
        # ВІДКЛЮЧЕНО: вкладка "Графік" тимчасово знята з системи, підлягає
        # рефакторингу й оновленню.
        # tabs_widget.addTab(self.v.chart_tab, "Графік (finplot)")
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # ВІДКЛЮЧЕНО (BACKTEST): вкладка "Тестер стратегій" тимчасово знята
        # з системи, підлягає рефакторингу й оновленню.
        # !_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!_!
        # tabs_widget.addTab(self.v.backtest_tab, "Тестер стратегій")
        tabs_widget.addTab(self.v.copilot_tab, "Автономний Копілот")
        tabs_widget.addTab(self.v.live_algo_tab, "Авто-Трейдінг (NN)")
        tabs_widget.addTab(self.v.settings_tab, "Налаштування")
