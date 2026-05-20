# Документація: Rules Engine (Рушій Правил) ⚙️📈

Цей модуль є ядром створення стратегій для нашого бектестера. Він реалізує паттерн **Domain Specific Language (DSL)**, що дозволяє описувати складні торгові правила як прості, читабельні об'єктно-орієнтовані (OOP) вирази в Python.

Основна перевага рушія — **Ліниві Обчислення (Lazy Evaluation)**. Рушій не розраховує всі існуючі індикатори під час старту. Замість цього, він читає ваші правила, і автоматично генерує лише ті індикатори, патерни чи алгоритми, які потрібні для поточної стратегії "на льоту".

---

## 🏗️ 1. Будівельні блоки (Джерела Даних)

Будь-яка стратегія починається зі збору даних. Для цього існують три основні класи: `Indicator`, `Pattern` та `Algorithm`.

### `Indicator(name)`
Використовується для класичних числових показників (оперує класом `IndicatorProcessor`).
- **Синтаксис:** `Indicator("НАЗВА_ПЕРІОД_ПАРАМЕТР")`
- **Доступні базові значення:** `Indicator("close")`, `Indicator("open")`, `Indicator("high")`, `Indicator("low")`, `Indicator("volume")`
- **Індикатори:** `Indicator("SMA_20")`, `Indicator("EMA_50")`, `Indicator("RSI_14")`, `Indicator("ATR_14")`, `Indicator("CCI_20")`, `Indicator("ADX_14")`, `Indicator("WilliamsR_14")`, `Indicator("Volume_Avg_20")`
- **Індикатори з багатьма параметрами:** `Indicator("MACD_12_26_9")`, `Indicator("MACD_Signal_12_26_9")`, `Indicator("Bollinger_Upper_20_2")`, `Indicator("Bollinger_Lower_20_2")`, `Indicator("Keltner_Upper_20")`
- **Лінійна кластеризація (Market State):** `Indicator("Market_State_Linear_20")` (Повертає: 1 (Up), -1 (Down), 0 (Flat), 3 (Volatility))

### `Pattern(name)`
Використовується для знаходження свічкових формацій (оперує класом `PatternDetector`).

> ⚠️ **Важливо щодо значень, що повертаються:**
> Більшість патернів повертають `True` / `False`, але деякі двосторонні патерни повертають `1` (бичачий) або `-1` (ведмежий):
> ```python
> Pattern("Engulfing") == 1   # Bullish Engulfing (поглинання вгору)
> Pattern("Engulfing") == -1  # Bearish Engulfing (поглинання вниз)
> ```

- **Синтаксис:** `Pattern("Назва_Патерну")` (регістр не має значення).
- **Однонаправлені патерни** (повертають `True`/`False`): `Pattern("Hammer")`, `Pattern("Inverted_Hammer")`, `Pattern("Shooting_Star")`, `Pattern("Morning_Star")`, `Pattern("Evening_Star")`, `Pattern("Piercing_Pattern")`, `Pattern("Dark_Cloud_Cover")`, `Pattern("Three_White_Soldiers")`, `Pattern("Three_Black_Crows")`, `Pattern("Hanging_Man")`.
- **Двонаправлені патерни** (повертають `1` / `-1`): `Pattern("Engulfing")`.

### `Algorithm(name)`
Використовується для "розумних" маркет-мейкер алгоритмів (SMC) та предиктивних AI-моделей. Вони використовують `BacktestAlgorithmProcessor`, щоб гарантувати відсутність "заглядання в майбутнє".
- **Синтаксис:** `Algorithm("НАЗВА")`
- **Доступні SMC алгоритми:** `Algorithm("BOS")`, `Algorithm("CHOCH")`, `Algorithm("FVG")`, `Algorithm("LIQUIDITY_SWEEP")`, `Algorithm("ORDER_BLOCK")`, `Algorithm("MARKET_STRUCTURE")`.
- **NGram AI Прогнози:**
  ```
  Algorithm("NGRAM_ROAD_1")  # передбачає 1 свічку вперед
  Algorithm("NGRAM_ROAD_3")  # консенсус по 3 свічках вперед (сильніший сигнал)
  Algorithm("NGRAM_ROAD_N")  # N — будь-яка кількість свічок вперед
  ```
  Повертає `1` (Buy), `-1` (Sell), `0` (очікування/Doji).
  > ⚠️ Для роботи NGram потрібен попередньо згенерований файл `predictions_road_X.json`. Чим більше `N` — тим сильніший і рідший сигнал.

---

## 🔗 2. Логічні та Математичні оператори

Після вибору блоків, їх потрібно з'єднати. Всі об'єкти підтримують стандартні оператори Python:

### Математичні операції
Ви можете змінювати або комбінувати індикатори прямо в коді:
```python
# Різниця між high та low (розмір свічки)
candle_size = Indicator("high") - Indicator("low")

# Формула з константою
custom_value = Indicator("ATR_14") * 2.5
```

### Порівняння (`>`, `<`, `>=`, `<=`, `==`, `!=`)
Дозволяють перевіряти стан:
```python
is_oversold = Indicator("RSI_14") < 30
is_uptrend = Indicator("Market_State_Linear_20") == 1
```

### Об'єднання умов (`&` (ТА), `|` (АБО))
**Увага:** завжди беріть кожну умову в дужки `()` при використанні `&` та `|` через специфіку пріоритетів у Python.
```python
# Купуємо, коли є Молот І RSI менше 30
buy_signal = (Pattern("Hammer") == True) & (Indicator("RSI_14") < 30)

# Продаємо, коли є Вечірня Зірка АБО падаючий тренд
sell_signal = Pattern("Evening_Star") | (Indicator("Market_State_Linear_20") == -1)
```

### Перетин (CrossOver / CrossUnder)
Використовується для визначення моменту, коли лінія 1 пробиває лінію 2.
Можна викликати двома способами (вони ідентичні):
```python
# Спосіб 1 (Через об'єкт - Fluent Interface):
golden_cross = Indicator("SMA_10").crosses_over(Indicator("SMA_50"))

# Спосіб 2 (Через клас напряму):
from utils.rules_engine import CrossUnder
death_cross = CrossUnder(Indicator("SMA_10"), Indicator("SMA_50"))
```

---

## ⏱️ 3. Управління угодою (Клас `Strategy`)

Стратегія — це фінальний об'єкт, який приймає ваші правила та відповідає за вхід, вихід та часові затримки.

```python
from utils.rules_engine import Strategy

my_strategy = Strategy(
    entry_rule=buy_logic,             # Обов'язково: Коли відкриваємо позицію
    exit_rule=sell_logic,             # Опціонально: Коли закриваємо позицію по логіці
    exit_after_candles=10,            # Опціонально: Примусово закрити угоду через 10 свічок після входу
    delay_entry_candles=1             # Опціонально: Входити не на свічці сигналу, а на наступній (+1)
)
```

---

## 🚀 4. Виконання (Клас `IndicatorRegistry`)

Для того щоб усе це запрацювало на реальних даних, нам потрібен `IndicatorRegistry`. Він бере ваші абстрактні правила і застосовує їх до Pandas DataFrame.

```python
import pandas as pd
from utils.rules_engine import IndicatorRegistry

# 1. Завантажуємо ваші OHLCV дані
df = pd.read_csv("your_data.csv")

# 2. Створюємо реєстр і передаємо йому дані
registry = IndicatorRegistry(df)

# 3. Виконуємо стратегію через реєстр!
results_df = my_strategy.execute(registry)

# results_df тепер містить дві булеві колонки: 'entry' та 'exit'
# Далі ви передаєте results_df до симулятора торгів
```

---

## 💡 Приклади повноцінних стратегій

### Приклад 1: Пробій Боллінджера + Молот (Mean Reversion)
```python
from utils.rules_engine import Indicator, Pattern, Strategy

# ВХІД: Ціна впала нижче нижньої лінії Боллінджера І утворився патерн Молот
entry = (Indicator("close") < Indicator("Bollinger_Lower_20_2")) & (Pattern("Hammer") == True)

# ВИХІД: Ціна торкнулася середньої лінії Боллінджера (SMA)
exit = Indicator("close").crosses_over(Indicator("Bollinger_Middle_20_2"))

strategy = Strategy(
    entry_rule=entry,
    exit_rule=exit,
    exit_after_candles=15 # Запобіжник: якщо ціна не відновлюється 15 свічок - закриваємо
)
```

### Приклад 2: Smart Money + AI (NGram) (Trend Following)
```python
from utils.rules_engine import Indicator, Algorithm, Strategy

# ВХІД: Злам структури вгору (BOS) І AI-прогноз дає сигнал Buy
entry = (Algorithm("BOS") == 1) & (Algorithm("NGRAM_ROAD_1") == 1)

# ВИХІД: Злам структури вниз (CHOCH)
exit = Algorithm("CHOCH") == -1

strategy = Strategy(
    entry_rule=entry,
    exit_rule=exit,
    delay_entry_candles=1 # Чекаємо 1 свічку після BOS для підтвердження
)
```

### Приклад 3: NGram з сильним консенсусом + фільтр тренду
```python
from utils.rules_engine import Indicator, Algorithm, Strategy

# ВХІД: NGram прогнозує Buy на 3 свічки вперед І ринок у висхідному тренді
entry = (Algorithm("NGRAM_ROAD_3") == 1) & (Indicator("Market_State_Linear_20") == 1)

# ВИХІД: NGram дає сигнал Sell АБО RSI перекуплений
exit = (Algorithm("NGRAM_ROAD_3") == -1) | (Indicator("RSI_14") > 70)

strategy = Strategy(
    entry_rule=entry,
    exit_rule=exit,
    exit_after_candles=20
)
```

### Приклад 4: Класичний Golden Cross з фільтром волатильності
```python
from utils.rules_engine import Indicator, Strategy

# ВХІД: Золотий хрест (SMA_10 перетинає SMA_50 вгору) І ринок не у флеті
entry = (
    Indicator("SMA_10").crosses_over(Indicator("SMA_50"))
) & (
    Indicator("Market_State_Linear_20") != 0
)

# ВИХІД: Хрест смерті (SMA_10 перетинає SMA_50 вниз)
exit = Indicator("SMA_10").crosses_under(Indicator("SMA_50"))

strategy = Strategy(
    entry_rule=entry,
    exit_rule=exit,
    delay_entry_candles=1
)
```

---

## ⚠️ 5. Підводні камені та обмеження

| Ситуація | Проблема | Рішення |
|----------|----------|---------|
| `& \|` без дужок | Python обчислює оператори не в тому порядку | Завжди огортай кожну умову в `()` |
| `NGram` без JSON файлу | `FileNotFoundError` при старті | Спочатку запусти генерацію прогнозів через `NGramPredictor` |
| `NGRAM_ROAD_N` з великим N | Сигнали стають дуже рідкими | Починай з `ROAD_1`, збільшуй поступово |
| `Algorithm` + `Indicator` в одній умові | Можливе розузгодження індексів | `IndicatorRegistry` забезпечує єдиний індекс — проблем не буде |
| `exit_after_candles` без `exit_rule` | Угода завжди закривається по таймеру | Комбінуй з `exit_rule` для гнучкості |
| Двонаправлені патерни без `== 1` або `== -1` | Умова завжди `True` | Завжди явно вказуй напрямок для `Engulfing` |
