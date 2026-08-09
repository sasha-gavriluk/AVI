import os
import json
import time
import pandas as pd
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QWidget, QCheckBox, QGridLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from gui.engine import engine

from utils.Trading.CCXTModule import CCXTModule
from utils.Trading.MassiveModule import MassiveModule
from utils.DataBaseManager import DataBaseManager
from utils.PathManager import PathManager
from utils.gap_analyzer import GapAnalyzer

from gui.visual.widgets.signal_card import SignalCard
from gui.visual.widgets.flow_layout import FlowLayout
from utils.algorithms.FCryptoLogic import FCryptoLogic

import utils.config as app_config

def parse_timeframe(tf):
    if tf.endswith('m'): return int(tf[:-1]), 'minute'
    if tf.endswith('h'): return int(tf[:-1]), 'hour'
    if tf.endswith('d'): return int(tf[:-1]), 'day'
    return 15, 'minute'

class DataFetcherWorker(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, logic_instance, assets_list, market_type, timeframes):
        super().__init__()
        self.logic = logic_instance
        self.assets = assets_list
        self.market = market_type
        # Список таймфреймів: робочий + старші для HTF-контексту (1h/4h/1d).
        # Без старших ТФ система не бачить, чи локальний рух — це тренд, чи відскок.
        self.timeframes = list(timeframes) if isinstance(timeframes, (list, tuple)) else [timeframes]

    def run(self):
        try:
            self.progress.emit("Ініціалізація підключень...")
            if self.market == "Crypto" and hasattr(self.logic, 'ccxt'):
                import utils.config as app_config
                if app_config.bybit_key and app_config.bybit_secret_key:
                    self.logic.ccxt.connect(app_config.bybit_key, app_config.bybit_secret_key)

            self.progress.emit("Ініціалізація GapAnalyzer...")
            gap_analyzer = GapAnalyzer()

            # Зчитуємо доступні таблиці раз
            try:
                tables_df = self.logic.db.conn.execute("SHOW TABLES;").df()
                available_tables = tables_df['name'].tolist()
            except Exception:
                available_tables = []

            for tf_i, timeframe in enumerate(self.timeframes):
                if not self.logic.is_running:
                    self.progress.emit("Процес перервано користувачем.")
                    return
                self.progress.emit(f"=== Таймфрейм {timeframe} ({tf_i+1}/{len(self.timeframes)}) ===")
                self._sync_timeframe(timeframe, gap_analyzer, available_tables)
                if not self.logic.is_running:
                    return

            self.progress.emit("Всі дані успішно синхронізовано!")
            self.finished_ok.emit()

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[DataFetcher] CRASH: {e}")
            self.error.emit(str(e))

    def _sync_timeframe(self, timeframe, gap_analyzer, available_tables):
        "Синхронізує всі активи для ОДНОГО таймфрейму"
        multiplier, tf_str = parse_timeframe(timeframe)
        tf_ms = multiplier * (60000 if tf_str == 'minute' else 3600000 if tf_str == 'hour' else 86400000)

        for i, asset in enumerate(self.assets):
                if not self.logic.is_running:
                    self.progress.emit("Процес перервано користувачем.")
                    return

                self.progress.emit(f"[{timeframe}] [{i+1}/{len(self.assets)}] {asset} - Перевірка прогалин...")

                base_name = asset.replace(':', '').replace('/', '_')
                table_name = f"{base_name}_{timeframe}"
                alt_name_1 = f"{base_name.replace('_', '')}_{timeframe}"

                # Знаходимо правильну таблицю, якщо є розбіжності (наприклад BTC_USDT vs BTCUSDT)
                if table_name not in available_tables:
                    if alt_name_1 in available_tables:
                        table_name = alt_name_1
                    elif f"{base_name[:3]}_{base_name[3:]}_{timeframe}" in available_tables: # BTCUSDT -> BTC_USDT
                        table_name = f"{base_name[:3]}_{base_name[3:]}_{timeframe}"
                
                # 1 year logic
                one_year_ms = 365 * 24 * 60 * 60 * 1000
                now_ms = int(time.time() * 1000)
                min_required_start = now_ms - one_year_ms
                
                gaps = []
                if table_name in available_tables:
                    try:
                        # Find min/max bounds in the table
                        min_ts = self.logic.db.conn.cursor().execute(f'SELECT MIN(timestamp) FROM "{table_name}"').fetchone()[0]
                        max_ts = self.logic.db.conn.cursor().execute(f'SELECT MAX(timestamp) FROM "{table_name}"').fetchone()[0]
                        
                        internal_gaps = self.logic.db.get_time_gaps(table_name, timeframe_ms=tf_ms)
                        if internal_gaps:
                            gaps.extend(internal_gaps)
                            
                        # Gap before data (up to 1 year ago)
                        if min_ts and min_ts > min_required_start + tf_ms:
                            gaps.append({'gap_start': min_required_start, 'gap_end': int(min_ts)})
                            
                        # Gap after data (up to now)
                        if max_ts and max_ts < now_ms - tf_ms:
                            gaps.append({'gap_start': int(max_ts), 'gap_end': now_ms})
                    except Exception as e:
                        gaps = [{'gap_start': min_required_start, 'gap_end': now_ms}]
                else:
                    gaps = [{'gap_start': min_required_start, 'gap_end': now_ms}]
                
                gaps.sort(key=lambda x: x['gap_start'])
                real_gaps = gap_analyzer.filter_real_gaps(gaps, asset, tf_ms, market_type=self.market)
                
                if not real_gaps:
                    self.progress.emit(f"[{i+1}/{len(self.assets)}] {asset} - Історія повна (≥ 1 рік).")
                    continue
                    
                self.progress.emit(f"[{i+1}/{len(self.assets)}] {asset} - {len(real_gaps)} прогалин. Завантаження...")
                
                if self.market == "Forex" and hasattr(self.logic, 'massive'):
                    for gap in real_gaps:
                        if not self.logic.is_running: return
                        gap_start = pd.to_datetime(gap['gap_start'], unit='ms')
                        gap_end = pd.to_datetime(gap['gap_end'], unit='ms')
                        
                        self.progress.emit(f"[{i+1}/{len(self.assets)}] {asset} - Форекс завантаження {gap_start.strftime('%d.%m.%Y')} -> {gap_end.strftime('%d.%m.%Y')}...")
                        self.logic.massive.fetch_ohlcv_auto_download(
                            asset, multiplier, tf_str,
                            start_date=gap_start.strftime('%Y-%m-%d'),
                            end_date=gap_end.strftime('%Y-%m-%d')
                        )
                elif self.market == "Crypto" and hasattr(self.logic, 'ccxt'):
                    for gap in real_gaps:
                        if not self.logic.is_running: return
                        current_since = gap['gap_start']
                        gap_end_ms = gap['gap_end']
                        
                        while current_since < gap_end_ms:
                            if not self.logic.is_running: return
                            
                            start_dt = pd.to_datetime(current_since, unit='ms').strftime('%d.%m.%Y')
                            end_dt = pd.to_datetime(gap_end_ms, unit='ms').strftime('%d.%m.%Y')
                            pct = min(100, int((current_since - gap['gap_start']) / max(1, (gap_end_ms - gap['gap_start'])) * 100))
                            self.progress.emit(f"[{i+1}/{len(self.assets)}] {asset} - Крипто завантаження {start_dt} -> {end_dt} [{pct}%]")
                            
                            print(f"[DataFetcher] Запит API для {asset} (since={current_since})...")
                            result = self.logic.ccxt.fetch_ohlcv(asset, timeframe, since=current_since, limit=1000)
                            print(f"[DataFetcher] Відповідь API отримана.")
                            
                            if result is None or not isinstance(result, tuple):
                                # API error, let's wait 5 seconds and try again instead of skipping
                                print("[DataFetcher] Помилка API (можливо ліміт запитів). Очікування 5 секунд...")
                                time.sleep(5)
                                continue
                                
                            df, _ = result
                            
                            if df is not None and not df.empty:
                                df = df.dropna(subset=['timestamp'])
                            
                            if df is None or df.empty:
                                # Safe break to avoid infinite loop if API returns empty
                                current_since += (1000 * tf_ms)
                            else:
                                last_ts = int(df['timestamp'].max())
                                if last_ts <= current_since:
                                    current_since += (1000 * tf_ms)
                                else:
                                    current_since = last_ts + 1
                                    
                            time.sleep(self.logic.ccxt.exchange.rateLimit / 1000.0)

class SignalsWorker(QThread):
    result_ready = pyqtSignal(str, dict)
    finished_calc = pyqtSignal()
    
    def __init__(self, assets_list, timeframe, market_type):
        super().__init__()
        self.assets = assets_list
        self.timeframe = timeframe
        self.market = market_type
        self.is_running = True
        
    def run(self):
        try:
            from utils.DataBaseManager import DataBaseManager
            db = DataBaseManager(use_default=True)
            tables_df = db.conn.execute("SHOW TABLES;").df()
            available_tables = tables_df['name'].tolist()
            
            for asset in self.assets:
                if not self.is_running:
                    break
                    
                base_name = asset.replace(':', '').replace('/', '_')
                table_name = f"{base_name}_{self.timeframe}"
                alt_name_1 = f"{base_name.replace('_', '')}_{self.timeframe}"
                
                actual_table = None
                if table_name in available_tables:
                    actual_table = table_name
                elif alt_name_1 in available_tables:
                    actual_table = alt_name_1
                elif f"{base_name[:3]}_{base_name[3:]}_{self.timeframe}" in available_tables:
                    actual_table = f"{base_name[:3]}_{base_name[3:]}_{self.timeframe}"
                    
                signal_data = {"error": "Таблиця не знайдена в БД"}
                if actual_table:
                    # Мережам FMR/FFB потрібно рівно 1000 свічок (seq_len). Беремо 1500:
                    # 1000 на вікно НН + запас на прогрів зон RS та EMA. Менше 1000 —
                    # FMR/FFB повертають нулі, і сигнал стає фікцією.
                    df = db.get_data_by_number_range(actual_table, 1500)
                    if df is not None and not df.empty:
                        df = df.sort_values(by='timestamp', ascending=True).reset_index(drop=True)
                        if self.market == "Crypto":
                            from utils.algorithms.FCryptoLogic import FCryptoLogic
                            logic_alg = FCryptoLogic(df)
                            signal_data = logic_alg.process()
                        else:
                            from utils.algorithms.BOForexLogic import BOForexLogic
                            logic_alg = BOForexLogic(df)
                            signal_data = logic_alg.process()
                    else:
                        signal_data = {"error": "Немає даних для аналізу"}
                
                self.result_ready.emit(asset, signal_data)
                
            db.disconnect()
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            self.finished_calc.emit()

class AppLogic:
    def __init__(self):
        engine.bind("app.start", self.on_start)
        engine.bind("app.mode_changed", self.on_mode_changed)
        engine.bind("app.market_changed", self.on_market_changed)
        engine.bind("app.open_assets_dialog", self.open_assets_dialog)
        
        self.is_running = False
        self.worker = None
        self.signals_worker = None
        self.signal_cards = {}

        # Старші таймфрейми для HTF-контексту. Качаються завжди разом із робочим,
        # інакше система не бачить, чи локальний рух — тренд, чи відскок у ведмежому ринку.
        self.context_timeframes = ['1h', '4h', '1d']
        
        self.crypto_assets = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
            "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT"
        ]
        
        self.forex_assets = [
            "C:EURUSD", "C:GBPUSD", "C:USDJPY", "C:USDCHF", "C:AUDUSD", 
            "C:USDCAD", "C:NZDUSD", "C:EURGBP", "C:EURJPY", "C:GBPJPY"
        ]
    
    def init_ui(self):
        main_window = engine.get("main_window")
        if main_window:
            main_window.setTabEnabled(1, True)
            
        input_assets = engine.get("input_assets_list")
        if input_assets and not input_assets.text().strip():
            # Задаємо активи за замовчуванням
            input_assets.setText("BTCUSDT, ETHUSDT, BNBUSDT")
            
        self.update_signals_ui()
        
    def on_mode_changed(self, checked=False):
        rb_futures = engine.get("rb_futures")
        rb_bo = engine.get("rb_bo")
        rb_crypto = engine.get("rb_crypto")
        rb_forex = engine.get("rb_forex")
        
        if not (rb_futures and rb_bo and rb_crypto and rb_forex):
            return
            
        if rb_bo.isChecked():
            rb_crypto.setEnabled(False)
            rb_forex.setEnabled(True)
            
            rb_crypto.blockSignals(True)
            rb_forex.blockSignals(True)
            rb_forex.setChecked(True)
            rb_crypto.blockSignals(False)
            rb_forex.blockSignals(False)
            
        elif rb_futures.isChecked():
            rb_forex.setEnabled(False)
            rb_crypto.setEnabled(True)
            
            rb_crypto.blockSignals(True)
            rb_forex.blockSignals(True)
            rb_crypto.setChecked(True)
            rb_crypto.blockSignals(False)
            rb_forex.blockSignals(False)
            
        self.on_market_changed()

    def on_market_changed(self, checked=False):
        input_assets = engine.get("input_assets_list")
        if input_assets:
            rb_crypto = engine.get("rb_crypto")
            is_crypto = rb_crypto.isChecked() if rb_crypto else True
            
            if is_crypto:
                input_assets.setText("BTCUSDT, ETHUSDT, BNBUSDT")
            else:
                input_assets.setText("C:EURUSD, C:GBPUSD, C:USDJPY")
            
            self.update_signals_ui()
            
    def open_assets_dialog(self):
        main_window = engine.get("main_window")
        if not main_window: return
            
        input_assets = engine.get("input_assets_list")
        if not input_assets: return
            
        rb_crypto = engine.get("rb_crypto")
        is_crypto = rb_crypto.isChecked() if rb_crypto else True
        available_assets = self.crypto_assets if is_crypto else self.forex_assets
        
        current_selected = [a.strip() for a in input_assets.text().split(",") if a.strip()]
        
        dialog = QDialog(main_window)
        dialog.setWindowTitle("Вибір активів")
        dialog.setMinimumWidth(300)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        btn_layout = QHBoxLayout()
        btn_select_all = QPushButton("Вибрати всі")
        btn_deselect_all = QPushButton("Зняти всі")
        btn_layout.addWidget(btn_select_all)
        btn_layout.addWidget(btn_deselect_all)
        layout.addLayout(btn_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; } QWidget#scroll_content { background-color: transparent; }")
        
        content_widget = QWidget()
        content_widget.setObjectName("scroll_content")
        content_layout = QVBoxLayout(content_widget)
        
        checkboxes = []
        for asset in available_assets:
            cb = QCheckBox(asset)
            if asset in current_selected:
                cb.setChecked(True)
            content_layout.addWidget(cb)
            checkboxes.append(cb)
            
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        def select_all():
            for c in checkboxes: c.setChecked(True)
        def deselect_all():
            for c in checkboxes: c.setChecked(False)
            
        btn_select_all.clicked.connect(select_all)
        btn_deselect_all.clicked.connect(deselect_all)
        
        btn_ok = QPushButton("Зберегти вибір")
        layout.addWidget(btn_ok)
        
        def save_selection():
            selected = [c.text() for c in checkboxes if c.isChecked()]
            input_assets.setText(", ".join(selected))
            self.update_signals_ui()
            dialog.accept()
            
        btn_ok.clicked.connect(save_selection)
        dialog.exec()
            
    def on_start(self):
        btn_start = engine.get("btn_start")
        status_label = engine.get("status_label")
        signals_log = engine.get("signals_log")
        main_window = engine.get("main_window")
        
        if self.is_running:
            # ЗУПИНКА
            self.is_running = False
            if btn_start:
                btn_start.setText("🚀 Запустити Термінал")
                btn_start.setStyleSheet("") 
            if status_label:
                status_label.setText("Процес зупинено.")
            if signals_log:
                signals_log.append("Процес перервано користувачем.")
            return
            
        # ЗАПУСК
        self.is_running = True
        if btn_start:
            btn_start.setText("🛑 Зупинити Термінал")
            btn_start.setStyleSheet("background-color: #f85149; border: 1px solid #ff7b72;")
        if status_label:
            status_label.setText("Запуск... Ініціалізація.")
            
        rb_futures = engine.get("rb_futures")
        trading_mode = "Futures" if (rb_futures and rb_futures.isChecked()) else "BO"
        
        rb_crypto = engine.get("rb_crypto")
        market_type = "Crypto" if (rb_crypto and rb_crypto.isChecked()) else "Forex"
        
        timeframe = engine.get("input_timeframe").text()
        
        input_assets = engine.get("input_assets_list").text().strip()
        assets_list = [a.strip() for a in input_assets.split(",") if a.strip()]
        
        if not assets_list:
            if status_label:
                status_label.setText("Помилка: Не вибрано жодного активу!")
            self.is_running = False
            if btn_start: btn_start.setText("🚀 Запустити Термінал"); btn_start.setStyleSheet("")
            return
        
        try:
            account_balance = float(engine.get("input_account_balance").text())
            risk_pct = 1.0 
        except ValueError:
            if status_label:
                status_label.setText("Помилка: Баланс повинен бути числом!")
            self.is_running = False
            if btn_start: btn_start.setText("🚀 Запустити Термінал"); btn_start.setStyleSheet("")
            return

        config_data = {
            "trading_mode": trading_mode,
            "market_type": market_type,
            "timeframe": timeframe,
            "account_balance": account_balance,
            "risk_per_trade_pct": risk_pct,
            "bo_expiration_bars": 1,
            "bo_payout_percent": 80.0,
            "bo_bet_size": 10.0,
            "max_candles": 5000,
            "assets": assets_list
        }
        
        config_dir = os.path.join(PathManager.get_user_data_dir(), "data", "config")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "gui_settings.json")
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
            
        # Підключення до БД
        try:
            self.db = DataBaseManager()
        except Exception as e:
            if status_label: status_label.setText("Помилка БД!")
            self.is_running = False
            if btn_start: btn_start.setText("🚀 Запустити Термінал"); btn_start.setStyleSheet("")
            return
            
        # Підключення API
        if market_type == "Crypto":
            try:
                self.ccxt = CCXTModule("bybit", self.db)
                # Підключення перенесено у фоновий потік (DataFetcherWorker), щоб не вішати UI
            except Exception as e:
                print(f"CCXT Error: {e}")
        else:
            try:
                if app_config.massive_key:
                    self.massive = MassiveModule(self.db, app_config.massive_key)
            except Exception as e:
                print(f"Massive Error: {e}")

        # Робочий ТФ + старші для HTF-контексту (без дублів, робочий іде першим)
        timeframes = [timeframe] + [tf for tf in self.context_timeframes if tf != timeframe]

        # Запуск фонового потоку перевірки прогалин
        self.worker = DataFetcherWorker(self, assets_list, market_type, timeframes)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()
        
    def _on_worker_progress(self, msg):
        print(f"[DataFetcher] {msg}")
        status_label = engine.get("status_label")
        if status_label:
            status_label.setText(msg)
            
    def _on_worker_finished(self):
        status_label = engine.get("status_label")
        main_window = engine.get("main_window")
        
        if status_label:
            status_label.setText("Дані завантажено. Генерація сигналів...")
            
        if main_window:
            main_window.setTabEnabled(1, True)
            main_window.setCurrentIndex(1)
            
        # Запускаємо оновлення UI сигналів
        self.update_signals_ui()
        
        if status_label:
            status_label.setText("Система активована. Сигнали оновлено.")
            
    def _on_worker_error(self, err_msg):
        status_label = engine.get("status_label")
        btn_start = engine.get("btn_start")
        if status_label:
            status_label.setText(f"Помилка завантаження: {err_msg}")
        self.is_running = False
        if btn_start:
            btn_start.setText("🚀 Запустити Термінал")
            btn_start.setStyleSheet("")

    def update_signals_ui(self):
        signals_placeholder = engine.get("signals_placeholder")
        if not signals_placeholder:
            return
            
        # Якщо QScrollArea ще не створена, створюємо її
        if not hasattr(self, 'signals_scroll'):
            self.signals_scroll = QScrollArea()
            self.signals_scroll.setWidgetResizable(True)
            self.signals_scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
            
            self.signals_container = QWidget()
            self.signals_container.setObjectName("signals_container")
            self.signals_container.setStyleSheet("QWidget#signals_container { background-color: transparent; }")
            
            # Використовуємо FlowLayout щоб уникнути горизонтальної прокрутки
            self.signals_grid = FlowLayout(self.signals_container)
            self.signals_grid.setSpacing(15)
            
            self.signals_scroll.setWidget(self.signals_container)
            
            # Додаємо у placeholder
            layout = signals_placeholder.layout()
            if not layout:
                from PyQt6.QtWidgets import QVBoxLayout
                layout = QVBoxLayout(signals_placeholder)
                layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.signals_scroll)
                
        # Очищуємо існуючі віджети
        while self.signals_grid.count():
            child = self.signals_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # Отримуємо вибрані активи
        input_assets = engine.get("input_assets_list")
        if not input_assets: return
        assets_list = [a.strip() for a in input_assets.text().split(",") if a.strip()]
        
        rb_crypto = engine.get("rb_crypto")
        market_type = "Crypto" if (rb_crypto and rb_crypto.isChecked()) else "Forex"
        timeframe = engine.get("input_timeframe").text()
        
        self.signal_cards = {}
        for asset in assets_list:
            card = SignalCard(asset)
            card.reason_label.setText("Аналіз ринку...")
            self.signal_cards[asset] = card
            self.signals_grid.addWidget(card)
            
        if not hasattr(self, 'db'):
            # Якщо БД ще не підключена, залишаємо картки в стані очікування
            for asset, card in self.signal_cards.items():
                card.reason_label.setText("Очікування запуску...")
            return

        # Зупиняємо попередній потік, якщо він ще працює
        if self.signals_worker and self.signals_worker.isRunning():
            self.signals_worker.is_running = False
            self.signals_worker.wait()
            
        self.signals_worker = SignalsWorker(assets_list, timeframe, market_type)
        self.signals_worker.result_ready.connect(self._on_signal_ready)
        self.signals_worker.start()

    def _on_signal_ready(self, asset, signal_data):
        if asset in self.signal_cards:
            card = self.signal_cards[asset]
            if "error" in signal_data:
                card.reason_label.setText(signal_data["error"])
            else:
                card.update_signal(signal_data)
