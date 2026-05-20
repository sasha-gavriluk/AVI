import pandas as pd
import uuid

from utils.DataBaseManager import DataBaseManager
from utils.other_utils import _handle_error

#==================================
# Лабораторний бэктестер
#==================================

class LaboratoryBacktesterDealWriter:

    # ----------------------------------
    # Ініціалізація
    # ----------------------------------

    def __init__(self, db_manager: DataBaseManager = None, df: pd.DataFrame = None, table_name: str = None, settings = None):
        """db_manager: об'єкт для роботи з базою даних, df: DataFrame з даними для бэктесту, settings: об'єкт налаштувань"""

        self.db_manager = db_manager
        self.table_name = table_name
        self.df = df
        self.settings = settings
        self.current_balance = settings.initial_balance if settings else 10000.0

        self.id_trade_info = pd.DataFrame(columns=['TradeNumber', 'TradeType', 'EntryPrice', 'EntryTimestamp', 'ExitPrice', 'ExitTimestamp', 'Profit', 'Balance', 'Status'])

        self.df = self._add_trade_columns()

    # ----------------------------------
    # Метод для получення всіх даних з бази даних
    # ----------------------------------

    @_handle_error
    def _get_all_data(self) -> pd.DataFrame:
        """Метод для отримання всіх даних з бази даних table_name: назва таблиці в базі даних"""

        df = self.db_manager.get_data_as_dataframe(self.table_name)

        return df
    
    #----------------------------------
    # Метод для повернення даних для бэктесту
    #----------------------------------

    @_handle_error
    def _get_backtest_data(self) -> pd.DataFrame:
        """Метод для повернення даних для бэктесту"""

        if self.df is not None:
            return self.df
        
        if self.db_manager is not None and self.table_name is not None:
            self.df = self._get_all_data()
            return self.df

        return pd.DataFrame()
    
    #----------------------------------
    # Метод для добавлення нових колонок в дані (TradeEntry, TradeExit)
    #----------------------------------

    @_handle_error
    def _add_trade_columns(self) -> pd.DataFrame:
        """Метод для добавлення нових колонок в дані (TradeEntry, TradeExit)"""

        df = self._get_backtest_data()
        df['TradeNumber'] = pd.Series([None] * len(df))
        df['TradeExit'] = pd.Series([None] * len(df))

        return df
    
    #----------------------------------
    # Метод для добавлення id угод
    #----------------------------------

    @_handle_error
    def _get_trade_id(self, timestamp: float = None) -> int:
        """Метод для добавлення id угод"""

        return str(uuid.uuid4())

    #-----------------------------------
    # Метод для збору інформації про угоду (тип, ціна, час) і позначення її в даних
    #-----------------------------------

    @_handle_error
    def _add_trade_info(self, dictionary: dict = None, trade_type: str = None, price: float = None, timestamp: float = None, end_price: float = None, end_timestamp: float = None, id_trade: int = None, status: str = None) -> pd.DataFrame:
        """Метод для збору інформації про угоду (тип, ціна, час) і позначення її в даних 
            trade_type: тип угоди (buy/sell), 
            price: ціна входу, 
            timestamp: час входу, 
            end_price: ціна виходу, 
            end_timestamp: час виходу
            id_trade: id угоди,
            status: статус угоди (open/closed)"""
        
        if dictionary is not None:
            trade_type = dictionary.get('TradeType')
            price = dictionary.get('EntryPrice')
            timestamp = dictionary.get('EntryTimestamp')
            end_price = dictionary.get('ExitPrice')
            end_timestamp = dictionary.get('ExitTimestamp')
            id_trade = dictionary.get('TradeNumber')
            status = dictionary.get('Status')
            profit = dictionary.get('Profit', 0.0)
            balance = dictionary.get('Balance', self.current_balance)
        else:
            profit = 0.0
            balance = self.current_balance

        info = {
            "TradeNumber": id_trade,
            "TradeType": trade_type,
            "EntryPrice": price,
            "EntryTimestamp": timestamp,
            "ExitPrice": end_price,
            "ExitTimestamp": end_timestamp,
            "Profit": profit,
            "Balance": balance,
            "Status": status if status is not None else ("open" if end_timestamp is None else "closed")
        }

        self.id_trade_info = pd.concat([self.id_trade_info, pd.DataFrame([info])], ignore_index=True)

        return self.id_trade_info
    
    #----------------------------------
    # Метод для оновлення угоди (відкрита/закрита) в даних
    #----------------------------------

    @_handle_error
    def _update_trade_info(self,  dictionary: dict = None, trade_type: str = None, price: float = None, timestamp: float = None, end_price: float = None, end_timestamp: float = None, id_trade: int = None, status: str = None) -> pd.DataFrame:
        """Метод для оновлення угоди (відкрита/закрита) в даних
            trade_type: тип угоди (buy/sell), 
            price: ціна входу, 
            timestamp: час входу, 
            end_price: ціна виходу, 
            end_timestamp: час виходу, 
            id_trade: id угоди, 
            status: статус угоди (open/closed)"""



        profit = None
        balance = None

        if dictionary is not None:
            if "TradeType" in dictionary: trade_type = dictionary.get('TradeType')
            if "EntryPrice" in dictionary: price = dictionary.get('EntryPrice')
            if "EntryTimestamp" in dictionary: timestamp = dictionary.get('EntryTimestamp')
            if "ExitPrice" in dictionary: end_price = dictionary.get('ExitPrice')
            if "ExitTimestamp" in dictionary: end_timestamp = dictionary.get('ExitTimestamp')
            if "Status" in dictionary: status = dictionary.get('Status')              
            if "TradeNumber" in dictionary: id_trade = dictionary.get('TradeNumber')
            if "Profit" in dictionary: profit = dictionary.get('Profit')
            if "Balance" in dictionary: balance = dictionary.get('Balance')

        condition = self.id_trade_info['TradeNumber'] == id_trade

        if trade_type is not None: self.id_trade_info.loc[condition, 'TradeType'] = trade_type
        if price is not None: self.id_trade_info.loc[condition, 'EntryPrice'] = price
        if timestamp is not None: self.id_trade_info.loc[condition, 'EntryTimestamp'] = timestamp
        if end_price is not None: self.id_trade_info.loc[condition, 'ExitPrice'] = end_price
        if end_timestamp is not None: self.id_trade_info.loc[condition, 'ExitTimestamp'] = end_timestamp
        if profit is not None: self.id_trade_info.loc[condition, 'Profit'] = profit
        if balance is not None: self.id_trade_info.loc[condition, 'Balance'] = balance
        if status is not None: self.id_trade_info.loc[condition, 'Status'] = status
        else: self.id_trade_info.loc[condition, 'Status'] = "open" if end_timestamp is None else "closed"

        return self.id_trade_info

    # ----------------------------------
    # Метод для вказівки входу в угоди (купівля або продаж) в даних
    # ----------------------------------

    @_handle_error
    def _add_trade_entry(self, trade_type: str, timestamp: float) -> pd.DataFrame:
        """Метод для вказівки входу в угоди (купівля або продаж) в даних trade_type: тип угоди (buy/sell), price: ціна входу, timestamp: час входу"""
        
        id_trade = self._get_trade_id(timestamp)

        df = self._get_backtest_data()
        condition = df['timestamp'] == float(timestamp)
        matched_rows = df[condition]

        upate_info = {
            "TradeNumber": id_trade,
            "TradeType": trade_type,
            "EntryTimestamp": timestamp,
            "EntryPrice": matched_rows['close'].iloc[0]
        }

        df.loc[condition, 'TradeNumber'] = id_trade
        
        self._add_trade_info(dictionary=upate_info)

        return df

    # ----------------------------------
    # Метод для вказівки виходу з угоди (закриття) в даних
    # ----------------------------------
    
    @_handle_error
    def _add_trade_exit(self, timestamp: float, id_trade: int) -> pd.DataFrame:
        """Метод для вказівки виходу з угоди (закриття) в даних id_trade: id угоди"""

        df = self._get_backtest_data()
        condition = df['timestamp'] == float(timestamp)
        matched_rows = df[condition]
        
        exit_price = matched_rows['close'].iloc[0]
        
        # Обчислення профіту
        condition_trade = self.id_trade_info['TradeNumber'] == id_trade
        trade_row = self.id_trade_info[condition_trade].iloc[0]
        trade_type = trade_row['TradeType']
        entry_price = trade_row['EntryPrice']
        
        commission = self.settings.commission if self.settings else 0.0
        spread = self.settings.spread if self.settings else 0.0
        
        # Профіт (спрощений розрахунок в одиницях ціни)
        if trade_type == 'buy':
            profit = (exit_price - entry_price) - commission - spread
        elif trade_type == 'sell':
            profit = (entry_price - exit_price) - commission - spread
        else:
            profit = 0.0
            
        self.current_balance += profit

        upate_info = {
            "TradeNumber": id_trade,
            "ExitPrice": exit_price,
            "ExitTimestamp": timestamp,
            "Profit": profit,
            "Balance": self.current_balance,
            "Status": "closed"
        }

        self._update_trade_info(dictionary=upate_info)

        return df

    # ----------------------------------
    # Метод для збереження результатів у базу даних
    # ----------------------------------
    
    @_handle_error
    def save_results_to_db(self, table_name: str = 'backtest_results') -> None:
        """Метод для збереження всіх угод в окрему таблицю бази даних (Step 0)"""
        if self.db_manager is not None:
            self.db_manager.insert_data_from_pandas_auto(table_name, self.id_trade_info)
            print(f"Результати бэктесту успішно збережені в таблицю {table_name} (кількість угод: {len(self.id_trade_info)})")
        else:
            print("Помилка: db_manager не передано для збереження результатів.")