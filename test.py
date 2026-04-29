from utils.DataBaseManager import DataBaseManager
from utils.LaboratoryBacktesterDealWriter import LaboratoryBacktesterDealWriter

dbm = DataBaseManager("trading_data_massive.duckdb")
r = dbm.get_data_as_dataframe("EURUSD_minute").drop_duplicates()
print(r)

backtester = LaboratoryBacktesterDealWriter(db_manager=dbm, table_name="EURUSD_minute")
# backtester = LaboratoryBacktesterDealWriter(df=r)

entry1 = backtester._add_trade_entry("buy", 1739918700000)
entry2 = backtester._add_trade_entry("buy", 1739919600000)
entry3 = backtester._add_trade_entry("buy", 1739920500000)
entry4 = backtester._add_trade_entry("buy", 1739921400000)
entry5 = backtester._add_trade_entry("buy", 1739922300000)

_exit = backtester._add_trade_exit(1739922300000, 3479841000000)

print(backtester.id_trade_info)