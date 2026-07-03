# Довідка дій рефакторингу — AVI System

Живий документ. Оновлюється після кожної сесії рефакторингу/відключення
функціоналу. Згруповано по кластерах (фіча/вкладка), а не по хронології —
щоб можна було швидко знайти "що сталося з X".

## Легенда

- **Статус:** `ВІДКЛЮЧЕНО` (код лишився, тимчасово не виконується) /
  `ВИДАЛЕНО` (фізично прибрано з робочого дерева; відновити — з git-історії) /
  `ЗМІНЕНО` (логіка реально інша, назад не відкотити коментарем) /
  `ВИПРАВЛЕНО` (баг-фікс, не пов'язаний з відключенням)
- **Маркер у коді:** текстовий рядок, за яким шукати місце в файлі (`grep`)
- Розділ "Що лишилось живим і чому" — навмисно НЕ відключені частини, які
  на перший погляд мали б піти разом з рештою, але щось інше на них спирається

> **2026-07-03: фізичне видалення.** Кластери 1, 2 і 4 нижче спочатку були
> лише ЗАКОМЕНТОВАНІ (код лишався в файлах як довідка). Після коміту
> `0eeea95` ("Заморозити Графік/Бектест вкладки та rules_engine/класичні
> стратегії") весь цей мертвий код фізично видалено з робочого дерева —
> закоментовані блоки прибрані, повністю неживі файли видалені, недосяжні
> методи в `TradingCopilot.py` вирізані. **Якщо колись знадобиться старий
> код — він цілий у git-історії до коміту `0eeea95` включно** (`git show
> 0eeea95:шлях/до/файлу` або `git checkout 0eeea95 -- шлях/до/файлу`).
> Таблиці нижче лишені як є (описують, ЩО саме було зроблено на етапі
> заморозки) — статус файлів у стовпці "Файл" тепер означає "видалено", а
> не "існує в закоментованому вигляді".

---

## Кластер 1: Вкладка "Графік" (Chart)

**Статус:** ВІДКЛЮЧЕНО — 2026-07-01. Очікує повного перепису на новому принципі.

| Файл | Що зроблено | Маркер у коді |
|---|---|---|
| `gui/visual/VisualRegistry.py` | Закоментовано `import TabChartVisual` та `self.chart_tab = TabChartVisual()` | `ВІДКЛЮЧЕНО: вкладка "Графік"` |
| `gui/logic/LogicRegistry.py` | `self.chart = ChartLogic()` **лишено живим** (див. нижче) | `ЧАСТКОВО ВІДКЛЮЧЕНО` |
| `gui/GuiBinder.py` | Виклик `self._bind_chart()` в `bind_all()` закоментовано; `addTab(self.v.chart_tab, ...)` в `attach_to_tabs()` закоментовано; метод `_bind_chart` (клас-метод, ~366 рядків) позначено маркером над `def`, **тіло методу не чіпалось** — лишається мертвим кодом на місці | `ВІДКЛЮЧЕНО: вкладка "Графік"` (3 місця) |
| `gui/MainWindow.py` | Закоментовано: `import finplot as fplt`; підключення сигналів `btn_open_chart.clicked` і `backtest_tab.request_show_chart`; гілку `elif widget == chart_tab` в `on_tab_changed()`; методи `_load_chart_from_action`, `_show_trades_from_action`, `on_open_chart_clicked`, `on_backtest_show_chart` (усі 4 повністю) | `ВІДКЛЮЧЕНО: вкладка "Графік"` (4 місця) |
| `gui/visual/TabChartVisual.py` (335 рядків) | Весь файл (класи `TabChartVisual`, `AppearanceSettingsDialog`, `SimulationSettingsDialog`) загорнуто у `_DISABLED_TAB_CHART_VISUAL_SOURCE = r"""..."""`. Ніде не імпортується | Заголовок файлу |
| `gui/visual/CustomChart.py` (347 рядків) | Весь файл (`TimeAxisItem`, `CustomViewBox`, `CandlestickItem`, `NativeChartWidget`) загорнуто у `_DISABLED_CUSTOM_CHART_SOURCE = r"""..."""`. Імпортувався лише з `TabChartVisual.py` | Заголовок файлу |

**Що лишилось живим і чому:**
- `LogicRegistry.chart` (`ChartLogic` instance) — методи `get_available_assets()`
  і `get_backtest_tables()` використовуються вкладками Налаштування й Бектест,
  не тільки самим графіком. Клас `ChartLogic.py` не чіпався взагалі.

---

## Кластер 2: Вкладка "Тестер стратегій" (Backtest)

**Статус:** ВІДКЛЮЧЕНО — 2026-07-02. Складніший кейс за графік — тут же
живе спільна логіка з вкладкою "Автономний Копілот" (`TradingCopilot`), тому
відключення точкове.

| Файл | Що зроблено | Маркер у коді |
|---|---|---|
| `gui/visual/VisualRegistry.py` | Закоментовано `import TabBacktestVisual` та `self.backtest_tab = TabBacktestVisual()` | `!_!...!_! ВІДКЛЮЧЕНО (BACKTEST)` |
| `gui/logic/LogicRegistry.py` | `self.backtest = BacktestLogic(self.copilot)` **лишено живим** (див. нижче) | `!_!...!_! ЧАСТКОВО ВІДКЛЮЧЕНО (BACKTEST)` |
| `gui/GuiBinder.py` | Виклик `self._bind_backtest()` в `bind_all()` закоментовано; `addTab(self.v.backtest_tab, ...)` в `attach_to_tabs()` закоментовано; метод `_bind_backtest` (клас-метод, ~318 рядків) позначено маркером над `def`, тіло не чіпалось | `!_!...!_! ВІДКЛЮЧЕНО (BACKTEST)` (3 місця) |
| `gui/MainWindow.py` | Гілку `elif widget == backtest_tab` в `on_tab_changed()` закоментовано (сигнал `request_show_chart` і метод `on_backtest_show_chart` вже були закоментовані в Кластері 1, бо це той самий графік) | `!_!...!_! ВІДКЛЮЧЕНО (BACKTEST)` |
| `gui/visual/TabBacktestVisual.py` (729 рядків) | Весь файл (клас `TabBacktestVisual`) загорнуто у `_DISABLED_TAB_BACKTEST_VISUAL_SOURCE = r'''...'''` (одинарні лапки — у файлі є f-string на `"""`). Ніде не імпортується | Заголовок файлу |

**Що лишилось живим і чому:**
- `LogicRegistry.backtest` (`BacktestLogic` instance) — `__init__` безпечний
  (лише читає `strategy_meta.json`, жодних потоків/таймерів не стартує).
  Головне: `BacktestLogic.__init__` бере `self.copilot = copilot_logic.trading_copilot`
  — це той самий `TradingCopilot`, яким користується вкладка "Автономний
  Копілот" (`CopilotLogic`). Видалити інстанціювання — означає ризикувати
  цим спільним об'єктом. Клас `gui/logic/BacktestLogic.py` (включно з
  `BacktestWorker`/`AutoLearnWorker`/`WfvWorker`) не чіпався взагалі — просто
  став недосяжним, бо ніхто його воркери більше не створює.
- `gui/logic/ChartLogic.py::get_backtest_tables()` — залишається (той самий
  збережений сервіс з Кластера 1), лише фільтрує таблиці з префіксом
  `backtest_`, з самою вкладкою напряму не пов'язаний.

---

## Кластер 3: Безпека (баг-фікси, не відключення)

**Статус:** ВИПРАВЛЕНО — 2026-07-01.

| Файл | Що зроблено |
|---|---|
| `gui/logic/DuckDbService.py` | `get_table_data()` і `get_table_count()` тепер викликають `self.db_manager._validate_table_name(table_name)` перед побудовою SQL-запиту — той самий guard-патерн, що вже є в `DataBaseManager`. Раніше назва таблиці підставлялась у f-string без перевірки (потенційна SQL-ін'єкція через назву таблиці). `execute_query()` навмисно не чіпався — приймає довільний SQL за призначенням. |

---

## Кластер 4: Класичні стратегії (rules_engine) — заморожено

**Статус:** ВІДКЛЮЧЕНО — 2026-07-02. На відміну від Кластерів 1-2 (цілі
вкладки), тут заморожено ЧАСТИНУ функціоналу двох живих вкладок
("Автономний Копілот" і "Налаштування") — режим "Нейромережі (Golden
Trio)" і вся спільна інфраструктура (аналіз прогалин, довантаження,
websockets, Telegram) лишаються повністю робочими. Повний розбір — у
`COPILOT_ARCHITECTURE.md`.

| Файл | Що зроблено | Маркер у коді |
|---|---|---|
| `utils/rules_engine/core.py`, `registry.py`, `strategy.py` | Весь код кожного файлу загорнуто у `_DISABLED_..._SOURCE = r'''...'''`. Жоден клас (`Indicator`/`Pattern`/`Algorithm`/`Strategy`/`IndicatorRegistry`/...) більше не визначений | `ВІДКЛЮЧЕНО (RULES_ENGINE)` у заголовку кожного файлу |
| `utils/rules_engine/__init__.py` | Імпорти з `.core`/`.registry`/`.strategy` закоментовані (інакше сам пакет впав би при першому імпорті) | `ВІДКЛЮЧЕНО (RULES_ENGINE)` |
| `utils/algorithms/backtesting/StrategyGenerator.py`, `MarketRunner.py` | Весь код обох файлів загорнуто у рядкові літерали — обидва на 100% залежали від rules_engine | Заголовок кожного файлу |
| `utils/algorithms/backtesting/__init__.py` | **Критичний фікс, знайдений під час верифікації:** `from .MarketRunner import MarketRunner` на рівні пакету закоментовано. Без цього кроку сам імпорт `TradingCopilot` (живий, потрібен режиму "Нейромережі") валив би `ImportError` при старті застосунку — `MarketRunner.py` більше не визначає клас | `ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ)` |
| `utils/algorithms/backtesting/TradingCopilot.py` | Тіла НЕ чіпались (локальні lazy-імпорти всередині методів — безпечно лишити недосяжними). Маркерами позначено: модульний блок `_init_worker`/`_scan_single_market`/`_run_single_strategy` (загорнуто в рядковий літерал), методи `run_random_training`, `update_rules_from_experience`, уся секція "СТАТИЧНИЙ АНАЛІЗАТОР СТРАТЕГІЙ" (`analyze`+10 helper-методів), `scan_markets_for_signals`. **Лишились живими:** `get_memory_df`, `get_best_components`, `record_backtest_result`, `predict_success_chance`, `generate_experience_summary`, математичні helper-и (`_calculate_score`, `_time_decay_weight`, `_jaccard`) — не залежать від rules_engine, і перші два активно живлять панель статистики в UI Копілота | `!_!...!_! ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ)` (5 місць) |
| `gui/logic/copilot_service.py` | `CopilotSchedulerThread.run()`: закоментовано імпорт+створення `StrategyGenerator`; гілку `"Класичні Стратегії"` кроку 3-4 замінено на лог-повідомлення "заморожено" (гілка `else` — режим Нейромереж — не чіпалась); крок 5 (`run_random_training`) замінено на лог-повідомлення | `!_!...!_! ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ)` (3 місця) |
| `gui/logic/CopilotLogic.py` | `_on_trigger_signal_scan` (websocket-тригер класичного сканування): тіло замінено на лог-повідомлення, оригінал закоментовано нижче; з'єднання сигналу `trigger_signal_scan` закоментовано в `__init__` | `!_!...!_! ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ)` (2 місця) |
| `gui/visual/TabCopilotVisual.py` | `cb_auto_gen` — примусово `setChecked(False)`+`setEnabled(False)`, прибрано з циклу перемикання auto/manual режиму (`_update_routine_ui`), лейбл дописано "(заморожено)". `combo_signal_source` — пункт "Класичні Стратегії" прибрано зі списку, лишився тільки NN-режим. Текст кроку 5 в списку рутини теж позначено "(заморожено)" | `!_!...!_! ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ)` (3 місця) |
| `gui/visual/TabSettingsVisual.py::_build_copilot_page` | `setEnabled(False)` на всі віджети 3 секцій: "Критерії Відбору в Топ та Пам'ять", "Обмеження даних для Авто Навчання", "Фільтри Активності", "Активні Стратегії" (`active_strategies_tree`+2 кнопки) — заголовки секцій дописано "(ЗАМОРОЖЕНО)". Секція "Параметри Сканування" (`target_assets_input`/`target_timeframes_input`) **НЕ чіпалась** — спільна з режимом Нейромереж. `GuiBinder._bind_settings` (save/load логіка) теж не чіпався — значення й далі читаються/пишуться в `settings.json`, просто керувати ними з UI не можна | `!_!...!_! ВІДКЛЮЧЕНО (RULES_ENGINE / СТРАТЕГІЇ)` |

**Що лишилось живим і чому:**
- Режим "Нейромережі (Golden Trio)" в `copilot_service.py::CopilotSchedulerThread` — прямий виклик `CopilotAlgorithmicLogic.analyze_window()`, rules_engine не зачіпає.
- Уся інфраструктура рутини: аналіз прогалин (`GapAnalyzerThread`), автозавантаження (`AutoDownloaderThread`), WebSocket-стрім (`WebsocketStreamerThread`), Telegram (`TelegramNotifier`) — не залежать від rules_engine.
- `TabSettingsVisual`'s "Параметри Сканування" (`target_assets`/`target_timeframes`) — читається і режимом Нейромереж, і (раніше) класичними стратегіями; заморожувати не було підстав.
- `gui/logic/BacktestLogic.py`, `gui/logic/ChartLogic.py::_preload_simulation_strategy` — вже недосяжні через Кластери 1-2, їхні локальні імпорти rules_engine/MarketRunner/StrategyGenerator нічого не ламають (ніколи не виконуються).

**Верифікація:** `py_compile` на всіх 11 торкнутих файлах, headless-запуск
`MainAppWindow` (5 вкладок, усі перемикання без падінь), прямий імпорт і
інстанціювання `TradingCopilot`+`CopilotSchedulerThread` (підтвердив, що
критичний фікс `backtesting/__init__.py` усунув би інакше неминучий
`ImportError` при старті рутини), перевірка стану віджетів (`cb_auto_gen`
вимкнений, `combo_signal_source` містить лише NN-пункт, `active_strategies_tree`
заблокований, `target_assets_input` — навпаки, активний).

---

## Карта залежностей: `utils/rules_engine/` (довідково, не кластер відключення)

> **ІСТОРИЧНА ДОВІДКА:** розділ описує стан ДО заморозки в Кластері 4
> вище (2026-07-02) — корисно, щоб розуміти, ЩО саме відключено і чому
> шлях "1. Активно" нижче більше не активний. Для поточного (замороженого)
> стану дивись Кластер 4 і `COPILOT_ARCHITECTURE.md`.

**Що це:** DSL (Domain Specific Language) для опису торгових стратегій як
Python-виразів (`Indicator("RSI_14") < 30` замість ручного `if df[...]`).
Три файли:
- `core.py` — дерево виразів: `Indicator`/`Pattern`/`Algorithm`/`Constant`
  (листя) + `BinaryOperation`/`CrossOver`/`CrossUnder` (вузли, від
  перевантажених `>`, `<`, `&`, `|`, `+` тощо). `.evaluate()` → True/False,
  `.evaluate_proximity()` → fuzzy "% готовності" сигналу 0.0-1.0.
- `registry.py` (`IndicatorRegistry`) — міст до реального DataFrame. Ледаче
  обчислення: індикатора нема — сам викликає `IndicatorProcessor`/
  `PatternDetector`/`AlgorithmProcessor`/`BacktestAlgorithmProcessor`.
- `strategy.py` (`Strategy`) — керує входом/виходом: `entry_rule`,
  `exit_rule`, `exit_after_candles`, `delay_entry_candles`.

Сам rules_engine нічого не рахує — лише оркеструє виклики до
`IndicatorProcessor`/`PatternDetector`/`AlgorithmProcessor`.

**Хто користується — по кластерах:**

1. **Активно (жива вкладка "Автономний Копілот"):**
   `gui/logic/CopilotLogic.py` створює `self.trading_copilot = TradingCopilot(...)`
   один раз на застосунок → `ScanWorker` → `TradingCopilot.scan_markets_for_signals()`
   → паралельно (`multiprocessing.Pool`) виконує збережені `.py`-стратегії
   через `exec()` у пісочниці (`safe_globals` з білим списком builtins) →
   всередині exec живуть `Indicator`/`Pattern`/`Algorithm`/`Strategy`. **Єдиний
   шлях, де rules_engine зараз реально щось робить.**

2. **Наразі недосяжно (побічний ефект Кластерів 1 і 2 вище):**
   - `gui/logic/BacktestLogic.py` — `BacktestWorker`/`AutoLearnWorker`/`WfvWorker`
     виконують код з редактора стратегій через rules_engine. Недосяжні, бо
     `_bind_backtest()` більше не викликається.
   - `utils/algorithms/backtesting/MarketRunner.py` — walk-forward симулятор
     (`Strategy` + `IndicatorRegistry`, прокрутка по свічках). Викликається
     лише з воркерів вище.
   - `utils/algorithms/backtesting/StrategyGenerator.py` — генерує ВИПАДКОВИЙ
     код стратегій текстом (з `rules.json`) для "Авто навчання ШІ". Викликається
     лише з `AutoLearnWorker`.
   - `gui/logic/ChartLogic.py` (`_preload_simulation_strategy`, ~рядок 373) —
     прогін стратегії прямо на графіку. Прив'язано до вже відключеної вкладки
     "Графік" (Кластер 1).

3. **Орфанний код — ніде не підключений:**
   `utils/Trading/trading_service.py::TradingService` — окремий клас "живої
   торгівлі" (`paper`/`live`, цикл `_run_loop` кожні 15с), теж використовує
   `IndicatorRegistry`+`Strategy`. Перевірено `grep`-ом по всьому проєкту —
   **ніде не інстанціюється**: не в `LogicRegistry`, не в жодній вкладці.
   Забутий rule-based шлях до живої торгівлі, паралельний до вкладки
   "Авто-Трейдінг (NN)" (яка натомість використовує NN-based
   `CopilotAlgorithmicLogic`, rules_engine не чіпає взагалі).

4. **Допоміжне:**
   `utils/PathManager.py` — дає текстовий шаблон-заготовку стратегії
   (`demo_strategy_code`) для нового файлу/редактора коду.

---

## Перевірка після кожного кластера

Обидва відключення (графік, бектест) верифіковані однаково:
1. `py_compile` на всіх торкнутих файлах
2. Headless-запуск (`QT_QPA_PLATFORM=offscreen`) — `MainAppWindow()` створюється без падінь
3. Програмне перемикання по всіх вкладках `QTabWidget` — без винятків
4. Клік/emit по "осиротілих" сигналах (кнопка "Відкрити графік", `request_show_chart`) — підтверджено, що тепер безпечно нічого не робить, а не падає

Після Кластера 2 залишилось 5 вкладок: Провідник БД, Завантаження даних,
Автономний Копілот, Авто-Трейдінг (NN), Налаштування.

---

## Фізичне видалення замороженого коду — 2026-07-03

Коміт `0eeea95` зафіксував стан "закоментовано", після чого весь мертвий
код фізично видалено з робочого дерева:

**Видалено файли повністю:**
`gui/visual/TabChartVisual.py`, `gui/visual/CustomChart.py`,
`gui/visual/TabBacktestVisual.py`, `utils/rules_engine/` (весь пакет:
`core.py`, `registry.py`, `strategy.py`, `__init__.py`, `README.md`),
`utils/algorithms/backtesting/StrategyGenerator.py`,
`utils/algorithms/backtesting/MarketRunner.py`.

**Вирізано закоментовані блоки й недосяжні методи (файли лишаються):**
`gui/visual/VisualRegistry.py`, `gui/logic/LogicRegistry.py` (стислі
пояснювальні коментарі замість маркерних блоків), `gui/GuiBinder.py`
(видалено самі методи `_bind_chart`/`_bind_backtest` — 702 рядки одним
блоком, бо вони посилались на класи, яких більше не існує),
`gui/MainWindow.py` (видалено 4 мертвих методи й усі закоментовані гілки),
`gui/logic/copilot_service.py`, `gui/logic/CopilotLogic.py` (видалено
метод `_on_trigger_signal_scan` повністю — сигнал, що його викликав, і так
відключений), `utils/algorithms/backtesting/__init__.py`.

**`utils/algorithms/backtesting/TradingCopilot.py`** — найбільша зміна:
з ~1300 рядків до ~300. Видалено модульні `_scan_single_market`/
`_run_single_strategy`/`_init_worker`, методи `run_random_training`,
`update_rules_from_experience`, увесь "СТАТИЧНИЙ АНАЛІЗАТОР СТРАТЕГІЙ"
(`analyze`+10 helper-методів), `scan_markets_for_signals`. Заразом
прибрано мертві імпорти (`ast`, `re`, `random`, `Pool`) і виправлено
застарілий docstring класу (більше не згадує AST-аналіз коду стратегій).
Лишилось лише 10 методів пам'яті/досвіду (`get_memory_df`,
`get_best_components`, `record_backtest_result`, `predict_success_chance`,
`generate_experience_summary`, `_calculate_score`, `_time_decay_weight`,
`_jaccard`, `_log_rule_change`, `__init__`).

**Свідомо НЕ чіпалось** (не входило в кластери відключення, ризиковано
видаляти без окремого рішення):
- `gui/logic/BacktestLogic.py` — воркери (`BacktestWorker`/`AutoLearnWorker`/
  `WfvWorker`) досі імпортують видалені `rules_engine`/`MarketRunner`/
  `StrategyGenerator` (лениво, всередині методів) — безпечно, бо вкладка
  Бектест відключена й ці методи ніколи не викликаються, але якщо колись
  повертати вкладку — ці класи доведеться або відновити, або переписати
  воркери заново.
- `gui/logic/ChartLogic.py::_preload_simulation_strategy` — та сама
  ситуація (лінивий імпорт `MarketRunner`, ніколи не викликається).
- `utils/Trading/trading_service.py::TradingService` — орфанний клас
  (ніде не інстанціюється), теж лінивий імпорт `rules_engine`, не чіпався.
- `utils/PathManager.py::demo_strategy_code` — шаблон і так був зламаний
  (Проблема №1 в `COPILOT_ARCHITECTURE.md`) ще до видалення rules_engine,
  просто лишається зламаним тим самим способом.

**Верифікація:** `py_compile` на всіх торкнутих файлах, headless-запуск
`main.py` цілком (не лише `MainAppWindow`) через `QT_QPA_PLATFORM=offscreen`
на 60 секунд — доходить до `window.show()` і живого Qt event loop без
жодної помилки в логах, лише нешкідливе Qt-попередження про offscreen-плагін.
