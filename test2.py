from Trading.MassiveModule import MassiveModule
from utils.DataBaseManager import DataBaseManager
from algorithms.NGramPredictor import NGramPredictor

import pandas as pd

from utils.config import massive_key

dbm = DataBaseManager("trading_data_massive.duckdb")
r = dbm.get_data_as_dataframe("EURUSD_minute").drop_duplicates()

ngram_predictor = NGramPredictor(r)
trigrams = ngram_predictor._analysis(column_name="WCE", num_tokens=3, top=10, min_occurrences=20, use_fuzzy_logic=True)
print(trigrams)
ngram_predictor.save_predictions_to_file()

print(len(r))


# mm = MassiveModule(dbm, massive_key)
# r = mm.fetch_ohlcv_auto_download(symbol="C:EURUSD", multiplier=15, timeframe="minute", start_date="2025-04-26", end_date="2026-04-26", limit=50000, batch_size="30D", time_sleep=int(15))

# table_name = "EURUSD_minute"
# timeframe_ms = 15 * 60 * 1000

# gaps = dbm.get_time_gaps(table_name, timeframe_ms=timeframe_ms)
# df = dbm.get_data_as_dataframe(table_name)

# timestamps = set(df["timestamp"].tolist())
# df_sorted = df.sort_values("timestamp").copy()
# df_sorted["prev_timestamp"] = df_sorted["timestamp"].shift(1)
# df_sorted["diff_ms"] = df_sorted["timestamp"] - df_sorted["prev_timestamp"]

# duplicate_count = df["timestamp"].duplicated().sum()
# step_counts = df_sorted["diff_ms"].value_counts().head(10)

# print(f"Таблиця: {table_name}")
# print(f"Всього рядків у get_data_as_dataframe: {len(df)}")
# print(f"Дублікатів timestamp: {duplicate_count}")
# print("Найчастіші кроки між сусідніми timestamp:")
# print(step_counts)
# print("-" * 80)

# print(f"Знайдено прогалин get_time_gaps: {len(gaps)}")
# print("-" * 80)

# for index, gap in enumerate(gaps[:20], start=1):
#     gap_start = gap["gap_start"]
#     gap_end = gap["gap_end"]
#     diff = gap_end - gap_start
#     gap_start_dt = pd.to_datetime(gap_start, unit="ms", utc=True)
#     gap_end_dt = pd.to_datetime(gap_end, unit="ms", utc=True)

#     expected_missing = list(range(
#         int(gap_start + timeframe_ms),
#         int(gap_end),
#         timeframe_ms
#     ))

#     existing_inside_gap = df[
#         (df["timestamp"] > gap_start) &
#         (df["timestamp"] < gap_end)
#     ]["timestamp"].tolist()

#     missing_timestamps = [
#         timestamp for timestamp in expected_missing
#         if timestamp not in timestamps
#     ]

#     print(f"Прогалина #{index}")
#     print(f"  gap_start є в даних: {gap_start in timestamps} | {gap_start} | {gap_start_dt} | {gap_start_dt.day_name()}")
#     print(f"  gap_end є в даних:   {gap_end in timestamps} | {gap_end} | {gap_end_dt} | {gap_end_dt.day_name()}")
#     print(f"  різниця ms: {diff}")
#     print(f"  різниця годин: {round(diff / 1000 / 60 / 60, 2)}")
#     print(f"  очікуваний крок ms: {timeframe_ms}")
#     print(f"  очікувано відсутніх timestamp всередині: {len(expected_missing)}")
#     print(f"  реально знайдено рядків всередині проміжку: {len(existing_inside_gap)}")
#     print(f"  перші відсутні: {missing_timestamps[:5]}")
#     print("-" * 80)

# if len(gaps) > 20:
#     print(f"Показано перші 20 прогалин із {len(gaps)}")
