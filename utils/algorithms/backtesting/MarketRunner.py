import pandas as pd

from utils.algorithms.backtesting.BaseSettings import BaseSettings
from utils.DataBaseManager import DataBaseManager
from utils.LaboratoryBacktesterDealWriter import LaboratoryBacktesterDealWriter
from utils.rules_engine import Strategy, IndicatorRegistry

#==================================
# Двигун Ринку (Market Runner)
#==================================

class MarketRunner(BaseSettings):

    #------------------------------
    # Ініціалізація
    #------------------------------

    def __init__(self, 
                 strategy,
                 db_path: str = 'main.db',
                 look_ahead: bool = False,
                 commission: float = 0.0,
                 spread: float = 0.0,
                 initial_balance: float = 10000.0,
                 db_table_path: str = None,
                 close_on_next_candle: bool = False,
                 trade_direction: str = 'BUY'):
        """
        Параметри: 
        strategy: екземпляр класу Strategy (з rules_engine)
        db_path: шлях до файлу бази даних DuckDB
        close_on_next_candle: автоматично закривати позицію перед наступною свічкою
        trade_direction: 'BUY' або 'SELL' - тип угод, які відкриватиме стратегія
        """

        # Ініціалізуємо базові налаштування
        super().__init__(look_ahead, commission, spread, initial_balance, db_table_path, close_on_next_candle)
        
        self.strategy = strategy
        self.db_path = db_path
        self.trade_direction = trade_direction.upper()

        import os, json
        self.config_mode = "Standard"
        self.bo_expiration_bars = 1
        
        from utils.PathManager import PathManager
        config_path = PathManager.get_settings_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    mode_data = data.get("trading_mode", {})
                    self.config_mode = mode_data.get("type", "Standard")
                    self.bo_expiration_bars = mode_data.get("bo_expiration_bars", 1)
            except: pass
            
        self.bars_in_trade = 0 # Лічильник барів для поточної угоди
        
    #------------------------------
    # Запуск двигуна бэктесту
    #------------------------------

    def run(self, result_table_name: str = None, df=None):
        """Запуск бэктесту: ініціалізація БД, генерація сигналів та виконання."""

        print("Запуск бэктесту через Rules Engine...")
        
        import time
        if result_table_name is None:
            result_table_name = f'backtest_results_{int(time.time() * 1000)}'
        
        def _execute_run(db, current_df):
            if current_df is None or current_df.empty:
                print(f"Помилка: Дані в таблиці відсутні.")
                return None
                
            print(f"Завантажено {len(current_df)} рядків.")
                
            # Сортуємо по часу для впевненості
            if 'timestamp' in current_df.columns:
                current_df = current_df.dropna(subset=['timestamp'])
                current_df = current_df.sort_values('timestamp').reset_index(drop=True)

            # 1. Запускаємо рушій правил (векторизовано)
            from utils.rules_engine import IndicatorRegistry
            registry = IndicatorRegistry(current_df)
            
            print("Обчислення сигналів стратегії...")
            signals_df = self.strategy.execute(registry)
            
            # Оновлюємо df новими індикаторами, які створив реєстр
            current_df = registry.data
                    
            # 2. Ініціалізуємо Deal Writer
            deal_writer = LaboratoryBacktesterDealWriter(db_manager=db, df=current_df, table_name=self.db_table_path, settings=self)
            
            # 3. Виконуємо ітерацію по розрахованих сигналах
            return self._process_signals(current_df, signals_df, deal_writer, result_table_name=result_table_name)

        if df is not None:
            return _execute_run(None, df)
        else:
            with DataBaseManager(self.db_path) as db:
                if self.db_table_path is None:
                    print("Помилка: Не вказано таблицю з даними (db_table_path).")
                    return None
                    
                # Отримуємо дані для бэктесту
                db_df = db.get_data_as_dataframe(self.db_table_path)
                return _execute_run(db, db_df)

    #------------------------------
    # Процес ітерації по сигналах
    #------------------------------

    def _process_signals(self, df: pd.DataFrame, signals_df: pd.DataFrame, deal_writer: LaboratoryBacktesterDealWriter, result_table_name: str = 'backtest_results'):
        """Метод для переведення булевих сигналів у реальні угоди"""

        current_position = None  # None, 'BUY' або 'SELL'
        current_trade_id = None
        
        # Відстеження стадій пре-сигналу, щоб не спамити (50, 75, 90)
        pre_signal_stage = 0 
        
        print("Виконання угод...")
        for i in range(len(df)):
            current_timestamp = float(df.iloc[i]['timestamp']) if 'timestamp' in df.columns else float(i)
            
            # Отримуємо розраховані рушієм сигнали
            is_entry = bool(signals_df.iloc[i]['entry'])
            is_exit = bool(signals_df.iloc[i]['exit'])
            proximity = float(signals_df.iloc[i]['entry_proximity']) if 'entry_proximity' in signals_df.columns else 0.0

            if current_position is None and not is_entry:
                # Early Warning (Pre-Signal) логіка
                if proximity >= 0.9 and pre_signal_stage < 90:
                    # print(f"[PRE-SIGNAL] {df.iloc[i].get('timestamp_str', current_timestamp)}: Готовність сигналу 90% (Майже сформовано!)")
                    pre_signal_stage = 90
                elif proximity >= 0.75 and proximity < 0.9 and pre_signal_stage < 75:
                    # print(f"[PRE-SIGNAL] {df.iloc[i].get('timestamp_str', current_timestamp)}: Готовність сигналу 75%")
                    pre_signal_stage = 75
                elif proximity >= 0.50 and proximity < 0.75 and pre_signal_stage < 50:
                    # print(f"[PRE-SIGNAL] {df.iloc[i].get('timestamp_str', current_timestamp)}: Готовність сигналу 50%")
                    pre_signal_stage = 50
                elif proximity < 0.3:
                    # Скидаємо стадію, якщо ринок відійшов від сигналу
                    pre_signal_stage = 0
            elif is_entry:
                pre_signal_stage = 0

            # ==========================================
            # 1. ЛОГІКА ВИХОДУ З УГОДИ
            # ==========================================
            if current_position is not None:
                if getattr(self, "config_mode", "Standard") == "Binary Options":
                    # --- РЕЖИМ БІНАРНИХ ОПЦІОНІВ ---
                    # Вихід відбувається ВИКЛЮЧНО по таймеру (кількості барів експірації)
                    self.bars_in_trade += 1
                    
                    if self.bars_in_trade >= getattr(self, "bo_expiration_bars", 1):
                        deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                        current_position = None
                        current_trade_id = None
                        self.bars_in_trade = 0
                else:
                    # --- СТАНДАРТНИЙ РЕЖИМ (CFD / Forex / Crypto) ---
                    # Автоматичне закриття угоди (close_on_next_candle)
                    if self.close_on_next_candle and not is_entry:
                        deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                        current_position = None
                        current_trade_id = None
                    
                    # Вихід по сигналу індикатора
                    elif is_exit:
                        deal_writer._add_trade_exit(timestamp=current_timestamp, id_trade=current_trade_id)
                        current_position = None
                        current_trade_id = None

            # ==========================================
            # 2. ЛОГІКА ВХОДУ В УГОДУ
            # ==========================================
            if is_entry and current_position is None:
                trade_type = 'buy' if self.trade_direction == 'BUY' else 'sell'
                deal_writer._add_trade_entry(trade_type=trade_type, timestamp=current_timestamp)
                latest_trade = deal_writer.id_trade_info.iloc[-1]
                current_trade_id = latest_trade['TradeNumber']
                current_position = self.trade_direction
                
                # Скидаємо лічильник барів при відкритті нової угоди
                self.bars_in_trade = 0 
        
        # Закриваємо позицію в кінці бэктесту, якщо вона залишилась відкритою
        if current_position is not None:
            last_timestamp = float(df.iloc[-1]['timestamp']) if 'timestamp' in df.columns else float(len(df)-1)
            deal_writer._add_trade_exit(timestamp=last_timestamp, id_trade=current_trade_id)
            
        # Зберігаємо результати у базу даних
        try:
            # ВИПРАВЛЕНО: Використовуємо з'єднання з deal_writer замість локального db, якого тут немає
            deal_writer.db_manager.conn.execute(f"DROP TABLE IF EXISTS {result_table_name}")
        except Exception:
            pass
            
        deal_writer.save_results_to_db(table_name=result_table_name)
        print("Бэктест завершено.")
        return deal_writer.id_trade_info