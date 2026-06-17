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

        import os, json
        self.config_mode = "Standard"
        self.bo_payout = 80.0
        self.bo_bet_size = 10.0
        
        self.std_sizing_type = "Фіксована сума ($)"
        self.std_sizing_value = 1000.0
        self.std_commission = 0.1
        
        self.fut_sizing_type = "Фіксована маржа ($)"
        self.fut_sizing_value = 100.0
        self.fut_leverage = 10
        self.fut_taker_fee = 0.05
        self.fut_maker_fee = 0.02
        
        from utils.PathManager import PathManager
        config_path = PathManager.get_settings_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    mode_data = data.get("trading_mode", {})
                    self.config_mode = mode_data.get("type", "Standard")
                    self.bo_payout = mode_data.get("bo_payout_percent", 80.0)
                    self.bo_bet_size = mode_data.get("bo_bet_size", 10.0)
                    
                    self.std_sizing_type = mode_data.get("standard_sizing_type", "Фіксована сума ($)")
                    self.std_sizing_value = mode_data.get("standard_sizing_value", 1000.0)
                    self.std_commission = mode_data.get("standard_commission_percent", 0.1)
                    
                    self.fut_sizing_type = mode_data.get("futures_sizing_type", "Фіксована маржа ($)")
                    self.fut_sizing_value = mode_data.get("futures_sizing_value", 100.0)
                    self.fut_leverage = mode_data.get("futures_leverage", 10)
                    self.fut_taker_fee = mode_data.get("futures_taker_fee", 0.05)
                    self.fut_maker_fee = mode_data.get("futures_maker_fee", 0.02)
                    
                    if not settings:
                        risk_data = data.get("risk_management", {})
                        if "initial_balance" in risk_data:
                            self.current_balance = risk_data["initial_balance"]
            except Exception:
                pass

        self.id_trade_info = pd.DataFrame(columns=['TradeNumber', 'TradeType', 'EntryPrice', 'EntryTimestamp', 'ExitPrice', 'ExitTimestamp', 'Profit', 'Quantity', 'Balance', 'Status'])
        self.trades_list = []

    # ----------------------------------
    # Метод для вказівки входу в угоди (купівля або продаж) в даних
    # ----------------------------------

    @_handle_error
    def _add_trade_entry(self, trade_type: str, timestamp: float, price: float):
        """Метод для вказівки входу в угоди (купівля або продаж) в даних trade_type: тип угоди (buy/sell), timestamp: час входу, price: ціна входу"""
        id_trade = str(uuid.uuid4())
        qty = 1.0 # Default fallback
        
        if self.config_mode == "Standard":
            if self.std_sizing_type == "Фіксована сума ($)":
                qty = self.std_sizing_value / price if price > 0 else 0
            elif self.std_sizing_type == "% від балансу":
                amount = self.current_balance * (self.std_sizing_value / 100.0)
                qty = amount / price if price > 0 else 0
            else: # Фіксована кількість
                qty = self.std_sizing_value
        elif self.config_mode == "Futures":
            if self.fut_sizing_type == "Фіксована маржа ($)":
                margin = self.fut_sizing_value
                notional = margin * self.fut_leverage
                qty = notional / price if price > 0 else 0
            elif self.fut_sizing_type == "% від балансу":
                margin = self.current_balance * (self.fut_sizing_value / 100.0)
                notional = margin * self.fut_leverage
                qty = notional / price if price > 0 else 0
            else: # Фіксована кількість
                qty = self.fut_sizing_value

        trade = {
            "TradeNumber": id_trade,
            "TradeType": trade_type,
            "EntryPrice": price,
            "EntryTimestamp": timestamp,
            "ExitPrice": None,
            "ExitTimestamp": None,
            "Profit": 0.0,
            "Quantity": qty,
            "Balance": self.current_balance,
            "Status": "open"
        }
        self.trades_list.append(trade)

    # ----------------------------------
    # Метод для вказівки виходу з угоди (закриття) в даних
    # ----------------------------------
    
    @_handle_error
    def _add_trade_exit(self, timestamp: float, price: float, id_trade: str):
        """Метод для вказівки виходу з угоди (закриття) в даних timestamp: час виходу, price: ціна виходу, id_trade: id угоди"""

        if not self.trades_list:
            return

        # Зазвичай остання угода і є тою, що закривається
        trade = self.trades_list[-1]
        if trade["TradeNumber"] != id_trade:
            # Шукаємо з кінця, якщо це не остання
            for t in reversed(self.trades_list):
                if t["TradeNumber"] == id_trade:
                    trade = t
                    break
            else:
                return

        exit_price = price
        trade_type = trade["TradeType"]
        entry_price = trade["EntryPrice"]
        
        # Обчислення профіту
        if getattr(self, "config_mode", "Standard") == "Binary Options":
            if trade_type == 'buy':
                if exit_price > entry_price:
                    profit = self.bo_bet_size * (self.bo_payout / 100.0)
                elif exit_price < entry_price:
                    profit = -self.bo_bet_size
                else:
                    profit = 0.0 # Нічия
            elif trade_type == 'sell':
                if exit_price < entry_price:
                    profit = self.bo_bet_size * (self.bo_payout / 100.0)
                elif exit_price > entry_price:
                    profit = -self.bo_bet_size
                else:
                    profit = 0.0 # Нічия
            else:
                profit = 0.0
        elif self.config_mode == "Futures":
            qty = trade.get("Quantity", 1.0)
            
            if trade_type == 'buy':
                gross_profit = qty * (exit_price - entry_price)
            elif trade_type == 'sell':
                gross_profit = qty * (entry_price - exit_price)
            else:
                gross_profit = 0.0
                
            entry_fee = (qty * entry_price) * (self.fut_taker_fee / 100.0)
            exit_fee = (qty * exit_price) * (self.fut_taker_fee / 100.0)
            
            profit = gross_profit - entry_fee - exit_fee
            
            # Check liquidation/margin call
            if self.fut_sizing_type == "Фіксована маржа ($)":
                margin = self.fut_sizing_value
            elif self.fut_sizing_type == "% від балансу":
                margin = self.current_balance * (self.fut_sizing_value / 100.0)
            else:
                margin = (qty * entry_price) / self.fut_leverage
                
            if profit < -margin:
                profit = -margin # Liquidated
                
        else:
            # СТАНДАРТНИЙ РОЗРАХУНОК (Спот)
            qty = trade.get("Quantity", 1.0)

            if trade_type == 'buy':
                gross_profit = qty * (exit_price - entry_price)
            elif trade_type == 'sell':
                gross_profit = qty * (entry_price - exit_price)
            else:
                gross_profit = 0.0
                
            entry_fee = (qty * entry_price) * (self.std_commission / 100.0)
            exit_fee = (qty * exit_price) * (self.std_commission / 100.0)
            
            profit = gross_profit - entry_fee - exit_fee
            
        self.current_balance += profit

        trade["ExitPrice"] = exit_price
        trade["ExitTimestamp"] = timestamp
        trade["Profit"] = profit
        trade["Balance"] = self.current_balance
        trade["Status"] = "closed"

    # ----------------------------------
    # Метод для фіналізації угод у DataFrame
    # ----------------------------------
    def finalize_trades(self):
        if self.trades_list:
            self.id_trade_info = pd.DataFrame(self.trades_list)
        return self.id_trade_info

    # ----------------------------------
    # Метод для збереження результатів у базу даних
    # ----------------------------------
    
    @_handle_error
    def save_results_to_db(self, table_name: str = 'backtest_results') -> None:
        """Метод для збереження всіх угод в окрему таблицю бази даних (Step 0)"""
        self.finalize_trades()
        if self.db_manager is not None:
            self.db_manager.insert_data_from_pandas_auto(table_name, self.id_trade_info)
            print(f"Результати бэктесту успішно збережені в таблицю {table_name} (кількість угод: {len(self.id_trade_info)})")
        else:
            # Не показуємо помилку, якщо db_manager немає, бо для AI Copilot (training) нам база іноді не потрібна
            pass