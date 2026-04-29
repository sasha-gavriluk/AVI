import time
from utils.DataBaseManager import DataBaseManager
from utils.algorithms.backtesting.NGramAnalyzer import NGramAnalyzer
from utils.algorithms.backtesting.MarketRunner import MarketRunner

def main():
    db_path = "trading_data_massive.duckdb"
    table_name = "EURUSD_minute"
    
    print(f"1. Підключення до бази даних: {db_path}, таблиця: {table_name}")
    dbm = DataBaseManager(db_path)
    
    # Перевіримо, чи існує така таблиця взагалі
    tables = dbm.get_all_tables()
    if table_name not in tables:
        print(f"Помилка: Таблиця {table_name} не знайдена в {db_path}. Наявні таблиці: {tables}")
        return

    print("\n2. Ініціалізація NGramAnalyzer...")
    
    # Видалимо стару таблицю результатів, щоб створилася нова з колонками Profit/Balance
    dbm.conn.execute("DROP TABLE IF EXISTS backtest_results")
    
    start_time = time.time()
    
    # Ініціалізуємо аналізатор
    # Він автоматично згенерує predictions.json з таблиці, якщо його ще немає
    analyzer = NGramAnalyzer(
        db_manager=dbm, 
        table_name=table_name, 
        ngram_length=3, 
        min_occurrences=20,
        top_patterns=5, # <--- ДОДАНО ПАРАМЕТР (залишаємо тільки 5 найпопулярніших патернів)
        force_update=False # Встановіть True, якщо хочете примусово оновити прогнози
    )
    
    print(f"NGramAnalyzer успішно ініціалізовано. Час: {time.time() - start_time:.2f} сек.")
    print(f"Завантажено {len(analyzer.predictions)} унікальних патернів.")
    
    print("\n3. Ініціалізація MarketRunner...")
    # MarketRunner приймає екземпляр аналізатора та шлях до БД
    runner = MarketRunner(
        analyzer=analyzer, 
        db_path=db_path, 
        db_table_path=table_name,
        commission=0.0001, # Наприклад
        spread=0.0001,
        initial_balance=10000.0,
        close_on_next_candle=False # <--- Увімкнено авто-закриття
    )
    
    print("\n4. Запуск Бэктесту...")
    backtest_start_time = time.time()
    runner.run()
    print(f"Бэктест завершено за {time.time() - backtest_start_time:.2f} сек.")
    
    print("\n5. Перевірка результатів...")
    # Читаємо згенеровані результати
    results_table = "backtest_results"
    if results_table in dbm.get_all_tables():
        results_df = dbm.get_data_as_dataframe(results_table)
        
        if not results_df.empty:
            total_trades = len(results_df)
            winning_trades = len(results_df[results_df['Profit'] > 0])
            losing_trades = len(results_df[results_df['Profit'] < 0])
            zero_trades = len(results_df[results_df['Profit'] == 0])
            
            gross_profit = results_df[results_df['Profit'] > 0]['Profit'].sum()
            gross_loss = results_df[results_df['Profit'] < 0]['Profit'].sum()
            net_profit = gross_profit + gross_loss
            
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
            
            print("\n" + "="*40)
            print("📊 ДЕТАЛЬНА СТАТИСТИКА БЭКТЕСТУ")
            print("="*40)
            print(f"Всього угод:           {total_trades}")
            print(f"Прибуткових угод (+):  {winning_trades} ({win_rate:.2f}%)")
            print(f"Збиткових угод (-):    {losing_trades} ({(losing_trades/total_trades)*100 if total_trades > 0 else 0:.2f}%)")
            print(f"Угод в нуль (0):       {zero_trades}")
            print("-" * 40)
            print(f"Сумарний прибуток:     {gross_profit:.5f}")
            print(f"Сумарний збиток:       {gross_loss:.5f}")
            print(f"Чистий профіт:         {net_profit:.5f}")
            print("-" * 40)
            print(f"Початковий баланс:     {runner.initial_balance:.5f}")
            print(f"Кінцевий баланс:       {results_df.iloc[-1]['Balance']:.5f}")
            print("="*40)
            
            print("\nОстанні 5 угод (для наочності):")
            print(results_df.tail(5)[['TradeNumber', 'TradeType', 'EntryPrice', 'ExitPrice', 'Profit', 'Balance']])
        else:
            print("Угоди не були здійснені.")
    else:
        print(f"Таблиця {results_table} не була створена. Можливо, не було знайдено жодних сигналів.")

if __name__ == '__main__':
    main()
