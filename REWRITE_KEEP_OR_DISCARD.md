# Аналіз: що лишати при переписуванні з нуля навколо CopilotAlgorithmicLogic

Живий документ для однієї конкретної ухвали: ти плануєш писати логіку
заново, лишаючи (1) `CopilotAlgorithmicLogic` і все, що йому реально
потрібно для роботи, та (2) усі файли, написані особисто тобою. Нижче —
повна карта проєкту (58 `.py` файлів) під ці два критерії.

**Нічого не видалено.** Це довідка для перегляду — став позначки/питання,
і тоді підемо видаляти те, що підтвердиш.

## Легенда
- ✅ **KEEP (твій файл)** — один із 14, що ти назвав своїми
- ✅ **KEEP (потрібен NN-пайплайну)** — `CopilotAlgorithmicLogic` не запрацює без цього
- ⚙️ **KEEP (інфраструктура застосунку)** — не пов'язано напряму з NN, але потрібне для роботи GUI/даних узагалі
- ❌ **DELETE-кандидат** — не твій файл і не потрібен NN-пайплайну
- ❓ **ПОТРІБНЕ РІШЕННЯ** — залежить від того, чи лишаєш певний функціонал

---

## 1. Ядро — `CopilotAlgorithmicLogic` і все, без чого воно не працює

| Файл | Статус | Навіщо |
|---|---|---|
| `utils/algorithms/CopilotAlgorithmicLogic.py` | (поза скоупом, лишається як є) | Сама логіка |
| `models/ArchitectureRS.py`, `ArchitectureFB.py`, `ArchitectureMR.py` | ✅ KEEP (NN) | Архітектури 3 мереж, завантажуються напряму в `_init_neural_network` |
| `models/rs_weights.pth`, `fb_weights.pth`, `mr_weights.pth` | ✅ KEEP (NN) | Ваги мереж |
| `utils/algorithms/indicators/IndicatorProcessor.py` | ✅ KEEP (твій файл + NN) | Рахує `MACD_*`, `RSI_*`, `Bollinger_*`, `Keltner_*`, `ATR_*`, `Market_State_Linear_*`, `Market_Slope_*`, `SMA/EMA_Cross_*`, `Stochastic_*`, `CCI_*`, `WilliamsR_*`, `Volume_Avg_*` — усе, що читає `_gather_signals` |
| `utils/algorithms/indicators/PatternDetector.py` | ✅ KEEP (твій файл + NN) | Рахує `Engulfing`, `Hammer`, `Morning_Star` і решту 10 патернів |
| `utils/algorithms/indicators/BacktestAlgorithmProcessor.py` | ✅ KEEP (твій файл + NN) | Рахує `FVG_Up/Down`, `Bullish/Bearish_OB`, `Near_Support/Resistance`, `Sweep_High/Low` |
| `utils/algorithms/indicators/AlgorithmProcessor.py` | ✅ KEEP (твій файл + NN) | Батьківський клас `BacktestAlgorithmProcessor`, той самий набір методів для НЕ-бектест режиму |
| `utils/algorithms/WCEAnomalyDetector.py` | ✅ KEEP (потрібен) | `AlgorithmProcessor.py` імпортує його напряму — навіть якщо не в твоєму списку, це залежність твого файлу. **Уточни: це теж твій файл?** |
| `utils/DataBaseManager.py` | ✅ KEEP (твій файл) | Читає/пише свічки в DuckDB |
| `utils/PathManager.py` | ⚙️ KEEP (інфраструктура) | Шляхи до БД/моделей/налаштувань — використовується всюди |
| `gui/logic/LiveAlgorithmicLogic.py` | ✅ KEEP (NN) | Єдина логіка, що напряму викликає `CopilotAlgorithmicLogic.analyze_window()` у вкладці "Авто-Трейдінг (NN)" |
| `gui/visual/TabLiveAlgorithmicVisual.py` | ✅ KEEP (NN) | UI цієї вкладки — самодостатній, без екзотичних залежностей |

### ⚠️ Знайдений розрив у поточному живому пайплайні

`LiveAlgorithmicLogic.py:38` і `CopilotService.py:368` обидва будують
`BacktestAlgorithmProcessor` з жорстко прописаним:
```python
algorithm_params=['Order_Blocks', 'Fair_Value_Gaps', 'Market_Structure']
```
Але `CopilotAlgorithmicLogic._gather_signals` тепер (після твоїх правок)
читає ще й `Near_Support`/`Near_Resistance` (від параметра `'Levels'`) і
`Sweep_High`/`Sweep_Low` (від параметра `'Liquidity_Sweep'`) — **жоден з
цих двох параметрів не запитується**, тобто в живій GUI-вкладці "Авто-
Трейдінг (NN)" сигнали `Levels`/`Liquidity_Sweep` зараз НІКОЛИ не
спрацьовують, попри те що в коді все підключено правильно. Якщо твій
тестовий скрипт (де вийшов PF 1.38) явно запитує ці параметри — живий
застосунок і твій бектест зараз дають РІЗНИЙ результат. Це не "видалити",
а "не забути додати `'Levels', 'Liquidity_Sweep'` в цей список" при
переписуванні.

### Не використовується в поточній `_gather_signals` (вага є, сигнал ніколи не рахується)
`'WCE'`, `'NGram'`, `'Anomaly'` є в `base_weights`/`_adapt_weights`, але
жодна колонка під ці ключі не перевіряється в `_gather_signals` —
`WrapCandleEngine.py`/`NGramAnalyzer.py`/`NGramPredictor.py`/
`WCEAnomalyDetector.py` (окрім WCE-частини всередині `AlgorithmProcessor`)
зараз функціонально не впливають на сигнал, хоча лишаються твоїми файлами
й будуть збережені за критерієм авторства.

---

## 2. Решта твоїх 14 файлів (не перелічені вище)

| Файл | Статус | Навіщо / чи використовується зараз |
|---|---|---|
| `utils/algorithms/WrapCandleEngine.py` | ✅ KEEP (твій) | Джерело `WCE`-фічі — зараз не підключено до сигналу (див. вище) |
| `utils/algorithms/NGramAnalyzer.py` | ✅ KEEP (твій) | Джерело `NGram`-фічі — так само не підключено зараз |
| `utils/algorithms/NGramPredictor.py` | ✅ KEEP (твій) | Пов'язаний з NGramAnalyzer |
| `utils/IndicatorDecorator.py` | ✅ KEEP (твій) | Використання не перевіряв у цій сесії — лишається за критерієм авторства |
| `utils/LaboratoryBacktesterDealWriter.py` | ✅ KEEP (твій), але ❓ **зараз ніде не використовується** | Єдиний споживач був `MarketRunner.py` (видалений разом з rules_engine). Зараз orphan-файл |
| `utils/other_utils.py` | ✅ KEEP (твій) | Загальні хелпери |
| `gui/logic/DuckDbService.py` | ✅ KEEP (твій, і вже виправлений на SQL-injection) | Використовується вкладкою "Провідник БД" |
| `utils/Trading/CCXTModule.py` | ✅ KEEP (твій) | Довантаження крипто-даних |
| `utils/Trading/MassiveModule.py` | ✅ KEEP (твій) | Довантаження форекс-даних |

---

## 3. Інфраструктура застосунку (не твоя й не NN, але потрібна для роботи GUI взагалі)

| Файл | Статус | Навіщо |
|---|---|---|
| `main.py`, `gui/MainWindow.py`, `gui/GuiBinder.py`, `gui/visual/VisualRegistry.py`, `gui/logic/LogicRegistry.py`, `gui/status_bar.py` | ⚙️ KEEP (або переписати заново) | Каркас застосунку — збірка вкладок, вікно, статус-бар. Якщо пишеш логіку з нуля, це теж кандидат на переписування, але функція (запуск, реєстри) знадобиться в будь-якому вигляді |
| `gui/logic/ExplorerLogic.py`, `gui/visual/TabExplorerVisual.py` | ⚙️ KEEP | Вкладка "Провідник БД" — перегляд таблиць, не пов'язана з NN напряму, але корисний інструмент |
| `gui/logic/DownloaderLogic.py`, `gui/visual/TabDownloaderVisual.py` | ⚙️ KEEP | Вкладка "Завантаження даних" — без неї дані в БД не з'являться взагалі |
| `gui/logic/SettingsLogic.py`, `gui/visual/TabSettingsVisual.py` | ⚙️ KEEP, але ❓ **дуже роздута** | Зараз тримає й налаштування класичних стратегій (заблоковані, неактивні) — при переписуванні можна суттєво скоротити, лишивши тільки risk/trading_mode + може target_assets |
| `gui/visual/UiElements.py` | ⚙️ KEEP | Спільні кастомні QWidget (`CheckableComboBox` тощо), використовуються кількома вкладками |
| `utils/SymbolManager.py` | ⚙️ KEEP | Визначення типу ринку/форматування символів — потрібен CCXT/Massive модулям |
| `utils/gap_analyzer.py` | ⚙️ KEEP | Аналіз прогалин у даних — незалежний від Copilot-стратегій утиліта |
| `utils/config.py` | ⚙️ KEEP | API-ключі |
| `utils/notification_service.py` | ⚙️ KEEP, якщо лишаєш Telegram-сповіщення | Наразі викликається лише з NN-гілки `CopilotService` |
| `utils/Trading/WebsocketStreamer.py`, `utils/Trading/TickAggregator.py` | ❓ **ПОТРІБНЕ РІШЕННЯ** | Живий-стрім даних — використовується лише в `CopilotService.start_websocket_stream`. Якщо викидаєш весь `CopilotService`, ці два теж стають orphan, якщо тільки не захочеш live-стрім десь ще |

---

## 4. Чіткі кандидати на видалення (не твої, не потрібні NN-пайплайну)

| Файл | Чому видаляти |
|---|---|
| `gui/logic/CopilotLogic.py` | Робота лише як обгортка над `CopilotService`+`TradingCopilot`. Функціонал (рутина/сканування) дублює `LiveAlgorithmicLogic`, тільки автоматизовано |
| `gui/logic/CopilotService.py` | Класичні стратегії вже видалені, лишився тільки NN-режим рутини — той самий виклик, що й у `LiveAlgorithmicLogic`, просто в циклі |
| `utils/algorithms/backtesting/TradingCopilot.py` | Пам'ять/досвід стосується ЛИШЕ класичних стратегій (яких більше нема) |
| `gui/visual/TabCopilotVisual.py` | UI для вкладки "Автономний Копілот" — весь функціонал або дублюється, або мертвий (класичні стратегії) |
| `gui/logic/BacktestLogic.py`, `gui/logic/ChartLogic.py` | Уже недосяжні (вкладки Бектест/Графік відключені в попередніх раундах) |
| `utils/algorithms/backtesting/BaseSettings.py`, `SignalProvider.py`\*, `backtest_service.py`, `__init__.py` | Залишки бектест-движка. **\*Виняток:** `SignalProvider.Analyzer` імпортується твоїм `NGramAnalyzer.py` — якщо лишаєш `NGramAnalyzer`, `SignalProvider.py` доведеться лишити теж |
| `utils/Trading/trading_service.py` | Підтверджений сирота — ніде не інстанціюється взагалі (з першого аудиту цієї сесії) |
| `utils/create_insurance.py` | Створює дефолтні `rules.json`/`strategy_meta.json` для видаленого rules_engine/StrategyGenerator. Використовується лише з `PathManager._initialize_user_data` (перший запуск) |
| `utils/algorithms/indicators/DataProcessingManager.py` | Ре-експорт-агрегатор, використовувався лише видаленим `rules_engine/registry.py`. Зараз ніхто не імпортує |
| `gui/components/open_graphics_view.py` | Ніхто не імпортує (ймовірно залишок старої реалізації графіка) |

---

## 5. Підсумок — головне рішення, яке варто ухвалити

Найбільший блок на видалення — це **вся вкладка "Автономний Копілот"**
(`CopilotLogic`/`CopilotService`/`TradingCopilot`/`TabCopilotVisual`, 4
файли). Її єдина жива функція зараз — автоматична рутина (аналіз
прогалин → довантаження → сканування NN → Telegram → сон до свічки) —
той самий виклик `CopilotAlgorithmicLogic.analyze_window()`, що й у
"Авто-Трейдінг (NN)", тільки в нескінченному циклі замість кнопки
"Аналізувати". Питання на твій розсуд: **лишаєш автоматичний
режим (рутину) в якомусь вигляді, чи вкладка "Авто-Трейдінг (NN)" з
ручним аналізом за кнопкою — достатньо?** Від цього залежить доля ще
~5 файлів (`WebsocketStreamer`, `TickAggregator`, частково
`notification_service`, `gap_analyzer`).

Дай знати, що лишаємо/викидаємо — і берусь видаляти підтверджене.
