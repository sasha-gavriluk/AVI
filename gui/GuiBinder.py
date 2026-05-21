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
        self.bind_all()

    # ----------------------------------
    # bind_all, виклик всіх методів зв'язування
    # ----------------------------------
    # Параметри: немає
    def bind_all(self):
        self._bind_settings()
        self._bind_explorer()
        self._bind_downloader()
        self._bind_chart()
        self._bind_backtest()
        self._bind_copilot()
        self._bind_live_trading()
        
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
        tab.bo_payout_input.setValue(data["trading_mode"]["bo_payout_percent"])
        tab.bo_bet_input.setValue(data["trading_mode"]["bo_bet_size"])
        tab.bo_exp_input.setValue(data["trading_mode"]["bo_expiration_bars"])
        
        tab.stop_loss_input.setValue(data["risk_management"]["stop_loss_percent"])
        tab.max_drawdown_input.setValue(data["risk_management"]["max_drawdown_session"])
        tab.daily_loss_input.setValue(data["risk_management"]["daily_loss_limit"])
        
        tab.half_life_input.setValue(data["copilot"]["half_life_days"])
        tab.min_score_input.setValue(data["copilot"]["min_score_for_best"])
        tab.routine_interval_input.setValue(data["copilot"].get("routine_interval_hours", 1.0))
        
        keys = logic.load_api_keys()
        tab.bybit_key_input.setText(keys.get("BYBIT_KEY", ""))
        tab.bybit_secret_input.setText(keys.get("BYBIT_SECRET_KEY", ""))
        tab.binance_key_input.setText(keys.get("BINANCE_KEY", ""))
        tab.binance_secret_input.setText(keys.get("BINANCE_SECRET_KEY", ""))
        tab.massive_key_input.setText(keys.get("MASSIVE_KEY", ""))

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
                    "bo_expiration_bars": tab.bo_exp_input.value()
                },
                "risk_management": {
                    "stop_loss_percent": tab.stop_loss_input.value(),
                    "max_drawdown_session": tab.max_drawdown_input.value(),
                    "daily_loss_limit": tab.daily_loss_input.value()
                },
                "copilot": {
                    "half_life_days": tab.half_life_input.value(),
                    "min_score_for_best": tab.min_score_input.value(),
                    "routine_interval_hours": tab.routine_interval_input.value()
                }
            }
            logic.save_settings(new_data)
            
            new_keys = {
                "BYBIT_KEY": tab.bybit_key_input.text(),
                "BYBIT_SECRET_KEY": tab.bybit_secret_input.text(),
                "BINANCE_KEY": tab.binance_key_input.text(),
                "BINANCE_SECRET_KEY": tab.binance_secret_input.text(),
                "MASSIVE_KEY": tab.massive_key_input.text()
            }
            logic.save_api_keys(new_keys)

        tab.mode_combo.currentTextChanged.connect(save_from_ui)
        tab.bo_payout_input.valueChanged.connect(save_from_ui)
        tab.bo_bet_input.valueChanged.connect(save_from_ui)
        tab.bo_exp_input.valueChanged.connect(save_from_ui)
        tab.stop_loss_input.valueChanged.connect(save_from_ui)
        tab.max_drawdown_input.valueChanged.connect(save_from_ui)
        tab.daily_loss_input.valueChanged.connect(save_from_ui)
        tab.half_life_input.valueChanged.connect(save_from_ui)
        tab.min_score_input.valueChanged.connect(save_from_ui)
        tab.routine_interval_input.valueChanged.connect(save_from_ui)
        tab.bybit_key_input.textChanged.connect(save_from_ui)
        tab.bybit_secret_input.textChanged.connect(save_from_ui)
        tab.binance_key_input.textChanged.connect(save_from_ui)
        tab.binance_secret_input.textChanged.connect(save_from_ui)
        tab.massive_key_input.textChanged.connect(save_from_ui)

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
            top_presets = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"] if is_massive else ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
            
            for p in top_presets:
                btn = QPushButton(p)
                btn.setStyleSheet("QPushButton { background-color: #313244; color: #CDD6F4; font-size: 11px; padding: 3px 6px; border-radius: 3px; }")
                btn.clicked.connect(lambda checked, symbol=p: append_symbol(symbol))
                tab.presets_row.addWidget(btn)
                
            all_presets = [
                "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", 
                "EURGBP", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD", "SPX500", "NAS100", 
                "US30", "GER30", "UK100", "BTCUSD", "ETHUSD", "SOLUSD"
            ] if is_massive else [
                "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", 
                "DOTUSDT", "DOGEUSDT", "SHIBUSDT", "LINKUSDT", "LTCUSDT", "UNIUSDT", 
                "NEARUSDT", "FILUSDT", "ATOMUSDT", "ICPUSDT", "APTUSDT", "OPUSDT", 
                "ARBUSDT", "INJUSDT"
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
            if is_massive: tab.symbols_input.setText("EURUSD, GBPUSD")
            else: tab.symbols_input.setText("BTCUSDT, ETHUSDT")
            update_symbol_presets()

        tab.radio_massive.toggled.connect(on_source_changed)
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
            db_name = "trading_data_massive.duckdb" if source == "massive" else f"{exchange.lower()}_data.duckdb"
            tab.card_db.value_label.setText(db_name)
            tab.card_status.value_label.setText("ACTIVE (Завантаження)")
            tab.card_status.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #A6E3A1;")
            
            tab.btn_start.setText("🛑 ЗУПИНИТИ")
            tab.btn_start.setStyleSheet("QPushButton { background-color: #F38BA8; color: #11111B; font-size: 14px; font-weight: bold; padding: 12px; border-radius: 6px; margin-top: 15px; }")

            s = {"source_type": source, "exchange": exchange, "symbols": symbols, "timeframes": tfs, "start_ms": start_ms, "end_ms": end_ms}
            worker = logic.start_download(s)
            worker.log_message.connect(on_log_message)
            worker.progress_update.connect(on_progress)
            worker.candles_updated.connect(on_candles)
            worker.finished_ok.connect(on_finished_ok)
            worker.finished_error.connect(on_error)

        tab.btn_start.clicked.connect(start_downloading)

    # ----------------------------------
    # _bind_chart, зв'язування графіка
    # ----------------------------------
    # Параметри: немає
    def _bind_chart(self):
        tab = self.v.chart_tab
        logic = self.l.chart
        
        from PyQt6.QtGui import QAction
        import pandas as pd
        import os
        
        def load_chart(db_path, table_name):
            if tab.ax is not None:
                tab.ax.clear()
            logic.request_initial_data_async(db_path, table_name)
            
        def on_chart_loaded(success):
            if success:
                tab.setup_chart(logic.df)
                update_trades_menu()
                
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
            
            entries = pd.Series(index=logic.df.index, dtype=float)
            exits = pd.Series(index=logic.df.index, dtype=float)
            for _, trade in logic.trades_df.iterrows():
                try:
                    entry_time = pd.to_datetime(trade['EntryTimestamp'], unit='ms')
                    exit_time = pd.to_datetime(trade['ExitTimestamp'], unit='ms')
                    if entry_time in logic.df.index:
                        high = logic.df.loc[entry_time, 'high']
                        entries.loc[entry_time] = high + (high * 0.0005)
                    if exit_time in logic.df.index:
                        low = logic.df.loc[exit_time, 'low']
                        exits.loc[exit_time] = low - (low * 0.0005)
                except Exception:
                    pass
            tab.draw_trades(entries, exits)
            
        def on_x_range_changed(vb, xrange):
            if xrange[0] < 100 and not logic.is_loading:
                logic.request_more_data_async()
                
        def on_more_loaded(added):
            if added > 0:
                tab.update_chart_data(logic.df, added)
                if tab.trades_drawn:
                    show_trades(logic.current_trades_table)
                    
        logic.chart_more_loaded.connect(on_more_loaded)
                        
        def on_chart_clicked(event):
            if event.button() != 1: return
            if logic.trades_df is None or logic.df is None: return
            
            pos = event.scenePos()
            view_coords = tab.ax.vb.mapSceneToView(pos)
            x_idx = int(round(view_coords.x()))
            
            if x_idx < 0 or x_idx >= len(logic.df): return
            click_time = logic.df.index[x_idx]
            
            trade = logic.find_nearest_trade(click_time)
            if trade is not None:
                dur_m = int((trade['ExitTimestamp'] - trade['EntryTimestamp']) / 60000)
                tab.detail_panel.set_trade_details(
                    str(trade.get('TradeID', '-')),
                    str(trade.get('Direction', '-')),
                    float(trade.get('Profit', 0)),
                    dur_m,
                    str(trade.get('Log', ''))
                )
                tab.detail_panel.show()
            else:
                tab.detail_panel.hide()
                
        def on_reset_cam():
            if tab.ax and logic.df is not None and not logic.df.empty:
                import finplot as fplt
                def _do_reset():
                    x_max = len(logic.df) - 1
                    x_min = max(0, x_max - 150)
                    visible = logic.df.iloc[x_min : x_max+1]
                    y_min = visible['low'].min()
                    y_max = visible['high'].max()
                    pad = (y_max - y_min) * 0.1
                    tab.ax.vb.setXRange(x_min, x_max + 10, padding=0)
                    tab.ax.vb.setYRange(y_min - pad, y_max + pad, padding=0)
                fplt.timer_callback(_do_reset, 0.1, single_shot=True)
                
        tab.x_range_changed.connect(on_x_range_changed)
        tab.chart_clicked.connect(on_chart_clicked)
        tab.reset_camera_requested.connect(on_reset_cam)
        
        assets = logic.get_available_assets()
        for db, t in assets:
            act = QAction(f"{t} ({os.path.basename(db)})", tab)
            act.triggered.connect(lambda checked, d=db, tbl=t: load_chart(d, tbl))
            tab.asset_menu.addAction(act)
            
        if assets:
            load_chart(assets[0][0], assets[0][1])

    # ----------------------------------
    # _bind_backtest, зв'язування бектесту
    # ----------------------------------
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
        tables = logic.get_tables()
        tab.table_combo.addItems(tables)
        
        tab.btn_save.clicked.connect(lambda: tab.save_strategy(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'strategies')))
        tab.btn_load.clicked.connect(lambda: tab.load_strategy(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'strategies'), logic.copilot))
        tab.btn_info.clicked.connect(tab.show_help_dialog)
        
        def run_backtest():
            tab.log_output.clear()
            tab.safe_append_html("<div style='font-family: monospace; font-size: 13px; line-height: 1.4; margin-bottom: 10px;'><p style='color: #0a84ff; font-weight: bold; margin-bottom: 5px;'>🚀 ЗАПУСК БЕКТЕСТУ</p><hr style='border: 0; border-top: 1px solid #444; margin-top: 2px; margin-bottom: 8px;'/></div>")
            
            db_name = "main.duckdb"
            table_name = tab.table_combo.currentText()
            if not table_name:
                tab.safe_append_html("<div style='color: #ff453a; font-family: monospace; font-weight: bold;'>❗ Оберіть Актив!</div><br>")
                return
                
            code = tab.code_editor.toPlainText()
            if "strategy = Strategy(" not in code:
                tab.safe_append_html("<div style='color: #ff453a; font-family: monospace; font-weight: bold;'>❗ У коді редактора відсутній об'єкт Strategy!</div><br>")
                return
                
            user_test_name = tab.test_name_input.text().strip()
            if not user_test_name:
                user_test_name = f"test_{int(time.time())}"
                tab.test_name_input.setText(user_test_name)
            test_name = f"backtest_{table_name}_{user_test_name}"
            
            tab.btn_run.setEnabled(False)
            tab.btn_run.setText("⏳ Розраховується...")
            tab.btn_show_chart.setEnabled(False)
            
            tab.safe_append_html(f"<div style='font-family: monospace; font-size: 13px; color: #e5e5ea;'><span style='color: #30d158; font-weight: bold;'>{db_name}</span> | <span style='color: #64d2ff; font-weight: bold;'>{table_name}</span> | <span style='color: #ffd60a; font-weight: bold;'>{test_name}</span></div>")
            
            tab._worker = BacktestWorker(code, "main.duckdb", table_name, test_name, copilot=logic.copilot)
            tab._worker.log_message.connect(lambda m: tab.safe_append_html(f"<div style='color: #e5e5ea; font-family: monospace; font-size: 13px;'>{m}</div><br>"))
            tab._worker.finished_ok.connect(lambda t: on_backtest_done(t, tab._worker.prediction_context))
            tab._worker.finished_error.connect(lambda e: on_backtest_error(e))
            tab._worker.start()
            
        def on_backtest_done(table_name, prediction_context):
            tab.safe_append_html(f"<div style='font-family: monospace; font-size: 13px;'><hr style='border: 0; border-top: 1px solid #444;'/><span style='color: #32d74b; font-weight: bold;'>✅ Бектест завершено!</span><br><span style='color: #8e8e93;'>Результати збережено в таблицю:</span> <span style='color: #64d2ff; font-weight: bold;'>{table_name}</span></div>")
            tab.btn_run.setEnabled(True)
            tab.btn_run.setText("▶ Розрахувати")
            tab.last_table_name = table_name
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
            if table: tab.request_show_chart.emit("main.duckdb", table)
            
        tab.btn_run.clicked.connect(run_backtest)
        tab.btn_show_chart.clicked.connect(show_chart)
        
        # Підключення Auto Learn
        def on_auto_learn_clicked():
            if hasattr(tab, "_auto_worker") and tab._auto_worker.isRunning():
                tab._auto_worker.stop()
                tab.btn_auto_learn.setText("🛑 ЗУПИНКА...")
                tab.btn_auto_learn.setEnabled(False)
                return
                
            table_name = tab.table_combo.currentText()
            if not table_name: return
            
            tab.log_output.clear()
            tab.btn_auto_learn.setText("🛑 ЗУПИНИТИ АВТО НАВЧАННЯ")
            tab.btn_auto_learn.setStyleSheet("background-color: #ff453a; color: white; font-weight: bold; padding: 8px;")
            
            count = tab.ai_learn_count.value()
            direction = "MIXED"
            if "BUY" in tab.ai_direction_combo.currentText(): direction = "BUY"
            elif "SELL" in tab.ai_direction_combo.currentText(): direction = "SELL"
            
            tab._auto_worker = AutoLearnWorker("main.duckdb", table_name, logic.meta_data, total_runs=count, direction_mode=direction)
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
            code = tab.code_editor.toPlainText()
            if "strategy = Strategy(" not in code: return
            table_name = tab.table_combo.currentText()
            if not table_name: return
            
            tab.safe_append_html(f"<div style='color: #A6ADC8; font-family: monospace; font-weight: bold;'>🔄 Запуск WFV для {table_name}...</div><br>")
            tab.btn_run_wfv.setEnabled(False)
            tab.btn_run.setEnabled(False)
            
            tab._wfv_worker = WfvWorker(code, "main.duckdb", table_name)
            tab._wfv_worker.log_message.connect(lambda m: tab.safe_append_html(m))
            
            def on_finished():
                tab.btn_run_wfv.setEnabled(True)
                tab.btn_run.setEnabled(True)
                
            tab._wfv_worker.finished.connect(on_finished)
            tab._wfv_worker.start()
            
        tab.btn_run_wfv.clicked.connect(on_wfv_clicked)

    # ----------------------------------
    # _bind_live_trading, зв'язування лайв торгівлі
    # ----------------------------------
    def _bind_live_trading(self):
        tab = self.v.live_trading_tab
        logic = self.l.live_trading
        
        logic.service.log_update.connect(
            lambda text: tab.log_console.append(
                f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] {text}"
            )
        )
        
        def on_start():
            tab.btn_start.setEnabled(False)
            tab.btn_stop.setEnabled(True)
            
            mode = "signal"
            if tab.rb_demo.isChecked(): mode = "demo"
            elif tab.rb_paper.isChecked(): mode = "paper"
            elif tab.rb_real.isChecked(): mode = "real"
                
            logic.start_trading(mode)
            
        def on_stop():
            tab.btn_start.setEnabled(True)
            tab.btn_stop.setEnabled(False)
            logic.stop_trading()
            
        tab.btn_start.clicked.connect(on_start)
        tab.btn_stop.clicked.connect(on_stop)

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
            
            use_ccxt = tab.cb_download_ccxt.isChecked()
            use_massive = tab.cb_download_massive.isChecked()
            auto_gen = tab.cb_auto_gen.isChecked()
            
            interval = 1.0
            import os
            import json
            if os.path.exists(tab.config_path):
                try:
                    with open(tab.config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        interval = data.get("copilot", {}).get("routine_interval_hours", 1.0)
                except Exception: pass
            
            logic.start_auto_routine(use_ccxt, use_massive, auto_gen, interval)
            
        def on_stop_auto():
            tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] 🛑 Зупинка автономного планувальника...")
            tab.btn_active.setStyleSheet("QPushButton { font-size: 14px; font-weight: bold; color: #11111B; background-color: #A6E3A1; border-radius: 6px; padding: 8px 16px; } QPushButton:hover { background-color: #94E2D5; }")
            tab.btn_active.setText("● ACTIVE")
            logic.stop_auto_routine()
            
        def on_scan_gaps():
            tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] --- Розпочато сканування прогалин ---")
            use_ccxt = tab.cb_download_ccxt.isChecked()
            use_massive = tab.cb_download_massive.isChecked()
            logic.analyze_database(use_ccxt, use_massive)
            
        tab.btn_active.clicked.connect(on_start_auto)
        tab.btn_stop.clicked.connect(on_stop_auto)
        tab.btn_start_task.clicked.connect(on_scan_gaps)
        tab.btn_add_task.clicked.connect(lambda: tab.log_console.append(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] --- Відкрито меню додавання задачі (В розробці) ---"))
        
        # Оновлення статистики
        logic.stats_ready.connect(tab.update_stats_ui)
        
        tab.stats_timer = QTimer(tab)
        tab.stats_timer.timeout.connect(logic.request_stats_async)
        tab.stats_timer.start(10000)
        QTimer.singleShot(500, logic.request_stats_async)

    # ----------------------------------
    # attach_to_tabs, додавання вкладок до QTabWidget
    # ----------------------------------
    # Параметри:
    # tabs_widget (QTabWidget): Віджет вкладок для додавання створених сторінок
    def attach_to_tabs(self, tabs_widget: QTabWidget):
        tabs_widget.addTab(self.v.explorer_tab, "Провідник БД")
        tabs_widget.addTab(self.v.downloader_tab, "Завантаження даних")
        tabs_widget.addTab(self.v.chart_tab, "Графік (finplot)")
        tabs_widget.addTab(self.v.backtest_tab, "Тестер стратегій")
        tabs_widget.addTab(self.v.copilot_tab, "Автономний Копілот")
        tabs_widget.addTab(self.v.live_trading_tab, "Лайв Торгівля")
        tabs_widget.addTab(self.v.settings_tab, "Налаштування")
