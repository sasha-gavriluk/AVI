import os
from utils.OtherUtils import _handle_error
import json
import time
import pandas as pd
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QWidget, QCheckBox, QGridLayout, QRadioButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from gui.engine import Engine as engine

from utils.Trading.CCXTModule import CCXTModule
from utils.Trading.MassiveModule import MassiveModule
from utils.DataBaseManager import DataBaseManager
from utils.PathManager import PathManager
from utils.GapAnalyzer import GapAnalyzer

from gui.visual.widgets.SignalCard import SignalCard
from gui.visual.widgets.FlowLayout import FlowLayout

import utils.Config as app_config

@_handle_error
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

    @_handle_error
    def run(self):
        try:
            self.progress.emit("Ініціалізація підключень...")
            if self.market == "Crypto" and hasattr(self.logic, 'ccxt'):
                import utils.Config as app_config
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

    @_handle_error
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

#==============================
# Потік живої торгівлі
#==============================
#
# Тримає TradeRunner і віддає його стан інтерфейсу сигналами Qt. Уся робота —
# біржа, фічі, мережа, ордер — відбувається ТУТ, у фоновому потоці, бо один
# такт коштує десятки секунд і головний потік на цей час просто завмер би.
#
# ЧОМУ ОДНА БАЗА НА ВСІХ. DataBaseManager тримає з'єднання DuckDB у спільному
# реєстрі за шляхом до файлу: скільки б менеджерів не створили, з'єднання
# лишається одне, а звернення до нього серіалізує спільний замок. Тому цей
# потік створює свій менеджер спокійно — новий файл не відкривається.
#
# Раніше на цьому місці був SignalsWorker: він на кожне оновлення інтерфейсу
# створював FCryptoLogic для кожного активу й годував мережу сирими свічками
# ТОГО таймфрейму, який обрано в інтерфейсі. Для мережі, навченої на 15м,
# це були просто інші дані. Прибрано 02.09.2026.
#==============================

class TradingWorker(QThread):
    state_ready = pyqtSignal(dict)
    log_line = pyqtSignal(str)
    finished_run = pyqtSignal(str)

    def __init__(self, pairs, live=False, paper_balance=150.0, new_test=False):
        """
        :param pairs: ['BTCUSDT', ...]
        :param live: True — справжні ордери на біржі
        :param new_test: True — почати новий відлік просідання
        """
        super().__init__()
        self.pairs = list(pairs)
        self.live = bool(live)
        self.paper_balance = float(paper_balance)
        self.new_test = bool(new_test)
        self.runner = None

    @_handle_error
    def run(self):
        try:
            from utils.algorithms.TradeRunner import TradeRunner

            db = DataBaseManager(use_default=True)

            exchange = None
            if app_config.has_bybit_keys():
                exchange = CCXTModule("bybit", db)
                exchange.connect(app_config.bybit_key, app_config.bybit_secret_key)
            else:
                self.log_line.emit("Ключі Bybit не задані — працюємо на тому, що в базі")

            self.runner = TradeRunner(
                pairs=self.pairs,
                db=db,
                exchange=exchange,
                live=self.live,
                paper_balance=self.paper_balance,
                new_test=self.new_test,
                on_state=self.state_ready.emit,
                on_log=self.log_line.emit,
            )
            self.runner.run()
            self.finished_run.emit(self.runner.account.report())

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished_run.emit(f"Помилка: {e}")

    @_handle_error
    def stop(self):
        "Просить цикл завершитись. Поточний такт дороблюється до кінця"
        if self.runner:
            self.runner.stop()

class AppLogic:
    def __init__(self):
        engine.bind("app.start", self.on_start)
        engine.bind("app.mode_changed", self.on_mode_changed)
        engine.bind("app.market_changed", self.on_market_changed)
        engine.bind("app.open_assets_dialog", self.open_assets_dialog)
        engine.bind("app.save_keys", self.on_save_keys)
        engine.bind("app.toggle_keys", self.on_toggle_keys)
        engine.bind("trades.toggle", self.on_toggle_trading)

        self.is_running = False
        self.worker = None
        self.trading_worker = None
        self.signal_cards = {}

        # Живий режим підтверджується руками один раз за запуск програми.
        # Далі в межах сесії кнопка стартує без питань
        self.live_confirmed = False

        # Чи забути записаний депозит і почати відлік просідання заново
        self.new_test = False

        # Старші таймфрейми для HTF-контексту. Качаються завжди разом із робочим,
        # інакше система не бачить, чи локальний рух — тренд, чи відскок у ведмежому ринку.
        self.context_timeframes = ['1h', '4h', '1d', '15m', '5m']
        
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
            
        tf_container = engine.get("timeframes_container")
        self.tf_buttons = []
        if tf_container:
            if not tf_container.layout():
                tf_container.setLayout(QHBoxLayout())
            for tf in self.context_timeframes:
                rb = QRadioButton(tf)
                if tf == "15m":
                    rb.setChecked(True)
                tf_container.layout().addWidget(rb)
                self.tf_buttons.append((tf, rb))
                
        input_assets = engine.get("input_assets_list")
        if input_assets and not input_assets.text().strip():
            # Задаємо активи за замовчуванням
            input_assets.setText("BTCUSDT, ETHUSDT, BNBUSDT")

        self.init_keys_ui()
        self.update_signals_ui()

        # Рядок режиму на вкладці «Угоди» має бути чесним ще до старту:
        # з ключами кнопка поведе на біржу, без них — лише порахує
        mode = engine.get("trades_mode")
        if mode:
            mode.setText("Ключі є — старт поведе на біржу" if app_config.has_bybit_keys()
                         else "Ключів немає — ордери не ставитимуться")

    #------------------------------
    # Ключі Bybit
    #------------------------------

    @_handle_error
    def init_keys_ui(self):
        """
        Підставляє збережені ключі в поля.

        Секрет одразу ховається крапками: поле лишається робочим, але ключ
        не світиться на екрані й не потрапляє на випадковий знімок.
        """
        from PyQt6.QtWidgets import QLineEdit

        field_key = engine.get("input_bybit_key")
        field_secret = engine.get("input_bybit_secret")
        status = engine.get("keys_status")

        if field_secret:
            field_secret.setEchoMode(QLineEdit.EchoMode.Password)
        if field_key:
            field_key.setEchoMode(QLineEdit.EchoMode.Password)

        if app_config.bybit_key and field_key:
            field_key.setText(app_config.bybit_key)
        if app_config.bybit_secret_key and field_secret:
            field_secret.setText(app_config.bybit_secret_key)

        if status:
            if app_config.has_bybit_keys():
                status.setText("Ключі збережено.")
                engine._apply_style(status, "status_ok")
            else:
                status.setText("Ключів немає — торгівля працюватиме лише на даних із бази.")
                engine._apply_style(status, "status_error")

    @_handle_error
    def on_toggle_keys(self, checked=False):
        "Галочка «Показати» — знімає крапки з обох полів"
        from PyQt6.QtWidgets import QLineEdit

        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        for name in ("input_bybit_key", "input_bybit_secret"):
            field = engine.get(name)
            if field:
                field.setEchoMode(mode)

    @_handle_error
    def on_save_keys(self):
        """
        Пише ключі в .env теки користувача — той самий файл, який читає Config.

        Порожнє поле означає «не чіпати», а не «стерти»: інакше випадкове
        очищення поля тихо позбавило б програму єдиної копії ключа.
        """
        field_key = engine.get("input_bybit_key")
        field_secret = engine.get("input_bybit_secret")
        status = engine.get("keys_status")

        key = field_key.text().strip() if field_key else ''
        secret = field_secret.text().strip() if field_secret else ''

        if not key and not secret:
            if status:
                status.setText("Обидва поля порожні — нічого не змінено.")
                engine._apply_style(status, "status_error")
            return

        saved = app_config.save_bybit_keys(key, secret)
        if status:
            if saved:
                status.setText("Ключі збережено. Резервна копія — .env.backup")
                engine._apply_style(status, "status_ok")
            else:
                status.setText("Не вдалось записати ключі.")
                engine._apply_style(status, "status_error")

    @_handle_error
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

    @_handle_error
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
            
    @_handle_error
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
        
        @_handle_error
        def select_all():
            for c in checkboxes: c.setChecked(True)
        @_handle_error
        def deselect_all():
            for c in checkboxes: c.setChecked(False)
            
        btn_select_all.clicked.connect(select_all)
        btn_deselect_all.clicked.connect(deselect_all)
        
        btn_ok = QPushButton("Зберегти вибір")
        layout.addWidget(btn_ok)
        
        @_handle_error
        def save_selection():
            selected = [c.text() for c in checkboxes if c.isChecked()]
            input_assets.setText(", ".join(selected))
            self.update_signals_ui()
            dialog.accept()
            
        btn_ok.clicked.connect(save_selection)
        dialog.exec()
            
    @_handle_error
    def on_start(self):
        btn_start = engine.get("btn_start")
        status_label = engine.get("status_label")
        main_window = engine.get("main_window")
        
        if self.is_running:
            # ЗУПИНКА
            self.is_running = False
            if btn_start:
                btn_start.setText("🚀 Запустити Термінал")
                btn_start.setStyleSheet("") 
            if status_label:
                status_label.setText("Процес зупинено.")
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
        
        timeframe = "15m"
        if hasattr(self, 'tf_buttons'):
            for tf, rb in self.tf_buttons:
                if rb.isChecked():
                    timeframe = tf
                    break
        
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
        
    @_handle_error
    def _on_worker_progress(self, msg):
        print(f"[DataFetcher] {msg}")
        status_label = engine.get("status_label")
        if status_label:
            status_label.setText(msg)
            
    @_handle_error
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
            
    @_handle_error
    def _on_worker_error(self, err_msg):
        status_label = engine.get("status_label")
        btn_start = engine.get("btn_start")
        if status_label:
            status_label.setText(f"Помилка завантаження: {err_msg}")
        self.is_running = False
        if btn_start:
            btn_start.setText("🚀 Запустити Термінал")
            btn_start.setStyleSheet("")

    #------------------------------
    # Картки активів на вкладці «Угоди»
    #------------------------------

    @_handle_error
    def update_signals_ui(self):
        """
        Перемальовує картки під поточний список активів.

        Картки більше нічого не рахують самі — вони тільки показують те, що
        приніс такт живого циклу. Раніше кожне оновлення інтерфейсу запускало
        власний прохід мережі, і це був окремий, ні з чим не звірений результат.
        """
        placeholder = engine.get("trade_cards")
        if not placeholder:
            return

        if not hasattr(self, 'signals_scroll'):
            from PyQt6.QtWidgets import QSizePolicy

            # Картки мають з'їдати вільну висоту вкладки, інакше вони тиснуться
            # в кілька пікселів між рядком стану й журналом
            placeholder.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Expanding)
            placeholder.setMinimumHeight(260)

            self.signals_scroll = QScrollArea()
            self.signals_scroll.setWidgetResizable(True)
            self.signals_scroll.setStyleSheet(
                "QScrollArea { border: none; background-color: transparent; }")

            self.signals_container = QWidget()
            self.signals_container.setObjectName("signals_container")
            self.signals_container.setStyleSheet(
                "QWidget#signals_container { background-color: transparent; }")

            # FlowLayout, щоб картки переносились рядками без горизонтальної прокрутки
            self.signals_grid = FlowLayout(self.signals_container)
            self.signals_grid.setSpacing(15)
            self.signals_scroll.setWidget(self.signals_container)

            layout = placeholder.layout()
            if not layout:
                layout = QVBoxLayout(placeholder)
                layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.signals_scroll)

        while self.signals_grid.count():
            child = self.signals_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.signal_cards = {}
        for asset in self.selected_assets():
            card = SignalCard(asset)
            card.reason_label.setText("Очікування запуску...")
            self.signal_cards[asset] = card
            self.signals_grid.addWidget(card)

    @_handle_error
    def selected_assets(self) -> list:
        "Активи, вибрані в налаштуваннях"
        field = engine.get("input_assets_list")
        if not field:
            return []
        return [a.strip() for a in field.text().split(",") if a.strip()]

    #------------------------------
    # Кнопка Старт / Стоп
    #------------------------------

    @_handle_error
    def on_toggle_trading(self):
        """
        Одна кнопка на два стани. Натиснув — пішло, натиснув удруге — спинилось.

        Живий режим підтверджується вікном ОДИН раз за запуск програми:
        далі кнопка стартує без питань, бо серед такту питати вже нікому.
        """
        if self.trading_worker and self.trading_worker.isRunning():
            self.trade_log("Зупинка... поточний такт дороблюється до кінця.")
            self.trading_worker.stop()
            self.set_trade_button(running=False, text="⏳  Зупиняється...")
            return

        assets = self.selected_assets()
        if not assets:
            self.trade_status("Не вибрано жодного активу — зайди в Налаштування.", ok=False)
            return

        live = app_config.has_bybit_keys()
        if live and not self.live_confirmed and not self.confirm_live(assets):
            return

        self.update_signals_ui()

        self.trading_worker = TradingWorker(assets, live=live,
                                            paper_balance=self.configured_balance(),
                                            new_test=self.new_test)
        self.trading_worker.state_ready.connect(self._on_trade_state)
        self.trading_worker.log_line.connect(self.trade_log)
        self.trading_worker.finished_run.connect(self._on_trade_finished)
        self.trading_worker.start()

        self.set_trade_button(running=True)
        self.trade_status("Цикл запущено. Качаємо дані, далі чекаємо закриття свічки.", ok=True)

        mode = engine.get("trades_mode")
        if mode:
            mode.setText("ЖИВИЙ РЕЖИМ — СПРАВЖНІ ОРДЕРИ" if live
                         else "БЕЗ КЛЮЧІВ — ОРДЕРИ НЕ СТАВЛЯТЬСЯ")

    @_handle_error
    def confirm_live(self, assets: list) -> bool:
        """
        Одноразове підтвердження перед справжніми ордерами.

        Тут же вирішується, від якого депозиту рахувати межу просідання.
        Якщо тест уже початий, за замовчуванням ПРОДОВЖУЄМО його: інакше
        перезапуск після втрати відсував би межу за новим, меншим рахунком,
        і домовлена сума ризику розтягувалась би без кінця.
        """
        from PyQt6.QtWidgets import QMessageBox
        from utils.algorithms.brain.ExchangeAccount import ExchangeAccount

        saved = ExchangeAccount.saved_baseline()
        self.new_test = False

        details = (
            f"Активів: {len(assets)} ({', '.join(assets)})\n"
            f"Застава на угоду: 10% депозиту, рахується один раз\n"
            f"Плече: 20x (10x, якщо біржа не дасть 20)\n"
            f"Поріг впевненості знято — заходимо на найкращому сигналі\n"
        )

        box = QMessageBox(engine.get("main_window"))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Жива торгівля")
        box.setText("Запустити ЖИВУ торгівлю справжніми грошима?")

        if saved:
            start = float(saved.get('start_balance', 0))
            limit = start * float(saved.get('max_drawdown_pct', 20)) / 100.0
            box.setInformativeText(
                details +
                f"\nТест уже початий {str(saved.get('recorded_at', ''))[:16].replace('T', ' ')}.\n"
                f"Депозит ${start:.2f}, зупинка на ${start - limit:.2f} "
                f"(запас ${limit:.2f}).\n\n"
                f"«Yes» — продовжити цей тест.\n"
                f"«Reset» — почати новий відлік від сьогоднішнього рахунку."
            )
            box.setStandardButtons(QMessageBox.StandardButton.Yes
                                   | QMessageBox.StandardButton.Reset
                                   | QMessageBox.StandardButton.Cancel)
        else:
            box.setInformativeText(
                details +
                "\nДепозит заміряється зараз, і від нього рахується межа 20%.\n"
                "Ордери підуть на Bybit одразу після першого сигналу."
            )
            box.setStandardButtons(QMessageBox.StandardButton.Yes
                                   | QMessageBox.StandardButton.Cancel)

        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        answer = box.exec()

        if answer == QMessageBox.StandardButton.Reset:
            self.new_test = True
        elif answer != QMessageBox.StandardButton.Yes:
            self.trade_status("Запуск скасовано.", ok=False)
            return False

        self.live_confirmed = True
        return True

    @_handle_error
    def configured_balance(self) -> float:
        "Баланс із налаштувань. Потрібен лише тоді, коли біржі немає"
        field = engine.get("input_account_balance")
        try:
            return float(field.text()) if field else 150.0
        except ValueError:
            return 150.0

    #------------------------------
    # Малювання стану такту
    #------------------------------

    @_handle_error
    def set_trade_button(self, running: bool, text: str = None):
        "Перемикає кнопку між Старт і Стоп"
        button = engine.get("btn_trade")
        if not button:
            return
        button.setText(text or ("■  Стоп" if running else "▶  Старт"))
        engine._apply_style(button, "danger" if running else "primary")

    @_handle_error
    def trade_status(self, message: str, ok: bool = True):
        "Рядок стану під кнопкою"
        label = engine.get("trade_status")
        if label:
            label.setText(message)
            engine._apply_style(label, "status_ok" if ok else "status_error")

    @_handle_error
    def trade_log(self, message: str):
        "Дописує рядок у журнал такту"
        log = engine.get("trade_log")
        if not log:
            return
        stamp = time.strftime('%H:%M:%S')
        log.append(f"{stamp}  {message}")
        log.verticalScrollBar().setValue(log.verticalScrollBar().maximum())

    @_handle_error
    def _on_trade_state(self, state: dict):
        "Прийшов стан такту з фонового потоку"
        balance = engine.get("stat_balance")
        if balance:
            balance.setText(f"БАЛАНС\n${state.get('balance', 0):.2f}"
                            f"  зі ${state.get('start_balance', 0):.2f}")

        margin = engine.get("stat_margin")
        if margin:
            margin.setText(f"ЗАСТАВА НА УГОДУ\n${state.get('margin_usd', 0):.2f}")

        drawdown = engine.get("stat_drawdown")
        if drawdown:
            value = state.get('drawdown_pct', 0.0)
            drawdown.setText(f"ПРОСІДАННЯ\n{value:.1f}%  з 20%")
            engine._apply_style(drawdown, "stat_bad" if value >= 10 else "stat")

        self.update_position_badge(state)

        # Закриті угоди помітно в журналі й окремим рядком стану: інакше
        # результат промайнув би між тактами й ніде не лишився
        for event in (state.get('events') or []):
            self.trade_log(f"Угода {event.get('pair')} закрита: {event.get('reason')} "
                           f"{event.get('pnl', 0):+.2f} USDT")

        # Картки: те, що мережа сказала по кожному активу
        best = state.get('signal') or {}
        for pair, verdict in (state.get('verdicts') or {}).items():
            card = self.signal_cards.get(pair)
            if not card:
                continue
            horizons = verdict.get('horizons') or {}
            if not horizons:
                continue

            # Для обраного активу показуємо ТОЙ горизонт, за яким зайшли,
            # для решти — найвпевненіший. Інакше картка обраного активу
            # показувала б інші числа, ніж рядок рішення під кнопкою
            bars = best.get('horizon') if best.get('pair') == pair else None
            if bars not in horizons:
                bars = max(horizons, key=lambda b: horizons[b].get('confidence', 0))
            top = horizons[bars]

            card.update_signal({
                'market_state': f'ГОРИЗОНТ {bars}',
                'signal': top.get('direction', 'NEUTRAL'),
                'confidence': top.get('confidence', 0.0),
                'horizons': horizons,
                'block_reason': '',
            })

        reason = state.get('block_reason')
        if state.get('stopped'):
            self.trade_status(reason or "Рубильник спрацював.", ok=False)
        elif reason:
            self.trade_status(reason, ok=True)
        elif best:
            self.trade_status(
                f"Обрано {best.get('pair')} {best.get('direction')} "
                f"{best.get('confidence', 0) * 100:.1f}% (горизонт {best.get('horizon')})",
                ok=True)

    @_handle_error
    def update_position_badge(self, state: dict):
        "Смужка «позиція відкрита / закрита»"
        badge = engine.get("position_badge")
        if not badge:
            return

        position = state.get('position')
        if state.get('stopped'):
            badge.setText(f"ЗУПИНЕНО — {state.get('block_reason', '')}")
            engine._apply_style(badge, "badge_stopped")
        elif position:
            pnl = position.get('pnl')
            pnl_text = f"  ·  {pnl:+.2f} USDT" if isinstance(pnl, (int, float)) else ""
            badge.setText(
                f"ПОЗИЦІЯ ВІДКРИТА  ·  {position.get('pair')} "
                f"{str(position.get('side', '')).upper()}  ·  "
                f"вхід {position.get('entry_price')}{pnl_text}")
            engine._apply_style(badge, "badge_open")
        elif state.get('waiting'):
            badge.setText(f"РОЗГІН  ·  {state.get('block_reason', '')}")
            engine._apply_style(badge, "badge_idle")
        else:
            badge.setText("ПОЗИЦІЯ ЗАКРИТА  ·  чекаємо сигналу")
            engine._apply_style(badge, "badge_idle")

    @_handle_error
    def _on_trade_finished(self, report: str):
        "Цикл зупинився — сам чи кнопкою"
        self.set_trade_button(running=False)
        self.trade_log(f"Цикл зупинено. {report}")
        self.trade_status("Зупинено. " + report, ok=False)
