import sys
import os
import pandas as pd

# Обхід блокування в бібліотеці finplot для певних локалей:
os.environ["LANG"] = "en_US.UTF-8"
os.environ["LC_ALL"] = "en_US.UTF-8"
import finplot as fplt

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMenuBar
from PyQt6.QtGui import QAction

# Використовуємо конфіг для шляхів
from utils.DataBaseManager import DataBaseManager
from utils.config import db_dir

class TradingChartApp(QWidget):
    def __init__(self):
        super().__init__()
        
        self.layout = QVBoxLayout(self)
        
        self.ax = None
        self.current_db = None
        self.current_table = None
        self.df = None
        self.trades_drawn = False
        self.current_trades_table = "backtest_results"
        self.is_loading = False
        
        # Налаштування кольорів Finplot
        fplt.foreground = '#eef'
        fplt.background = '#1e1f22'
        fplt.odd_plot_background = '#25262a'
        fplt.cross_hair_color = '#fff'
        
        self._init_menu()
        self._load_all_tables()
        
        # При старті автоматично завантажуємо перший актив (якщо бази не пусті)
        if self.available_assets:
            first_db, first_table = self.available_assets[0]
            self.load_chart(first_db, first_table)

    def _init_menu(self):
        menubar = QMenuBar(self)
        self.layout.setMenuBar(menubar)
        
        self.asset_menu = menubar.addMenu("Актив")
        
        # Додаємо меню Таймфрейм з однією кнопкою 15m
        self.tf_menu = menubar.addMenu("Таймфрейм")
        tf_action = QAction("15m", self)
        tf_action.setCheckable(True)
        tf_action.setChecked(True)
        self.tf_menu.addAction(tf_action)
        
        self.show_menu = menubar.addMenu("Вигляд")
        
        self.show_trades_menu = self.show_menu.addMenu("Відобразити угоди з тесту...")
        
        self.reset_cam_action = QAction("Скинути камеру", self)
        self.reset_cam_action.triggered.connect(self.reset_camera)
        self.show_menu.addAction(self.reset_cam_action)

    def _load_all_tables(self):
        self.available_assets = []
        
        # Шукаємо всі бази .duckdb у папці data/db
        if not os.path.exists(db_dir):
            print("Папка з базами даних не знайдена!")
            return
            
        dbs = [f for f in os.listdir(db_dir) if f.endswith('.duckdb')]
        
        for db in dbs:
            try:
                dbm = DataBaseManager(use_default=True)
                tables = dbm.get_all_tables()
                dbm.disconnect()
                
                for t in tables:
                    # Фільтруємо системні таблиці та будь-які результати бектестів
                    if "backtest" not in t.lower() and not t.startswith("sqlite_"):
                        action = QAction(f"{t} ({db})", self)
                        # Замикаємо значення в lambda
                        action.triggered.connect(lambda checked, d=db, t_name=t: self.load_chart(d, t_name))
                        self.asset_menu.addAction(action)
                        self.available_assets.append((db, t))
            except Exception as e:
                print(f"Помилка зчитування БД {db}: {e}")

    def load_chart(self, db_name, table_name):
        if table_name == "backtest_results" or table_name.startswith("backtest_"):
            print(f"Таблицю {table_name} неможливо відкрити як графік свічок.")
            return
            
        self.current_db = db_name
        self.current_table = table_name
        self.trades_drawn = False
        
        # Завантажуємо дані
        dbm = DataBaseManager(use_default=True)
        # Початково завантажуємо останні 1000 свічок
        df = dbm.get_data_by_number_range(table_name, 1000)
        dbm.disconnect()
        
        if df is None or df.empty:
            print(f"Даних для {table_name} не знайдено.")
            return
            
        # Розворочуємо та готуємо час
        df = df.sort_values('timestamp')
        df['time'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('time', inplace=True)
        self.df = df
        
        # Замість того, щоб видаляти віджет і створювати новий (що ламає Finplot),
        # ми створюємо його ОДИН РАЗ, а далі просто очищуємо і малюємо заново.
        if self.ax is None:
            self.ax = fplt.create_plot()
            self.layout.addWidget(self.ax.vb.win)
            # Підключаємо подію зміни X-діапазону для динамічної підгрузки
            self.ax.vb.sigXRangeChanged.connect(self.on_x_range_changed)
        else:
            self.ax.clear()
            self.ax.vb.reset()
            # Скидаємо старий датасорс
            if hasattr(self.ax.vb, 'datasrc'):
                self.ax.vb.datasrc = None
        
        # Малюємо свічки на наявному графіку
        df_chart = df[['open', 'close', 'high', 'low']]
        fplt.candlestick_ochl(df_chart, ax=self.ax)
        
        fplt.refresh()
        
        # Скидаємо камеру на останні свічки (замість autoviewrestore, який показує весь графік)
        self.reset_camera()
        
        # Оновлюємо динамічне меню угод для цієї БД
        self.update_trades_menu()

    def reset_camera(self):
        """Ініціює скидання камери з невеликою затримкою (щоб finplot встиг відрендеритись)"""
        fplt.timer_callback(self._do_reset_camera, 0.1, single_shot=True)

    def _do_reset_camera(self):
        """Зближує графік до останніх 150 свічок з правильним масштабуванням по Y"""
        if self.ax and self.df is not None and not self.df.empty:
            x_max = len(self.df) - 1
            x_min = max(0, x_max - 150)
            
            # Рахуємо межі по Y для цих 150 свічок, щоб уникнути "сплющення" графіка
            visible_df = self.df.iloc[x_min : x_max+1]
            y_min = visible_df['low'].min()
            y_max = visible_df['high'].max()
            
            # Додаємо відступ по Y
            y_padding = (y_max - y_min) * 0.1
            y_min -= y_padding
            y_max += y_padding
            
            # Встановлюємо діапазон по осі X та Y
            self.ax.vb.setXRange(x_min, x_max + 10, padding=0)
            self.ax.vb.setYRange(y_min, y_max, padding=0)

    def on_x_range_changed(self, vb, xrange):
        """Відслідковуємо, чи користувач проскролив до початку графіка"""
        if xrange[0] < 100 and not self.is_loading:
            self.load_more_data()

    def load_more_data(self):
        if self.df is None or self.df.empty or not self.current_db:
            return
            
        self.is_loading = True
        print("Динамічна підгрузка: завантажуємо ще 1000 свічок...")
        
        dbm = DataBaseManager(use_default=True)
        # Знаходимо найстаріший timestamp з існуючих даних
        earliest_timestamp = int(self.df['timestamp'].iloc[0])
        
        query = f"SELECT * FROM {self.current_table} WHERE timestamp < {earliest_timestamp} ORDER BY timestamp DESC LIMIT 1000"
        new_df = dbm.conn.execute(query).fetchdf()
        dbm.disconnect()
        
        if new_df.empty:
            print("Більше старих даних немає.")
            self.is_loading = False
            return
            
        new_df = new_df.sort_values('timestamp')
        new_df['time'] = pd.to_datetime(new_df['timestamp'], unit='ms')
        new_df.set_index('time', inplace=True)
        
        added_count = len(new_df)
        
        # Додаємо старі дані перед поточними
        self.df = pd.concat([new_df, self.df])
        
        # Зберігаємо поточну позицію камери перед перемалюванням
        (x_min, x_max), (y_min, y_max) = self.ax.vb.viewRange()
        
        # Перемальовуємо графік
        self.ax.clear()
        self.ax.vb.reset()
        if hasattr(self.ax.vb, 'datasrc'):
            self.ax.vb.datasrc = None
            
        df_chart = self.df[['open', 'close', 'high', 'low']]
        fplt.candlestick_ochl(df_chart, ax=self.ax)
        
        # Відновлюємо камеру зі зміщенням по X (бо індекси зсунулися на added_count)
        self.ax.vb.setXRange(x_min + added_count, x_max + added_count, padding=0)
        self.ax.vb.setYRange(y_min, y_max, padding=0)
        
        # Якщо були намальовані угоди, перемальовуємо їх
        if self.trades_drawn:
            self.trades_drawn = False
            self.show_trades(self.current_trades_table)
            
        fplt.refresh()
        self.is_loading = False

    def show_trades(self, trades_table="backtest_results"):
        if self.ax is None or self.df is None or self.current_db is None:
            return
            
        self.current_trades_table = trades_table
            
        if self.trades_drawn:
            print("Угоди вже відображені на графіку.")
            return
            
        dbm = DataBaseManager(use_default=True)
        tables = dbm.get_all_tables()
        if trades_table not in tables:
            print(f"Таблиця угод ({trades_table}) не знайдена в цій базі.")
            dbm.disconnect()
            return
            
        trades_df = dbm.get_data_as_dataframe(trades_table)
        dbm.disconnect()
        
        if trades_df.empty:
            print("Таблиця угод пуста.")
            return
            
        trades_plotted = 0
        
        # Створюємо порожні Series для маркерів (NaN) з таким самим часовим індексом
        entries = pd.Series(index=self.df.index, dtype=float)
        exits = pd.Series(index=self.df.index, dtype=float)
        
        # Проходимося по кожній угоді
        for _, trade in trades_df.iterrows():
            entry_time = pd.to_datetime(trade['EntryTimestamp'], unit='ms')
            exit_time = pd.to_datetime(trade['ExitTimestamp'], unit='ms')
            
            # Додаємо маркер відкриття зверху над свічкою
            if entry_time in self.df.index:
                # Зміщуємо трохи вище High свічки (на 0.05%)
                high_price = self.df.loc[entry_time, 'high']
                entries.loc[entry_time] = high_price + (high_price * 0.0005)
                trades_plotted += 1
                
            # Додаємо маркер закриття знизу під свічкою
            if exit_time in self.df.index:
                # Зміщуємо трохи нижче Low свічки (на 0.05%)
                low_price = self.df.loc[exit_time, 'low']
                exits.loc[exit_time] = low_price - (low_price * 0.0005)
            
        if trades_plotted > 0:
            # Малюємо маркери відкриття (синій трикутник вниз 'v' над свічкою)
            fplt.plot(entries, style='v', color='#0000ff', legend='Відкриття')
            # Малюємо маркери закриття (червоний трикутник вгору '^' під свічкою)
            fplt.plot(exits, style='^', color='#ff0000', legend='Закриття')
            
            # Оновлюємо графіку
            fplt.refresh()
            print(f"Відображено {trades_plotted} угод(и) на поточному графіку.")
            self.trades_drawn = True
        else:
            print("На цьому відрізку/активі угод немає.")

    def load_backtest(self, db_name, trades_table):
        """Метод для завантаження графіку з результатами бектесту"""
        if not self.available_assets:
            print("Немає доступних активів для відображення.")
            return
            
        # Намагаємось автоматично розпізнати актив з назви таблиці результатів (backtest_[Asset]_[TestName])
        base_table = None
        for db, tbl in self.available_assets:
            if db == db_name and trades_table.startswith(f"backtest_{tbl}_"):
                base_table = tbl
                break
                
        if not base_table:
            # Спроба 2: пошук збігу підстроки
            for db, tbl in self.available_assets:
                if db == db_name and tbl in trades_table:
                    base_table = tbl
                    break
                    
        if not base_table:
            base_table = self.available_assets[0][1]
            
        # Спочатку вантажимо свічки
        self.load_chart(db_name, base_table)
        
        # Потім малюємо маркери
        self.show_trades(trades_table)

    def update_trades_menu(self):
        """Динамічно оновлює список доступних таблиць угод у меню 'Вигляд -> Відобразити угоди...'"""
        self.show_trades_menu.clear()
        if not self.current_db or not self.current_table:
            return
            
        try:
            dbm = DataBaseManager(use_default=True)
            tables = dbm.get_all_tables()
            dbm.disconnect()
            
            # Шукаємо всі таблиці, які відносяться до нашого поточного активу self.current_table
            prefix = f"backtest_{self.current_table}_"
            backtest_tables = [t for t in tables if t.startswith(prefix)]
            
            if not backtest_tables:
                no_actions = QAction(f"Немає бектестів для {self.current_table}", self)
                no_actions.setEnabled(False)
                self.show_trades_menu.addAction(no_actions)
                return
                
            for bt in backtest_tables:
                # Вирізаємо префікс, щоб залишити лише чисту назву тесту для відображення
                display_name = bt.replace(prefix, "")
                action = QAction(f"{display_name} ({self.current_table})", self)
                action.triggered.connect(lambda checked, t_name=bt: self.show_trades_via_menu(t_name))
                self.show_trades_menu.addAction(action)
        except Exception as e:
            print(f"Помилка оновлення меню угод: {e}")

    def show_trades_via_menu(self, trades_table):
        # Дозволяємо перемалювати угоди
        self.trades_drawn = False
        
        # Перемальовуємо графік, щоб стерти старі угоди
        self.ax.clear()
        self.ax.vb.reset()
        if hasattr(self.ax.vb, 'datasrc'):
            self.ax.vb.datasrc = None
        
        df_chart = self.df[['open', 'close', 'high', 'low']]
        fplt.candlestick_ochl(df_chart, ax=self.ax)
        self.reset_camera()
        
        # Малюємо нові угоди
        self.show_trades(trades_table)

