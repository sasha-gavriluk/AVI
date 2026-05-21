import os
import sys
import traceback

# Додаємо корінь проекту в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from utils.rules_engine import Algorithm, Strategy
from utils.algorithms.backtesting.MarketRunner import MarketRunner

def test_ngram():
    print("1. Ініціалізація тестової стратегії N-GRAM...")
    # Звертаємось до твого алгоритму N-Gram
    ngram = Algorithm("NGRAM_ROAD_60")
    
    entry = (ngram == 1)
    exit = (ngram == -1)
    
    strategy = Strategy(entry_rule=entry, exit_rule=exit)
    
    # ВАЖЛИВО: Заміни "EURUSD_15m" на ту таблицю, яка ТОЧНО є у твоїй БД
    test_table = "EURUSD_15m" 
    
    print(f"2. Запуск MarketRunner для таблиці {test_table}...")
    runner = MarketRunner(
        strategy=strategy,
        db_path="main.duckdb",
        db_table_path=test_table
    )
    
    try:
        # Запускаємо бектест. Саме тут Rules Engine викличе N-Gram алгоритм,
        # який полізе генерувати/зберігати json і впаде з помилкою.
        results_df = runner.run(result_table_name="test_ngram_debug")
        
        if results_df is not None:
            print(f"\n✅ Тест пройшов успішно! Кількість угод: {len(results_df)}")
        else:
            print("\n⚠️ Тест завершився, але повернув None.")
            
    except Exception as e:
        print("\n" + "="*50)
        print("❌ СПІЙМАНО КРИТИЧНУ ПОМИЛКУ N-GRAM АЛГОРИТМУ!")
        print("="*50)
        traceback.print_exc()  # Виведе точний рядок, де впав твій код
        print("="*50)

if __name__ == "__main__":
    test_ngram()