# Архітектура "Автономного Копілота" (Copilot)

Живий довідковий документ. Описує все, що стосується вкладки "Автономний
Копілот", **КРІМ** `utils/algorithms/CopilotAlgorithmicLogic.py` (NN-логіка
документована окремо). Розділ "Журнал змін" в кінці — сюди дописувати кожну
правку, яку вносимо в цю систему надалі, щоб не загубити швидкий доступ до
історії рішень.

---

## 1. Що таке Копілот

Це не один клас, а **5-шарова система** з двома незалежними "мізками":

1. **Класичні стратегії** — DSL-код (`utils/rules_engine/`, задокументовано
   в `REFACTOR_LOG.md`), який Копілот сам генерує, тестує, запам'ятовує і
   вдосконалює методом проб і помилок (self-learning на основі власної
   історії бектестів).
2. **Режим Нейромереж (Golden Trio)** — альтернативне джерело сигналів,
   напряму викликає `CopilotAlgorithmicLogic.analyze_window()` (не входить
   в цей документ).

Перемикається одним комбобоксом у вкладці (`combo_signal_source`,
`gui/visual/TabCopilotVisual.py:161`).

---

## 2. Шари архітектури (файлова карта)

```
gui/visual/TabCopilotVisual.py    (445 р.) — UI: чекбокси, черга задач, лог, статистика
        |
gui/GuiBinder.py::_bind_copilot() (рядок ~1376) — з'єднує кнопки з логікою
        |
gui/logic/CopilotLogic.py         (128 р.) — тримає TradingCopilot (1 екземпляр
        |                                     на весь застосунок), проксі до service
        |
gui/logic/copilot_service.py      (695 р.) — потоки (QThread): GapAnalyzer,
        |                                     AutoDownloader, Scheduler, Websocket
        |
utils/algorithms/backtesting/TradingCopilot.py (1307 р.) — "мозок":
        |     пам'ять, самонавчання, статичний аналізатор, сканер ринків
        |
        +-- utils/algorithms/backtesting/StrategyGenerator.py (278 р.) — генератор
        |         випадкових стратегій (rules.json + strategy_meta.json)
        |
        +-- utils/algorithms/backtesting/MarketRunner.py (236 р.) — прогін
        |         стратегії по свічках (walk-forward симуляція угод)
        |
        +-- utils/rules_engine/ (core.py, registry.py, strategy.py) — DSL,
                  задокументовано в REFACTOR_LOG.md "Карта залежностей"
```

**Хто створює що:**
- `LogicRegistry.__init__` (`gui/logic/LogicRegistry.py:19`) створює
  `self.copilot = CopilotLogic()` **першим** серед усіх логік — і саме тому
  `BacktestLogic` (Кластер 2 в `REFACTOR_LOG.md`) бере `self.copilot`
  звідси, а не створює свій власний `TradingCopilot`.
- `CopilotLogic.__init__` створює **єдиний** `self.trading_copilot =
  TradingCopilot(db_path=PathManager.get_db_path())` на весь застосунок
  (`gui/logic/CopilotLogic.py:19`). Всі інші місця (`copilot_service.py`,
  `BacktestLogic.py`) або перевикористовують цей об'єкт, або створюють
  СВІЙ окремий екземпляр `TradingCopilot(db_path=...)` в межах одного
  фонового потоку (`CopilotSchedulerThread.run()` — рядок 258) — обидва
  варіанти безпечні, бо `TradingCopilot` без стану сесії (все читає/пише
  напряму в DuckDB).

---

## 3. Залежності в межах системи (не rules_engine — той окремо в REFACTOR_LOG.md)

| Залежність | Хто використовує | Навіщо |
|---|---|---|
| `utils/DataBaseManager.py` | `TradingCopilot`, `MarketRunner`, `copilot_service.py` | читання OHLCV-таблиць, запис `copilot_memory`/`copilot_signals`/`rules_changelog` |
| `utils/LaboratoryBacktesterDealWriter.py` | `MarketRunner._execute_run` | перетворює сигнали входу/виходу на записи угод, рахує Profit |
| `utils/gap_analyzer.py::GapAnalyzer` | `copilot_service.GapAnalyzerThread` | фільтрує "прогалини" в даних, що насправді вихідні/свята |
| `utils/Trading/MassiveModule.py`, `utils/Trading/CCXTModule.py` | `copilot_service.AutoDownloaderThread` | довантажують пропущені свічки після аналізу прогалин |
| `utils/Trading/WebsocketStreamer.py::WebsocketStreamerThread` | `copilot_service.CopilotService.start_websocket_stream` | live-потік тіків/свічок замість опитування (polling) |
| `utils/notification_service.py::TelegramNotifier` | `TradingCopilot.scan_markets_for_signals`, `CopilotSchedulerThread` | надсилає знайдені сигнали й зведення в Telegram |
| `utils/create_insurance.py::Insurance` | `StrategyGenerator.__init__` | генерує "страхові" (дефолтні) `rules.json`/`strategy_meta.json`, якщо файли відсутні/пошкоджені |
| `utils/PathManager.py` | всі файли нижче | єдине джерело шляхів: `settings.json`, `rules.json`, `strategy_meta.json`, папка стратегій, `main.duckdb` |
| `utils/algorithms/CopilotAlgorithmicLogic.py` | `copilot_service.CopilotSchedulerThread` (лише в режимі "Нейромережі") | **єдина точка дотику** з NN-системою — викликає `analyze_window()` на останніх 10 свічках |

**Хто НЕ залежить (свідомо ізольовано):** `MarketRunner`/`StrategyGenerator`/
`TradingCopilot` нічого не знають про GUI (`gui/`) — увесь Qt-код лишається
в `gui/logic/copilot_service.py` і вище. Це дозволяє викликати їх напряму
зі скриптів (як робить `AI_Lab/benchmark_compare.py` для NN-частини).

---

## 4. Як він працює — покроково

### 4.1. Ручний режим (черга задач, ліва панель вкладки)
1. Користувач тисне "+ Задачу" → спливає меню з 4 варіантами (`show_add_task_menu`,
   `gui/GuiBinder.py:1412`): "Аналіз прогалин", "Авто-завантаження", "Генерація
   стратегій", "Очищення бази" (останнє — **лише імітація**, нічого не
   робить, рядок 1448).
2. Кожна задача додається як текстовий рядок у `QListWidget` (`tasks_list`).
3. "▶ Старт" (`start_task_queue`) бере задачі **по одній** (`run_next_task`),
   виконує, чекає сигналу `task_finished`, бере наступну. Це не паралельно —
   послідовний конвеєр.

### 4.2. Авто-рутина (`🔄 РУТИНА`, кнопка `● ACTIVE`)
Запускає `CopilotSchedulerThread` (`copilot_service.py:238`) — нескінченний
цикл, що на кожній ітерації:
1. **Аналіз прогалин у БД** (`GapAnalyzerThread`, синхронно всередині потоку).
2. **Автозавантаження** пропущених свічок (`AutoDownloaderThread`, CCXT
   і/або Massive), якщо прогалини знайдено.
3. **Генерація сигналів**: якщо `signal_mode == "Класичні Стратегії"` —
   `TradingCopilot.scan_markets_for_signals()` для кожного таймфрейму, що
   має активні стратегії; якщо `"Нейромережі (Golden Trio)"` — прямий виклик
   `CopilotAlgorithmicLogic.analyze_window()` на кожному активі з
   `target_assets`.
4. **Відправка звітів у Telegram** (частина кроку 3, через `TelegramNotifier`).
5. **Авто-генерація стратегій**: `copilot.run_random_training(generator,
   n_strategies=100)` — тільки якщо `auto_gen` увімкнено.
6. **Розумне очікування**: рахує час до закриття НАСТУПНОЇ свічки
   (враховуючи `target_timeframes` і затримку Massive API), спить до цього
   моменту (перевіряючи `is_running` щосекунди, щоб миттєво реагувати на
   "■ STOP"), і цикл повторюється.

### 4.3. Live-режим через WebSocket (замість polling)
Якщо `settings.json["downloader"]["update_mode"] == "websockets"`:
- `start_scheduler()` НЕ запускає `CopilotSchedulerThread` взагалі, а
  натомість готує live-стрім (`_pending_websocket_start = True`), спочатку
  довантажує історію (`analyze_database`), і лише ПІСЛЯ завершення
  довантаження стартує `WebsocketStreamerThread`.
- Кожна закрита свічка (`on_candle_closed`, `copilot_service.py:647`)
  зберігається в DuckDB і **одразу** емітить `trigger_signal_scan` →
  `CopilotLogic._on_trigger_signal_scan()` → миттєве сканування стратегій
  для щойно закритого таймфрейму (без очікування циклу рутини).
- Це ЗАМІНЮЄ крок "розумне очікування" з 4.2 — сканування прив'язане до
  реального закриття свічки, а не до розрахованого таймера.

### 4.4. Самонавчання (Reinforcement-подібний цикл)
Це найважливіший принцип усієї системи класичних стратегій:
```
StrategyGenerator.generate()
   → бере copilot.get_best_components() (рейтинг з copilot_memory)
   → зважено обирає сигнал/фільтри (кращі історично компоненти = вищий шанс)
   → перед генерацією викликає copilot.update_rules_from_experience()
        → аналізує успішні (win_rate>50, PF>1.2) записи пам'яті
        → усереднює порогові значення (RSI<30 → може стати RSI<27) в rules.json
        → логує кожну зміну в таблицю rules_changelog
   → генерує код стратегії
   → MarketRunner тестує на реальних даних
   → TradingCopilot.record_backtest_result() пише результат в copilot_memory
   → цикл повторюється зі свіжим рейтингом
```
Тобто `rules.json` (пороги індикаторів) і `copilot_memory` (досвід) —
**самі себе редагують** з кожним циклом авто-генерації, без втручання
людини. Це навмисний дизайн, не побічний ефект.

---

## 5. Формати роботи (режими)

| Вимір | Варіанти | Де перемикається |
|---|---|---|
| Джерело сигналів | "Класичні Стратегії" / "Нейромережі (Golden Trio)" | `combo_signal_source`, `TabCopilotVisual.py:161` → `settings.json["copilot_view"]["signal_mode"]` |
| Керування рутиною | Авто-режим (усе увімкнено) / Ручний набір чекбоксів | `cb_auto_mode` — коли True, решта чекбоксів заблоковані й вважаються True |
| Оновлення даних | Polling (цикл рутини) / Websockets (live-стрім) | `settings.json["downloader"]["update_mode"]` |
| Джерело довантаження | CCXT (крипто) / Massive (форекс+крипто) | `cb_download_ccxt` / `cb_download_massive` |
| Тип угоди в симуляції | Standard (CFD/Forex/Crypto) / Binary Options | `settings.json["trading_mode"]["type"]`, зчитує `MarketRunner.__init__` |
| Напрямок генерації стратегій | BUY / SELL / MIXED (випадково) | параметр `direction` у `run_random_training`/`AutoLearnWorker` |
| Вихід з угоди (Standard) | по сигналу `exit_rule` / по `close_on_next_candle` | `BaseSettings`, налаштування `MarketRunner` |
| Вихід з угоди (Binary Options) | ВИКЛЮЧНО по таймеру (`bo_expiration_bars` або `bo_fixed_time_minutes`) | `trading_mode.bo_fixed_time_enabled` |

---

## 6. Налаштування — ДВА окремих поверхи

Це джерело плутанини, варто пам'ятати чітко:

### 6.1. `settings.json["copilot"]` — глибокі налаштування, редагуються у вкладці **"Налаштування" → Copilot** (`gui/visual/TabSettingsVisual.py::_build_copilot_page`, рядок 268)
| Ключ | Призначення |
|---|---|
| `half_life_days` | період напіврозпаду ваги старих записів пам'яті (`_time_decay_weight`) |
| `min_score_for_best` | поріг `_calculate_score()`, вище якого стратегія йде в `get_best_components()`/зберігається як файл |
| `update_threshold_weight` | мінімальна сумарна вага успішних прикладів, щоб `update_rules_from_experience` взагалі щось змінив |
| `active_strategies` | **застарілий** плаский список (замінений на `active_strategies_tree`, лишився для сумісності) |
| `active_strategies_tree` | словник `{таймфрейм: [шляхи до .py стратегій]}` — що саме сканується в рутині |
| `target_assets` | список активів для сканування/генерації (пусто = всі) |
| `target_timeframes` | список таймфреймів |
| `top_strategies_count` | скільки найкращих `.py`-стратегій зберігати в папці `Copilot/` |
| `min_trades`, `min_profit_factor` | пороги фільтрації в `run_random_training`/`AutoLearnWorker` |
| `min_trades_mode`, `min_trades_base_candles`, `min_trades_tolerance`, `auto_learn_data_limits` | **використовуються ЛИШЕ в `AutoLearnWorker`** (Кластер 2, зараз відключено) — `TradingCopilot.run_random_training` їх не читає |
| `routine_interval_minutes` | присутнє в `settings.json`, але **не знайдено жодного місця коду, яке його читає** (див. розділ 7) |

### 6.2. `settings.json["copilot_view"]` — швидкі перемикачі, редагуються ПРЯМО у вкладці Copilot (`TabCopilotVisual.save_settings`, рядок 295)
| Ключ | Призначення |
|---|---|
| `cb_auto_mode` | Авто/Ручний режим рутини |
| `cb_auto_gen` | вмикає крок 5 (авто-генерація 100 стратегій) |
| `cb_download_ccxt` / `cb_download_massive` | джерела автозавантаження |
| `cb_gen_signals` | вмикає кроки 3-4 (сканування + Telegram) |
| `signal_mode` | "Класичні Стратегії" / "Нейромережі (Golden Trio)" |

**Важливо:** обидва JSON-розділи читаються з диска НАПРЯМУ (`open(settings_path)`)
у багатьох місцях замість єдиного сервісу конфігурації — якщо колись
переробляти Copilot, це перше місце для рефакторингу (List у розділі 7).

---

## 7. Знайдені проблеми (довідково, нічого не виправлено)

> **Оновлення 2026-07-02:** пункти 1 і 2 нижче стосувалися виключно
> rules_engine/класичних стратегій — після заморозки (розділ 8, запис
> 2026-07-02) усі три `exec()`-шляхи з пункту 2 недосяжні, а зламаний
> шаблон з пункту 1 генерується лише при першому запуску й теж посилається
> на заморожений rules_engine. Ризик не зник (код лишився), але наразі
> не активний.

1. **Зламаний шаблон стратегії за замовчуванням.** `PathManager.py:90-120`
   (`demo_strategy_code`, генерується лише при ПЕРШОМУ запуску програми) —
   викликає `Indicator("MACD", "macd", {...})` (3 аргументи),
   `Algorithm(name, conditions=[...])`, `Strategy(name=..., algorithms=[...])`
   — жоден з цих сигнатур **не існує** в поточному `rules_engine` (там
   `Indicator(name)` 1 аргумент, `Strategy(entry_rule, exit_rule=None, ...)`).
   Перший запуск на чистій машині створить файл, який впаде з `TypeError`
   при першій спробі аналізу/запуску.
2. **Три різні рівні "пісочниці" для `exec()` одного й того ж коду стратегій:**
   - `TradingCopilot._run_single_strategy` (авто-генерація, `run_random_training`) —
     AST-перевірка (`ast.walk`, блокує `import`/`exec`/`eval`/`open`) + обмежені `__builtins__`.
   - `TradingCopilot._scan_single_market` (сканування сигналів) — **лише**
     фільтрація рядків, що починаються з `import`/`from` (простий string-match,
     обходиться однорядковим `__import__(...)` без ключового слова `import`) +
     ті самі обмежені `__builtins__`.
   - `BacktestLogic.AutoLearnWorker.run` (Кластер 2, зараз недосяжний) —
     **взагалі без AST-перевірки й без обмеження `__builtins__`** (`exec(code_str, local_ns)`,
     `gui/logic/BacktestLogic.py:268`) — найслабший варіант з трьох.
3. **`routine_interval_minutes`** є в `settings.json["copilot"]`, але жоден
   Python-файл його не читає — рутина сама рахує час до закриття свічки
   (розділ 4.2, крок 6), цей ключ схоже застарів або запланований, але не
   довведений.
4. **"Очищення бази"** в черзі ручних задач (`gui/GuiBinder.py:1448`) —
   лише друкує повідомлення в лог, реальної дії не виконує.
5. Обидва JSON-розділи (`copilot`/`copilot_view`) читаються прямим
   `open()+json.load()` майже в кожному методі окремо (немає єдиного
   кешованого сервісу конфігурації) — стилістично неоднорідно і легко
   розсинхронізувати.

---

## 8. Журнал змін до Копілота

### 2026-07-02 — Заморожено все, пов'язане з класичними стратегіями (rules_engine)

Повний розбір і всі торкнуті файли — `REFACTOR_LOG.md`, Кластер 4. Коротко:

- **Заморожено повністю** (весь код обгорнутий у рядкові літерали, ніде
  не виконується): `utils/rules_engine/` (усі 4 файли), `StrategyGenerator.py`,
  `MarketRunner.py`.
- **Заморожено методи/виклики** (тіла лишились, але недосяжні — локальні
  lazy-імпорти всередині методів, тож нічого не падає): в `TradingCopilot.py`
  — `run_random_training`, `update_rules_from_experience`, увесь
  "СТАТИЧНИЙ АНАЛІЗАТОР СТРАТЕГІЙ" (`analyze`+helpers), `scan_markets_for_signals`,
  модульні `_scan_single_market`/`_run_single_strategy`/`_init_worker`;
  в `copilot_service.py::CopilotSchedulerThread` — класична гілка кроку
  3-4, крок 5 (авто-генерація); в `CopilotLogic.py` — `_on_trigger_signal_scan`
  (websocket-тригер) і його з'єднання сигналу.
- **Заморожено UI-настройки**: `TabCopilotVisual.py` (`cb_auto_gen`
  заблокований, `combo_signal_source` містить лише "Нейромережі (Golden
  Trio)"), `TabSettingsVisual.py::_build_copilot_page` (4 з 5 секцій
  заблоковані через `setEnabled(False)` — "Критерії Відбору", "Обмеження
  Авто Навчання", "Фільтри Активності", "Активні Стратегії"; "Параметри
  Сканування" НЕ чіпалась, бо спільна з NN-режимом).
- **Критичний фікс під час верифікації**: `utils/algorithms/backtesting/__init__.py`
  імпортував `MarketRunner` на рівні пакету — після заморозки `MarketRunner.py`
  це валило б `ImportError` для БУДЬ-ЯКОГО імпорту з `utils.algorithms.backtesting.*`,
  включно з живим `TradingCopilot` (тобто зламало б навіть NN-режим).
  Виправлено — імпорт закоментовано.
- **Лишилось живим і чому**: режим "Нейромережі (Golden Trio)" (не
  залежить від rules_engine), уся інфраструктура рутини (гепи/довантаження/
  websocket/Telegram), і в `TradingCopilot.py` — методи читання пам'яті
  (`get_memory_df`, `get_best_components`, `record_backtest_result`,
  `predict_success_chance`, `generate_experience_summary`) — не залежать
  від rules_engine, перші два далі живлять панель "СТАТИСТИКА ДОСВІДУ"/
  "РЕЙТИНГ КОМПОНЕНТІВ" у вкладці Копілота (даними, накопиченими до
  заморозки — нові туди більше не потраплятимуть).
- **Причина**: явний запит користувача — тимчасово заморозити всю
  rules_engine-гілку й роботу зі стратегіями (включно з настройками) перед
  переробкою GUI, той самий принцип, що й для вкладок Графік/Бектест
  (REFACTOR_LOG.md, Кластери 1-2).
- **Верифікація**: `py_compile` на 11 файлах, headless-запуск `MainAppWindow`
  (5 вкладок), пряме інстанціювання `TradingCopilot`+`CopilotSchedulerThread`,
  перевірка стану віджетів (disabled/enabled) відповідно до плану.
