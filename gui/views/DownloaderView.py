import os
import sys
import json
import time
import re
import traceback
import pandas as pd
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox, QRadioButton,
    QButtonGroup, QComboBox, QLineEdit, QCheckBox, QDateTimeEdit, QPushButton,
    QProgressBar, QTextEdit, QLabel, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QDateTime

from utils.DataBaseManager import DataBaseManager
from utils.Trading.CCXTModule import CCXTModule
from utils.Trading.MassiveModule import MassiveModule
from utils.config import bybit_key, bybit_secret_key, massive_key

# ============================================================
# СИСТЕМНИЙ СТРІМ-ПЕРЕХОПЛЮВАЧ ДЛЯ КЛАСУ PRINT
# ============================================================

class StringCapture:
    """Перехоплює стандартний вивід sys.stdout і передає його в Qt-сигнал"""
    def __init__(self, signal):
        self.signal = signal

    def write(self, text):
        stripped = text.strip()
        if stripped:
            self.signal.emit(stripped)

    def flush(self):
        pass


# ============================================================
# ФОНОВИЙ ПОТІК ДЛЯ ЗАВАНТАЖЕННЯ ДАНИХ ЧЕРЕЗ КЛАСИ ПРОЄКТУ
# ============================================================

class DownloaderWorker(QThread):
    """
    Фоновий потік, який використовує CCXTModule та MassiveModule
    для асинхронного завантаження котирувань без блокування GUI.
    """
    log_message = pyqtSignal(str)       # Передача логів у вікно (HTML)
    progress_update = pyqtSignal(int)   # Передача прогресу (0-100)
    candles_updated = pyqtSignal(int)   # Оновлення лічильника свічок в реальному часі
    finished_ok = pyqtSignal(int)       # Успішне завершення (кількість свічок)
    finished_error = pyqtSignal(str)    # Помилка

    def __init__(self, settings: dict):
        super().__init__()
        self.settings = settings
        self.is_running = True

    def run(self):
        # Направляємо stdout до нашої консолі, щоб бачити вивід декораторів
        old_stdout = sys.stdout
        sys.stdout = StringCapture(self.log_message)

        try:
            source_type = self.settings["source_type"]  # "massive" або "exchange"
            exchange_name = self.settings["exchange"].lower() # "bybit" або "binance"
            symbols_raw = [s.strip() for s in self.settings["symbols"].split(",") if s.strip()]
            timeframes = self.settings["timeframes"]
            start_ms = self.settings["start_ms"]
            end_ms = self.settings["end_ms"]

            if not symbols_raw:
                self.finished_error.emit("Список активів порожній!")
                return
            if not timeframes:
                self.finished_error.emit("Не обрано таймфрейми!")
                return

            total_tasks = len(symbols_raw) * len(timeframes)
            completed_tasks = 0
            total_loaded_candles = 0

            # ------------------------------------------------------------
            # РЕЖИМ MASSIVE (Збереження в trading_data_massive.duckdb)
            # ------------------------------------------------------------
            if source_type == "massive":
                if not massive_key:
                    self.finished_error.emit("MASSIVE_KEY відсутній в .env файлі! Перевірте налаштування конфігурації.")
                    return

                db_filename = "trading_data_massive.duckdb"
                dbm = DataBaseManager(db_filename)
                
                print(f"📁 Підключення до бази: {db_filename}")
                print(f"🔑 Ініціалізація MassiveModule з вашим API-ключем...")
                
                # Створюємо MassiveModule
                massive_mod = MassiveModule(dbm, massive_key)
                
                # Конвертуємо дати у потрібний формат "YYYY-MM-DD"
                start_date_str = datetime.fromtimestamp(start_ms / 1000).strftime('%Y-%m-%d')
                end_date_str = datetime.fromtimestamp(end_ms / 1000).strftime('%Y-%m-%d')

                # Розрахуємо загальну кількість днів для відображення живого прогресу
                d_start = pd.to_datetime(start_date_str)
                d_end = pd.to_datetime(end_date_str)
                total_days = (d_end - d_start).days
                if total_days <= 0:
                    total_days = 1

                for symbol in symbols_raw:
                    for tf in timeframes:
                        if not self.is_running:
                            print("❌ Завантаження зупинено користувачем.")
                            dbm.disconnect()
                            return

                        # Форматуємо символ (додаємо C: якщо це Forex/CFD і немає префіксу)
                        symbol_formatted = symbol.upper()
                        if not symbol_formatted.startswith("C:"):
                            symbol_formatted = f"C:{symbol_formatted}"

                        print(f"\n📥 [MASSIVE] Початок завантаження {symbol_formatted} [{tf}] з {start_date_str} до {end_date_str}...")
                        
                        # Розбираємо таймфрейм (наприклад, 15m -> 15, "minute")
                        multiplier, tf_unit = self._parse_tf_for_massive(tf)
                        
                        symbol_clean = symbol_formatted.replace(":", "")[1:]
                        suffix_map = {"minute": "m", "hour": "h", "day": "d"}
                        suffix = f"{multiplier}{suffix_map.get(tf_unit, tf_unit)}"
                        table_name = f"{symbol_clean}_{suffix}"

                        # Завантажуємо шматками по 30 днів для живого прогресу
                        current_start = d_start
                        while current_start < d_end:
                            if not self.is_running:
                                break

                            current_end = current_start + pd.Timedelta("30D")
                            if current_end > d_end:
                                current_end = d_end + pd.Timedelta(days=1)

                            # Виклик внутрішнього методу завантаження частини даних
                            massive_mod._fetch_ohlcv(
                                symbol=symbol_formatted,
                                multiplier=multiplier,
                                timeframe=tf_unit,
                                start_date=current_start.strftime('%Y-%m-%d'),
                                end_date=current_end.strftime('%Y-%m-%d')
                            )

                            # Зчитуємо кількість завантажених свічок та надсилаємо в інтерфейс
                            try:
                                count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                                if count_df:
                                    self.candles_updated.emit(total_loaded_candles + count_df[0])
                            except Exception:
                                pass

                            # Розрахунок та відправка прогресу на основі оброблених днів
                            days_done = (current_end - d_start).days
                            percent_done = min(99, int((days_done / total_days) * 100))
                            self.progress_update.emit(percent_done)

                            current_start = current_end
                            time.sleep(1.5)

                        # Після завершення всього циклу для активу зчитуємо остаточну кількість
                        try:
                            count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                            if count_df:
                                total_loaded_candles += count_df[0]
                                self.candles_updated.emit(total_loaded_candles)
                        except Exception:
                            pass

                dbm.disconnect()

            # ------------------------------------------------------------
            # РЕЖИМ БІРЖІ (Кожна біржа у свій файл, наприклад bybit_data.duckdb)
            # ------------------------------------------------------------
            else:
                db_filename = f"{exchange_name}_data.duckdb"
                dbm = DataBaseManager(db_filename)
                
                print(f"📁 Підключення до бази: {db_filename}")
                print(f"🔌 Ініціалізація CCXTModule для {exchange_name.upper()}...")
                
                # Створюємо CCXTModule
                ccxt_mod = CCXTModule(exchange_name, dbm)
                
                # Якщо Bybit і є ключі в .env — підключаємось з ключами
                if exchange_name == "bybit" and bybit_key and bybit_secret_key:
                    print("🔑 Використання API ключів Bybit для автентифікованого з'єднання...")
                    ccxt_mod.connect(bybit_key, bybit_secret_key)
                
                total_range_ms = end_ms - start_ms
                if total_range_ms <= 0:
                    total_range_ms = 1

                for symbol_raw in symbols_raw:
                    # Нормалізуємо символ до біржового вигляду (наприклад, BTCUSDT -> BTC/USDT)
                    symbol = self._normalize_symbol_for_ccxt(symbol_raw)
                    
                    for tf in timeframes:
                        if not self.is_running:
                            print("❌ Завантаження зупинено користувачем.")
                            dbm.disconnect()
                            return

                        print(f"\n📥 [{exchange_name.upper()}] Початок завантаження {symbol} [{tf}]...")
                        
                        # Завантажуємо свічки частинами
                        current_start = start_ms
                        while current_start < end_ms:
                            if not self.is_running:
                                break

                            # Викликаємо fetch_ohlcv з CCXTModule, який розраховує індикатори та записує їх
                            ccxt_mod.fetch_ohlcv(symbol, tf, since=current_start, limit=1000)
                            
                            symbol_clean = symbol.replace("/", "_").replace(":", "_")
                            table_name = f"{symbol_clean}_{tf}"
                            
                            tables = dbm.get_all_tables()
                            if table_name not in tables:
                                print(f"⚠️ Немає даних для {symbol} ({tf}).")
                                break
                                
                            last_df = dbm._get_last_record_as_dataframe(table_name)
                            if last_df.empty:
                                break
                                
                            last_t = int(last_df['timestamp'].iloc[0])
                            if last_t <= current_start:
                                # Більше немає нових свічок
                                break
                                
                            current_start = last_t + 1
                            
                            # Зчитуємо та оновлюємо поточну кількість свічок
                            try:
                                count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                                if count_df:
                                    self.candles_updated.emit(total_loaded_candles + count_df[0])
                            except Exception:
                                pass

                            # Розрахунок та відправка живого прогресу на основі часового діапазону
                            ms_done = last_t - start_ms
                            percent_done = min(99, int((ms_done / total_range_ms) * 100))
                            self.progress_update.emit(percent_done)

                            # Невелика пауза для дотримання лімітів запитів
                            time.sleep(0.3)

                        try:
                            # Оновлюємо остаточну кількість
                            count_df = dbm.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                            if count_df:
                                total_loaded_candles += count_df[0]
                                self.candles_updated.emit(total_loaded_candles)
                        except Exception:
                            pass

                dbm.disconnect()

            # Повертаємо stdout на місце
            sys.stdout = old_stdout
            self.finished_ok.emit(total_loaded_candles)

        except Exception as e:
            sys.stdout = old_stdout
            self.finished_error.emit(traceback.format_exc())

    def stop(self):
        self.is_running = False

    # ============================================================
    # ВНУТРІШНІ УТИЛІТИ ДЛЯ КОНВЕРТАЦІЇ ТА НОРМАЛІЗАЦІЇ
    # ============================================================

    def _parse_tf_for_massive(self, tf: str) -> tuple:
        """Переводить стандартний таймфрейм наприклад '15m' в multiplier (15) та unit ('minute')"""
        match = re.match(r'(\d+)([mhd])', tf)
        if match:
            val = int(match.group(1))
            unit = match.group(2)
        else:
            val = 1
            unit = tf[-1] if tf[-1] in ["m", "h", "d"] else "m"
            
        unit_map = {"m": "minute", "h": "hour", "d": "day"}
        return val, unit_map.get(unit, "minute")

    def _normalize_symbol_for_ccxt(self, symbol: str) -> str:
        """Перетворює злитий символ BTCUSDT у стандартний CCXT-формат BTC/USDT"""
        symbol = symbol.strip().upper()
        if "/" not in symbol:
            # Шукаємо стабільні коіни для додавання роздільника
            for stable in ["USDT", "BUSD", "USDC", "USD", "BTC", "ETH"]:
                if symbol.endswith(stable) and len(symbol) > len(stable):
                    base = symbol[:-len(stable)]
                    return f"{base}/{stable}"
        return symbol


# ============================================================
# ГОЛОВНЕ ВІКНО ЗАВАНТАЖУВАЧА ДАНИХ (GUI)
# ============================================================

class DataDownloaderWindow(QWidget):
    """
    Панель для завантаження котирувань через API з інтеграцією CCXTModule
    та MassiveModule, преміальним інтерфейсом та живою аналітикою.
    """
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        # Головний макет
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Спліттер на ліву (налаштування) та праву (консоль) частини
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ============================================================
        # 1. ЛІВА ПАНЕЛЬ: НАЛАШТУВАННЯ (40%)
        # ============================================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # Заголовок
        header = QLabel("📥 ІНТЕГРОВАНИЙ ЗАВАНТАЖУВАЧ API")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #89B4FA; padding-bottom: 5px;")
        left_layout.addWidget(header)
        
        # Группа Джерела (Massive vs Exchange)
        source_group = QGroupBox("Цільове джерело та база даних")
        source_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                font-weight: bold;
                color: #A6ADC8;
            }
        """)
        source_layout = QVBoxLayout(source_group)
        
        self.radio_massive = QRadioButton("Massive API (База 'trading_data_massive.duckdb')")
        self.radio_massive.setChecked(True)
        self.radio_massive.setStyleSheet("padding: 3px;")
        
        self.radio_exchange = QRadioButton("Біржовий коннектор (Окремі бази, наприклад 'bybit_data.duckdb')")
        self.radio_exchange.setStyleSheet("padding: 3px;")
        
        # Підключаємо перемикач джерела до авто-налаштування символів за замовчуванням
        self.radio_massive.toggled.connect(self._on_source_changed)
        
        source_layout.addWidget(self.radio_massive)
        source_layout.addWidget(self.radio_exchange)
        left_layout.addWidget(source_group)
        
        # Группа вибору біржі
        self.exchange_group = QGroupBox("Вибір Біржі (для біржового коннектору)")
        self.exchange_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
                color: #A6ADC8;
            }
        """)
        exchange_layout = QHBoxLayout(self.exchange_group)
        
        exchange_layout.addWidget(QLabel("Конектор:"))
        self.exchange_combo = QComboBox()
        self.exchange_combo.addItems(["Bybit", "Binance"])
        self.exchange_combo.setStyleSheet("padding: 4px;")
        exchange_layout.addWidget(self.exchange_combo, stretch=1)
        left_layout.addWidget(self.exchange_group)
        
        # Вимикаємо вибір біржі для Massive за замовчуванням
        self.exchange_group.setEnabled(False)
        
        # Группа активів (Symbols)
        symbols_group = QGroupBox("Активи для завантаження")
        symbols_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
                color: #A6ADC8;
            }
        """)
        symbols_layout = QVBoxLayout(symbols_group)
        
        self.symbols_input = QLineEdit("EURUSD, GBPUSD")
        self.symbols_input.setPlaceholderText("Введіть активи через кому, наприклад: BTCUSDT, ETHUSDT")
        symbols_layout.addWidget(self.symbols_input)
        
        # Клікабельні пресети швидкого додавання активів (Топ + Випадаючий список 20+)
        self.presets_row = QHBoxLayout()
        self.presets_row.addWidget(QLabel("Пресети:"))
        self._update_symbol_presets()
        symbols_layout.addLayout(self.presets_row)
        
        left_layout.addWidget(symbols_group)
        
        # Группа Таймфреймів
        tf_group = QGroupBox("Таймфрейми (можна обрати декілька)")
        tf_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
                color: #A6ADC8;
            }
        """)
        tf_grid = QGridLayout(tf_group)
        
        self.tf_checkboxes = {}
        timeframes_list = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        row, col = 0, 0
        for tf in timeframes_list:
            cb = QCheckBox(tf)
            cb.setStyleSheet("padding: 4px;")
            if tf in ["15m", "1h"]:
                cb.setChecked(True)
            tf_grid.addWidget(cb, row, col)
            self.tf_checkboxes[tf] = cb
            col += 1
            if col > 3:
                col = 0
                row += 1
                
        left_layout.addWidget(tf_group)
        
        # Группа Часу
        time_group = QGroupBox("Часовий діапазон")
        time_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
                color: #A6ADC8;
            }
        """)
        time_layout = QVBoxLayout(time_group)
        
        row_start = QHBoxLayout()
        row_start.addWidget(QLabel("Від:"))
        self.date_start = QDateTimeEdit(QDateTime.currentDateTime().addMonths(-3))
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd HH:mm")
        row_start.addWidget(self.date_start, stretch=1)
        time_layout.addLayout(row_start)
        
        row_end = QHBoxLayout()
        row_end.addWidget(QLabel("До:"))
        self.date_end = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd HH:mm")
        row_end.addWidget(self.date_end, stretch=1)
        time_layout.addLayout(row_end)
        
        # Кнопки швидких пресетів часу
        quick_time_layout = QHBoxLayout()
        quick_times = [
            ("7д", -7),
            ("1м", -30),
            ("3м", -90),
            ("1р", -365)
        ]
        for label, days in quick_times:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #313244;
                    color: #CDD6F4;
                    font-size: 11px;
                    padding: 3px 8px;
                    font-weight: normal;
                }
                QPushButton:hover {
                    background-color: #45475A;
                }
            """)
            btn.clicked.connect(lambda checked, d=days: self.set_quick_date(d))
            quick_time_layout.addWidget(btn)
        quick_time_layout.addStretch()
        time_layout.addLayout(quick_time_layout)
        
        left_layout.addWidget(time_group)
        
        # Кнопка запуску
        self.btn_start = QPushButton("🚀 РОЗПОЧАТИ ЗАВАНТАЖЕННЯ")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #A6E3A1;
                color: #11111B;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                margin-top: 15px;
            }
            QPushButton:hover {
                background-color: #94E2D5;
            }
        """)
        self.btn_start.clicked.connect(self.start_downloading)
        left_layout.addWidget(self.btn_start)
        
        left_layout.addStretch()
        
        # ============================================================
        # 2. ПРАВА ПАНЕЛЬ: СТАТУС ТА ЛОГИ (60%)
        # ============================================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # Заголовок правої панелі
        right_layout.addWidget(QLabel("📊 МОНІТОРИНГ ТА ЖИВИЙ ВИВІД МОДУЛІВ"))
        
        # Картки аналітики (Stats Dashboard)
        stats_layout = QHBoxLayout()
        
        self.card_db = self.create_stats_card("ЦІЛЬОВА БД", "trading_data_massive.duckdb", "#89B4FA")
        self.card_candles = self.create_stats_card("ЗАГАЛОМ СВІЧОК", "0", "#A6E3A1")
        self.card_status = self.create_stats_card("СТАТУС АКТИВНОСТІ", "IDLE (Очікування)", "#CDD6F4")
        
        stats_layout.addWidget(self.card_db)
        stats_layout.addWidget(self.card_candles)
        stats_layout.addWidget(self.card_status)
        right_layout.addLayout(stats_layout)
        
        # Прогрес бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #313244;
                background-color: #181825;
                height: 18px;
                text-align: center;
                border-radius: 4px;
                color: #CDD6F4;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #89B4FA;
                border-radius: 3px;
            }
        """)
        right_layout.addWidget(self.progress_bar)
        
        # Консоль логування (Terminal-like)
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("""
            QTextEdit {
                background-color: #11111B;
                color: #A6ADC8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.log_console.setPlaceholderText("Тут у реальному часі відображатиметься логування та вивід print() з CCXTModule/MassiveModule, а також робота декораторів розрахунку індикаторів...")
        right_layout.addWidget(self.log_console)
        
        # Додаємо панелі у спліттер
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        main_layout.addWidget(splitter)

    # ============================================================
    # ДОПОМІЖНІ МЕТОДИ UI
    # ============================================================

    def create_stats_card(self, title: str, value: str, color_hex: str) -> QFrame:
        """Створює преміальну картку статистики (Glassmorphism style)"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        
        t_label = QLabel(title)
        t_label.setStyleSheet("font-size: 10px; font-weight: bold; color: #89DCEB;")
        layout.addWidget(t_label)
        
        v_label = QLabel(value)
        v_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color_hex};")
        v_label.setWordWrap(True)
        layout.addWidget(v_label)
        
        # Додаємо посилання на лейбл значення в об'єкті фрейму
        card.value_label = v_label
        return card

    def append_symbol(self, symbol: str):
        """Додає символ до текстового поля введення активів"""
        current = self.symbols_input.text().strip()
        if not current:
            self.symbols_input.setText(symbol)
        else:
            symbols = [s.strip().upper() for s in current.split(",") if s.strip()]
            if symbol not in symbols:
                symbols.append(symbol)
                self.symbols_input.setText(", ".join(symbols))

    def set_quick_date(self, days: int):
        """Встановлює швидкі дати від поточного моменту"""
        self.date_end.setDateTime(QDateTime.currentDateTime())
        self.date_start.setDateTime(QDateTime.currentDateTime().addDays(days))

    def _on_source_changed(self):
        """Перемикання доступності вибору біржі та пресетів символів"""
        is_massive = self.radio_massive.isChecked()
        self.exchange_group.setEnabled(not is_massive)
        
        # Встановлюємо дефолтні символи залежно від вибору
        if is_massive:
            self.symbols_input.setText("EURUSD, GBPUSD")
        else:
            self.symbols_input.setText("BTCUSDT, ETHUSDT")
            
        self._update_symbol_presets()

    def _update_symbol_presets(self):
        """Оновлює швидкі кнопки та випадаючий список з 20+ популярними активами"""
        # Очищуємо попередні елементи в presets_row
        while self.presets_row.count() > 1:
            item = self.presets_row.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        is_massive = self.radio_massive.isChecked()
        
        # 1. Швидкі кнопки (Топ-4 найпопулярніших)
        top_presets = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"] if is_massive else ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
        
        for p in top_presets:
            btn = QPushButton(p)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #313244;
                    color: #CDD6F4;
                    font-size: 11px;
                    padding: 3px 6px;
                    font-weight: normal;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45475A;
                }
            """)
            btn.clicked.connect(lambda checked, symbol=p: self.append_symbol(symbol))
            self.presets_row.addWidget(btn)
            
        # 2. Випадаючий список з 20 популярними активами для кожного принципу
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
        combo.setStyleSheet("""
            QComboBox {
                background-color: #313244;
                color: #CDD6F4;
                font-size: 11px;
                padding: 2px 6px;
                border: none;
                border-radius: 3px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        combo.activated.connect(lambda index: self._on_preset_combo_activated(combo))
        self.presets_row.addWidget(combo)
        
        self.presets_row.addStretch()

    def _on_preset_combo_activated(self, combo):
        """Обробник вибору активу з великого випадаючого списку"""
        index = combo.currentIndex()
        if index > 0:  # Пропускаємо плейсхолдер
            symbol = combo.itemText(index)
            self.append_symbol(symbol)
            combo.setCurrentIndex(0)  # Скидаємо вибір на плейсхолдер

    # ============================================================
    # ЛОГІКА ЗАПУСКУ ЗАВАНТАЖЕННЯ ЧЕРЕЗ РОБОЧИЙ ПОТІК
    # ============================================================

    def start_downloading(self):
        # Якщо потік вже працює — виконуємо скасування
        if self.worker and self.worker.isRunning():
            self.btn_start.setEnabled(False)
            self.btn_start.setText("⏳ Зупинка...")
            self.worker.stop()
            return

        # Збір налаштувань
        source_type = "massive" if self.radio_massive.isChecked() else "exchange"
        exchange = self.exchange_combo.currentText()
        symbols = self.symbols_input.text().strip()
        
        # Збір таймфреймів
        timeframes = []
        for tf, cb in self.tf_checkboxes.items():
            if cb.isChecked():
                timeframes.append(tf)

        # Конвертація дат в мілісекунди
        start_ms = self.date_start.dateTime().toMSecsSinceEpoch()
        end_ms = self.date_end.dateTime().toMSecsSinceEpoch()

        # Валідація
        if not symbols:
            self.log_console.append("<span style='color: #F38BA8;'>❌ Помилка: Вкажіть хоча б один актив!</span>")
            return
        if not timeframes:
            self.log_console.append("<span style='color: #F38BA8;'>❌ Помилка: Оберіть хоча б один таймфрейм!</span>")
            return
        if start_ms >= end_ms:
            self.log_console.append("<span style='color: #F38BA8;'>❌ Помилка: Дата початку не може бути більшою за дату закінчення!</span>")
            return

        # Очищення та підготовка UI
        self.log_console.clear()
        self.progress_bar.setValue(0)
        self.card_candles.value_label.setText("0")
        
        # Оновлення картки БД
        db_filename = "trading_data_massive.duckdb" if source_type == "massive" else f"{exchange.lower()}_data.duckdb"
        self.card_db.value_label.setText(db_filename)
        
        # Оновлення статусу
        self.card_status.value_label.setText("ACTIVE (Завантаження)")
        self.card_status.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #A6E3A1;")

        # Переналаштування кнопки на режим "Зупинити"
        self.btn_start.setText("🛑 ЗУПИНИТИ ЗАВАНТАЖЕННЯ")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #F38BA8;
                color: #11111B;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                margin-top: 15px;
            }
            QPushButton:hover {
                background-color: #E78284;
            }
        """)

        settings = {
            "source_type": source_type,
            "exchange": exchange,
            "symbols": symbols,
            "timeframes": timeframes,
            "start_ms": start_ms,
            "end_ms": end_ms
        }

        # Створюємо та запускаємо фоновий потік
        self.worker = DownloaderWorker(settings)
        self.worker.log_message.connect(self._on_log_message)
        self.worker.progress_update.connect(self._on_progress_update)
        self.worker.candles_updated.connect(self._on_candles_updated)
        self.worker.finished_ok.connect(self._on_finished_ok)
        self.worker.finished_error.connect(self._on_finished_error)
        self.worker.start()

    # ============================================================
    # ОБРОБНИКИ СИГНАЛІВ ФОНОВОГО ПОТОКУ
    # ============================================================

    @pyqtSlot(str)
    def _on_log_message(self, msg):
        self.log_console.append(msg)
        self.log_console.ensureCursorVisible()

    @pyqtSlot(int)
    def _on_progress_update(self, val):
        self.progress_bar.setValue(val)

    @pyqtSlot(int)
    def _on_candles_updated(self, val):
        self.card_candles.value_label.setText(f"{val:,}")

    @pyqtSlot(int)
    def _on_finished_ok(self, total_candles):
        self.card_candles.value_label.setText(f"{total_candles:,}")
        
        self.card_status.value_label.setText("COMPLETED (Успішно)")
        self.card_status.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #A6E3A1;")

        self.log_console.append("<br/><span style='color: #A6E3A1; font-weight: bold;'>🎉 ЗАВАНТАЖЕННЯ ТА ОБЧИСЛЕННЯ ІНДИКАТОРІВ ЗАВЕРШЕНО УСПІШНО!</span>")
        self.log_console.append(f"Загальна кількість свічок у базі даних: <b>{total_candles:,}</b>")
        self._reset_start_button()

    @pyqtSlot(str)
    def _on_finished_error(self, err_msg):
        self.card_status.value_label.setText("ERROR (Помилка)")
        self.card_status.value_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #F38BA8;")
        
        self.log_console.append(f"<br/><span style='color: #F38BA8; font-weight: bold;'>❌ Критична помилка завантаження:</span><br/>{err_msg}")
        self._reset_start_button()

    def _reset_start_button(self):
        self.btn_start.setEnabled(True)
        self.btn_start.setText("🚀 РОЗПОЧАТИ ЗАВАНТАЖЕННЯ")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #A6E3A1;
                color: #11111B;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
                margin-top: 15px;
            }
            QPushButton:hover {
                background-color: #94E2D5;
            }
        """)

    def get_active_download_db_path(self):
        """Повертає повний шлях до БД, яка зараз завантажується, або None"""
        if self.worker and self.worker.isRunning():
            source_type = "massive" if self.radio_massive.isChecked() else "exchange"
            if source_type == "massive":
                db_filename = "trading_data_massive.duckdb"
            else:
                exchange = self.exchange_combo.currentText()
                db_filename = f"{exchange.lower()}_data.duckdb"
                
            db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db'))
            return os.path.join(db_dir, db_filename)
        return None
