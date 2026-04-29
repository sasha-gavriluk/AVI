# from Trading.ccxt_module import CCXTModule
# from Trading.massive_module import MassiveModule
from utils.DataBaseManager import DataBaseManager
# from utils.config import bybit_key, bybit_secret_key, massive_key

# db_manager_ccxt = DataBaseManager("trading_data.duckdb")
db_manager_massive = DataBaseManager("trading_data_massive.duckdb")

# bybit = CCXTModule("bybit", db_manager_ccxt)
# bybit.connect(bybit_key, bybit_secret_key)
# bybit.fetch_ohlcv("BTC/USDT", "1m", None, 10)



# mm = MassiveModule(db_manager_massive, massive_key)
# r = mm.fetch_ohlcv("C:EURUSD", 15, "minute", "2025-01-01", "2025-01-16", limit=50000)

import sys
from gui.OpenGraphicsView import OpenGraphicsView
from PyQt6.QtWidgets import QApplication

# ============================
# Головна функція для запуску програми
# ============================

def main():
    app = QApplication(sys.argv)
    window = OpenGraphicsView(db_manager_massive)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()