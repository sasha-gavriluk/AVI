from datetime import datetime
from PyQt6.QtWidgets import QTabWidget, QMessageBox, QPushButton, QComboBox, QTreeWidgetItem
from PyQt6.QtCore import Qt, QDateTime
from gui.visual.VisualRegistry import VisualRegistry
from gui.logic.LogicRegistry import LogicRegistry


def _timestamp() -> str:
    """Часова мітка для рядків логу, формат [ГГ:ХХ:СС]."""
    return datetime.now().strftime('%H:%M:%S')


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
        # Вкладки "Графік" і "Тестер стратегій" тимчасово відсутні —
        # _bind_chart()/_bind_backtest() видалені (Code/REFACTOR_LOG.md,
        # старий код у git-коміті 0eeea95).
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
            tab.tree_view.addTopLevelItem(QTreeWidgetItem(["Завантаження..."]))
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
            from PyQt6.QtWidgets import QFileDialog
            import os
            from utils.PathManager import PathManager

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

    # Методи _bind_chart() і _bind_backtest() видалено — вкладки
    # "Графік" і "Тестер стратегій" тимчасово відсутні в системі.
    # Довідка: Code/REFACTOR_LOG.md, старий код — git-коміт 0eeea95.

    # ----------------------------------
    # _bind_copilot, зв'язування вкладки Copilot
    # ----------------------------------
    def _bind_copilot(self):
        tab = self.v.copilot_tab
        logic = self.l.copilot
        
        from PyQt6.QtCore import QTimer
        
        logic.service.log_update.connect(lambda text: tab.log_console.append(f"[{_timestamp()}] {text}"))
        
        def on_start_auto():
            tab.log_console.append(f"[{_timestamp()}] 🚀 Запуск автономного планувальника Копілота...")
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
            tab.log_console.append(f"[{_timestamp()}] 🛑 Зупинка автономного планувальника...")
            tab.btn_active.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #11111B; background-color: #A6E3A1; border-radius: 6px; padding: 8px 16px; } QPushButton:hover { background-color: #94E2D5; }")
            tab.btn_active.setText("● ACTIVE")
            logic.stop_auto_routine()
            
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction

        def add_task_to_list(task_name):
            tab.tasks_list.addItem(task_name)
            tab.log_console.append(f"[{_timestamp()}] Додано задачу: {task_name}")

        def show_add_task_menu():
            menu = QMenu(tab)
            for t in ["Аналіз прогалин", "Авто-завантаження", "Генерація стратегій", "Очищення бази"]:
                act = QAction(t, tab)
                act.triggered.connect(lambda checked, name=t: add_task_to_list(name))
                menu.addAction(act)
            menu.exec(tab.btn_add_task.mapToGlobal(tab.btn_add_task.rect().bottomLeft()))

        def run_next_task():
            if tab.tasks_list.count() == 0:
                tab.log_console.append(f"[{_timestamp()}] 🎉 Усі задачі в черзі виконано.")
                tab.btn_start_task.setEnabled(True)
                return
            
            item = tab.tasks_list.takeItem(0)
            task_name = item.text()
            tab.log_console.append(f"[{_timestamp()}] ▶ Виконується задача: {task_name}")
            
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
                tab.log_console.append(f"[{_timestamp()}] Очищення бази успішно імітовано.")
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
        tabs_widget.addTab(self.v.copilot_tab, "Автономний Копілот")
        tabs_widget.addTab(self.v.live_algo_tab, "Авто-Трейдінг (NN)")
        tabs_widget.addTab(self.v.settings_tab, "Налаштування")
