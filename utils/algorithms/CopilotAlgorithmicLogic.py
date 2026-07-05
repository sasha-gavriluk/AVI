import pandas as pd
import numpy as np
import torch
import os
import sys
from collections import deque

# Підключаємо архітектуру Нейромережі з папки models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../models')))
try:
    from ArchitectureRS import ArchitectureNN as ArchitectureRS
except ImportError:
    ArchitectureRS = None

try:
    from ArchitectureFB import ArchitectureNN as ArchitectureFB
except ImportError:
    ArchitectureFB = None

try:
    from ArchitectureMR import ArchitectureNN as ArchitectureMR
except ImportError:
    ArchitectureMR = None


def _compute_atr(df: pd.DataFrame, period=14) -> np.ndarray:
    """ATR(period), та сама формула, що й IndicatorProcessor.add_atr / AI_Lab TestNN.py.
    Має точно збігатись з нормалізацією, використаною під час тренування RS/MR/FB."""
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    return pd.Series(tr).rolling(window=period).mean().values


class CopilotAlgorithmicLogic:
    """
    Алгоритмічна логіка генерації сигналів для Копілота.
    Режимно-залежна ієрархія: спочатку MR-мережа визначає режим ринку
    (TREND/FLAT/VOLATILE), і залежно від нього вмикаються різні ваги
    індикаторів/патернів та різне трактування контр-трендових сигналів
    (штраф 0-35%, що масштабується близькістю до значущого рівня, а не
    жорстке вето). Деталі — див. AI_Lab/../plans (Раунд 3, Фаза А).
    """

    def __init__(self, use_context_rules: bool = False):
        self.use_context_rules = use_context_rules
        self._init_neural_network()
        # Ковзна історія nn_resistance/nn_support на актив (для проксі
        # "значущості рівня" у штрафі контр-тренду) — ключ: назва активу,
        # бо в GUI один екземпляр цього класу обходить по черзі кілька активів.
        self._level_history = {}
        # Базові ваги для кожної групи індикаторів (від 0.0 до 1.0)
        self.base_weights = {
            # Трендові індикатори
            'MACD': 0.6,
            'SMA_Cross': 0.5,
            'EMA_Cross': 0.6,
            'ADX': 0.4,

            # Осцилятори
            'RSI': 0.5,
            'Stochastic': 0.5,
            'WilliamsR': 0.4,
            'CCI': 0.4,

            # Смуги та канали
            'Bollinger': 0.5,
            'Keltner': 0.5,

            # Бичачі Патерни
            'Engulfing_Bullish': 0.7,
            'Morning_Star': 0.6,
            'Hammer': 0.5,
            'Inverted_Hammer': 0.4,
            'Piercing_Pattern': 0.5,
            'Three_White_Soldiers': 0.7,

            # Ведмежі Патерни
            'Engulfing_Bearish': 0.7,
            'Evening_Star': 0.6,
            'Shooting_Star': 0.5,
            'Dark_Cloud_Cover': 0.5,
            'Three_Black_Crows': 0.7,
            'Hanging_Man': 0.4,

            # SMC (Smart Money Concepts)
            'Bullish_FVG': 0.8,
            'Bearish_FVG': 0.8,
            'Bullish_OB': 0.8,
            'Bearish_OB': 0.8,

            # Алгоритми
            'WCE': 0.6,
            'NGram': 0.6,
            'Anomaly': 0.7,
            
            # Рівні
            'Levels': 0.5,
            'Liquidity_Sweep': 0.5,

            # ШІ Фічі
            'NN_Support_Level': 1.0,
            'NN_Resistance_Level': 1.0,
            'NN_FB_Bullish': 1.2,
            'NN_FB_Bearish': 1.2
        }

    def _init_neural_network(self):
        """Ініціалізація та завантаження PyTorch моделей."""
        self.nn_rs_model = None
        self.nn_fb_model = None
        self.nn_mr_model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Модель RS
        if ArchitectureRS is not None:
            model_path_rs = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../models/rs_weights.pth'))
            if os.path.exists(model_path_rs):
                try:
                    self.nn_rs_model = ArchitectureRS(seq_len=1000).to(self.device)
                    self.nn_rs_model.load_state_dict(torch.load(model_path_rs, map_location=self.device, weights_only=True))
                    self.nn_rs_model.eval()
                except Exception as e:
                    print(f"Помилка завантаження RS NN: {e}")

        # Модель FB
        if ArchitectureFB is not None:
            model_path_fb = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../models/fb_weights.pth'))
            if os.path.exists(model_path_fb):
                try:
                    self.nn_fb_model = ArchitectureFB(seq_len=1000).to(self.device)
                    self.nn_fb_model.load_state_dict(torch.load(model_path_fb, map_location=self.device, weights_only=True))
                    self.nn_fb_model.eval()
                except Exception as e:
                    print(f"Помилка завантаження FB NN: {e}")

        # Модель MR
        if ArchitectureMR is not None:
            model_path_mr = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../models/mr_weights.pth'))
            if os.path.exists(model_path_mr):
                try:
                    self.nn_mr_model = ArchitectureMR(seq_len=1000).to(self.device)
                    self.nn_mr_model.load_state_dict(torch.load(model_path_mr, map_location=self.device, weights_only=True))
                    self.nn_mr_model.eval()
                except Exception as e:
                    print(f"Помилка завантаження MR NN: {e}")

    def _predict_nn_scores(self, df_window: pd.DataFrame) -> tuple:
        """
        Повертає tuple (Resistance, Support, FB_Bullish, FB_Bearish, MR_Trend,
        MR_Flat, MR_Explosion, H_Resistance, H_Support, T_Resistance, T_Support).
        Resistance/Support — max(горизонтальний, трендовий) для сумісності з
        усією логікою Фази А, яка очікує один скаляр на напрямок; окремі H_/T_
        значення повертаються теж, для діагностики/подальших фаз.
        """
        if len(df_window) < 1000:
            return (0.0,) * 11

        # Беремо останні 1000 свічок (FB/MR — одне вікно, як і раніше)
        recent_df = df_window.iloc[-1000:]
        prices = recent_df[['open', 'high', 'low', 'close']].values

        # Перевірка наявності колонки volume
        vol_col = 'volume' if 'volume' in recent_df.columns else 'tick_volume'
        if vol_col in recent_df.columns:
            volumes = recent_df[[vol_col]].values
        else:
            volumes = np.zeros((len(recent_df), 1))

        base_price = prices[-1, 3]
        atr_val = _compute_atr(recent_df, period=14)[-1]
        # ФІКС: тут було (0.0, 0.0, 0.0, 0.0) — 4 елементи замість 7.
        # Через це при base_price == 0 (гепи/збій даних) розпакування
        # `nn_resistance, nn_support, ... = self._predict_nn_scores(...)`
        # кидало ValueError і валило весь analyze_window.
        if base_price == 0 or not np.isfinite(atr_val) or atr_val <= 0:
            return (0.0,) * 11

        # ATR-відносна нормалізація: рух у "одиницях ATR" замість %, та сама
        # формула, що й при тренуванні в AI_Lab — щоб НН могла знаходити спільні
        # патерни між активами з різною волатильністю замість плутатись між ними.
        norm_prices = (prices - base_price) / atr_val
        max_vol = np.max(volumes)
        norm_vols = volumes / max_vol if max_vol > 0 else np.zeros_like(volumes)

        window_X = np.concatenate([norm_prices, norm_vols], axis=1)
        tensor_X = torch.tensor(window_X, dtype=torch.float32).unsqueeze(0).to(self.device)

        out_fb = [0.0, 0.0]
        out_mr = [0.0, 0.0, 0.0]
        h_res = h_sup = t_res = t_sup = 0.0

        with torch.no_grad():
            if self.nn_rs_model is not None:
                # RS (Фаза Б): мультивіконна мережа — 5 вікон (1000/500/200/100/50),
                # той самий base_price/atr_val для всіх, щоб точно збігатись з тренуванням.
                rs_windows = []
                for w in ArchitectureRS.WINDOW_SIZES:
                    w_prices = prices[-w:]
                    w_volumes = volumes[-w:]
                    w_norm_prices = (w_prices - base_price) / atr_val
                    w_max_vol = np.max(w_volumes)
                    w_norm_vols = w_volumes / w_max_vol if w_max_vol > 0 else np.zeros_like(w_volumes)
                    w_X = np.concatenate([w_norm_prices, w_norm_vols], axis=1)
                    rs_windows.append(torch.tensor(w_X, dtype=torch.float32).unsqueeze(0).to(self.device))
                out_rs = self.nn_rs_model(rs_windows).cpu().numpy()[0]
                h_res, h_sup, t_res, t_sup = (float(v) for v in out_rs)

            if self.nn_fb_model is not None:
                out_fb = self.nn_fb_model(tensor_X).cpu().numpy()[0]
            if self.nn_mr_model is not None:
                out_mr = self.nn_mr_model(tensor_X).cpu().numpy()[0]

        nn_resistance = max(h_res, t_res)
        nn_support = max(h_sup, t_sup)

        return (nn_resistance, nn_support, float(out_fb[0]), float(out_fb[1]),
                float(out_mr[0]), float(out_mr[1]), float(out_mr[2]),
                h_res, h_sup, t_res, t_sup)

    def analyze_window(self, df_window: pd.DataFrame, asset: str = "_default") -> dict:
        """
        Головний метод аналізу. Отримує датафрейм (вікно до поточної свічки),
        повертає сигнал та детальний розбір прийняття рішення.
        `asset` — ідентифікатор активу для ковзної історії рівнів (крок 5.5),
        бо один екземпляр класу може обходити кілька активів по черзі.
        """
        if df_window is None or df_window.empty:
            return {"signal": None, "confidence": 0, "reason": "No data"}

        last_row = df_window.iloc[-1]

        # 0. ШІ-прогноз (потрібен ДО режиму — режим тепер визначає MR-мережа)
        (nn_resistance, nn_support, fb_bullish, fb_bearish, mr_trend, mr_flat, mr_explosion,
         h_res, h_sup, t_res, t_sup) = self._predict_nn_scores(df_window)

        # 1. Режим ринку — головний ґейт (MR-мережа)
        regime = self._determine_regime(mr_trend, mr_flat, mr_explosion)

        # Стара індикаторна система лишається як незалежний додатковий
        # запобіжник (VOLATILE/FLAT у _apply_context_rules) і джерело напрямку
        market_state = self._determine_market_state(last_row)
        direction = self._determine_trend_direction(last_row) if regime == "TREND" else None

        # 2. Сила тренду (лише коли regime == TREND)
        trend_strength = self._determine_trend_strength(last_row, regime)

        # 3. Адаптація ваг за режимом
        adapted_weights = self._adapt_weights(regime, trend_strength)

        # 4. Збір сигналів
        signals = self._gather_signals(last_row, df_window, nn_support, nn_resistance, regime, direction)

        # Без жорстких порогів: сирий sigmoid-вихід (0..1) напряму як signal_dir,
        # той самий порядок величини, що й у решти індикаторів (±1) — масштабування
        # відбувається через adapted_weights, а не через штучний *10-множник, який
        # раніше змушував NN-сигнали повністю домінувати над усіма іншими.
        signals['NN_Support_Level'] = nn_support
        signals['NN_Resistance_Level'] = -nn_resistance

        # Зв'язок "FB має сенс лише за підтвердження від RS" лишається, але
        # безперервно: сила сигналу природньо згасає до 0, коли RS не бачить
        # рівня, замість жорсткого AND на двох магічних порогах.
        signals['NN_FB_Bullish'] = fb_bullish * nn_support
        signals['NN_FB_Bearish'] = -(fb_bearish * nn_resistance)
        fb_bullish_confirmed = fb_bullish > 0 and nn_support > 0
        fb_bearish_confirmed = fb_bearish > 0 and nn_resistance > 0

        # 4.1 Застосування Правил Гри (лише абсолютний MR-блок + стара VOLATILE/FLAT
        # система; контр-тренд і рівні тепер обробляються окремо, крок 5.5)
        if self.use_context_rules:
            signals = self._apply_context_rules(market_state, signals, last_row, mr_explosion)

        # 5. Розрахунок скорингу (сирий, без контр-трендового штрафу)
        buy_score = 0.0
        sell_score = 0.0
        details = []

        for ind_name, signal_dir in signals.items():
            if signal_dir == 0:
                continue

            # Якщо volume_validation зменшив signal_dir (наприклад до 0.5), вага теж зменшиться
            weight = adapted_weights.get(ind_name, 0.0) * abs(signal_dir)

            if signal_dir > 0:
                buy_score += weight
                details.append(f"🟢 {ind_name}: вага {weight:.2f}")
            elif signal_dir < 0:
                sell_score += weight
                details.append(f"🔴 {ind_name}: вага {weight:.2f}")

        # 5.5 Штраф контр-тренду: диференційований за силою тренду та EMA-50 історією рівнів
        counter_trend_penalty = 0.0
        if regime == "TREND":
            hist = self._level_history.setdefault(
                asset, {'ema_res': 0.0, 'ema_sup': 0.0, 'initialized': False}
            )
            
            alpha = 2.0 / (50 + 1) # EMA з періодом 50
            
            if not hist['initialized']:
                hist['ema_res'] = nn_resistance
                hist['ema_sup'] = nn_support
                hist['initialized'] = True
            else:
                hist['ema_res'] = alpha * nn_resistance + (1 - alpha) * hist['ema_res']
                hist['ema_sup'] = alpha * nn_support + (1 - alpha) * hist['ema_sup']
                
            avg_res = hist['ema_res']
            avg_sup = hist['ema_sup']

            if direction == "UP":
                level_signal, avg = nn_resistance, avg_res
            else:
                level_signal, avg = nn_support, avg_sup

            proximity = 0.0
            if avg > 0:
                excess = max(0.0, level_signal - avg)
                proximity = min(1.0, excess / avg)
                
            if trend_strength == "STRONG":
                max_penalty = 0.60
            elif trend_strength == "MEDIUM":
                max_penalty = 0.35
            else:
                max_penalty = 0.15
                
            counter_trend_penalty = max_penalty * (1.0 - proximity)

            if direction == "UP":
                sell_score *= (1.0 - counter_trend_penalty)
            else:
                buy_score *= (1.0 - counter_trend_penalty)

        # 6. Визначення порогу агресії
        threshold = self._get_aggression_threshold(trend_strength, market_state)

        # Нормалізація (базова максимальна можлива вага для одного напрямку)
        max_possible_weight = sum([w for k, w in adapted_weights.items() if "Bearish" not in k])
        # Трохи занижуємо теоретичний максимум, оскільки всі індикатори одночасно спрацьовують рідко
        practical_max = max_possible_weight * 0.4

        normalized_buy = min(buy_score / (practical_max + 1e-5), 1.0)
        normalized_sell = min(sell_score / (practical_max + 1e-5), 1.0)

        # 6.5 Фільтр торгової сесії: мертва зона (21:00-23:00 UTC, найтихіший
        # проміжок доби практично для всіх forex-майорів) — повний блок;
        # азійська сесія — м'який дампінг (не вето, і далі порівнюємо зі
        # звичайним порогом); Лондон/NY — без змін. Один уніфікований гейт
        # на всі активи замість per-asset магічних годин.
        session = self._determine_session(last_row)
        session_mult = {"DEAD": 0.0, "ASIAN": 0.6}.get(session, 1.0)
        normalized_buy *= session_mult
        normalized_sell *= session_mult

        final_signal = None
        confidence = 0.0

        if normalized_buy > threshold and normalized_buy > normalized_sell:
            final_signal = "BUY"
            confidence = normalized_buy
        elif normalized_sell > threshold and normalized_sell > normalized_buy:
            final_signal = "SELL"
            confidence = normalized_sell

        # Визначаємо причину відсутності сигналу (для UI)
        block_reason = ""
        if final_signal is None and self.use_context_rules:
            if regime == "VOLATILE":
                block_reason = f"⚡ Блок: MR Вибух ({mr_explosion:.2f} > 0.5)"
            elif market_state == "VOLATILE":
                block_reason = "🌪️ Блок: Ринок у стані Хаосу (VOLATILE, індикатор)"
            elif session == "DEAD":
                block_reason = "🌙 Блок: мертва торгова зона (21:00-23:00 UTC)"
            elif market_state == "FLAT" and regime == "FLAT":
                block_reason = "⏸️ Блок: FLAT без дотику до меж каналу"
            elif regime == "TREND" and counter_trend_penalty > 0:
                block_reason = f"📈 Регім TREND ({direction}) — контр-тренд оштрафовано на {counter_trend_penalty:.0%}"
            elif session == "ASIAN" and normalized_buy < threshold and normalized_sell < threshold:
                block_reason = f"🌏 Азійська сесія — сигнал ослаблено ×{session_mult}, недостатньо для порогу"
            elif normalized_buy < threshold and normalized_sell < threshold:
                block_reason = f"🔇 Нижче порогу ({threshold:.0%}) — сигнал слабкий"

        return {
            "signal": final_signal,
            "confidence": round(confidence, 3),
            "buy_score": round(normalized_buy, 3),
            "sell_score": round(normalized_sell, 3),
            "regime": regime,
            "market_state": market_state,
            "trend_direction": direction,
            "trend_strength": trend_strength,
            "threshold": threshold,
            "counter_trend_penalty": round(counter_trend_penalty, 3),
            "nn_resistance": round(nn_resistance, 3),
            "nn_support": round(nn_support, 3),
            "nn_fb_bullish": round(fb_bullish, 3),
            "nn_fb_bearish": round(fb_bearish, 3),
            "fb_bullish_confirmed": fb_bullish_confirmed,
            "fb_bearish_confirmed": fb_bearish_confirmed,
            "mr_trend": round(mr_trend, 3),
            "mr_flat": round(mr_flat, 3),
            "mr_explosion": round(mr_explosion, 3),
            "h_resistance": round(h_res, 3),
            "h_support": round(h_sup, 3),
            "t_resistance": round(t_res, 3),
            "t_support": round(t_sup, 3),
            "session": session,
            "session_mult": session_mult,
            "active_signals": details,
            "raw_buy": round(buy_score, 2),
            "raw_sell": round(sell_score, 2),
            "block_reason": block_reason
        }

    def _determine_market_state(self, last_row: pd.Series) -> str:
        """Визначає: UPTREND, DOWNTREND, FLAT, VOLATILE"""
        state_cols = [c for c in last_row.index if 'Market_State_Linear' in c]
        if state_cols:
            val = last_row[state_cols[0]]
            if val == 1: return "UPTREND"
            if val == -1: return "DOWNTREND"
            if val == 3: return "VOLATILE"
            return "FLAT"

        # Fallback якщо індикатор стану відсутній
        return "FLAT"

    def _determine_regime(self, mr_trend: float, mr_flat: float, mr_explosion: float) -> str:
        """
        Режим ринку за MR-мережею — перший ґейт, що вмикає гілку логіки
        (TREND/FLAT/VOLATILE). mr_trend/mr_flat/mr_explosion — незалежні
        sigmoid-виходи (не сума=1, кожен своя бінарна класифікація).
        mr_explosion має абсолютний пріоритет (природна межа 0.5 для
        бінарного BCE-класифікатора). Інакше — мікс: TREND лише якщо
        mr_trend впевнено переважає (підлога 0.55, а не просто "більше").
        """
        if mr_explosion > 0.5:
            return "VOLATILE"
        if mr_trend >= 0.55 and mr_trend > mr_flat:
            return "TREND"
        return "FLAT"

    def _determine_trend_direction(self, last_row: pd.Series) -> str:
        """
        Напрямок тренду за знаком нахилу (Market_Slope) — окремо від
        категоріальної Market_State_Linear-системи, щоб не мати конфлікту
        двох незалежних класифікаторів, коли регім (з MR) уже сказав TREND.
        """
        slope_cols = [c for c in last_row.index if 'Market_Slope' in c]
        slope_val = last_row[slope_cols[0]] if slope_cols else 0.0
        return "UP" if slope_val >= 0 else "DOWN"

    def _determine_session(self, last_row: pd.Series) -> str:
        """
        Торгова сесія за UTC-годиною свічки (`timestamp` — epoch-мілісекунди,
        тому обов'язково unit='ms' — без цього pandas трактує число як
        наносекунди і дата виходить 1970 рік).
        Ліквідність forex-майорів: Лондон+NY (07:00-21:00 UTC) — пік;
        азійська сесія (23:00-07:00) — тихіше для EUR/GBP/USD пар;
        21:00-23:00 UTC (після закриття NY, до старту Азії) — найтихіший
        проміжок доби практично для всіх пар одразу.
        Один уніфікований гейт на всі активи, а не per-asset список годин.
        """
        if 'timestamp' not in last_row.index:
            return "UNKNOWN"
        try:
            hour = pd.to_datetime(last_row['timestamp'], unit='ms').hour
        except Exception:
            return "UNKNOWN"

        if 21 <= hour < 23:
            return "DEAD"
        if 7 <= hour < 21:
            return "ACTIVE"
        return "ASIAN"

    def _determine_trend_strength(self, last_row: pd.Series, regime: str) -> str:
        """Визначає силу тренду: STRONG, MEDIUM, SLOW (лише коли regime == TREND)"""
        if regime != "TREND":
            return "NONE"

        slope_cols = [c for c in last_row.index if 'Market_Slope' in c]
        adx_cols = [c for c in last_row.index if 'ADX' in c]

        slope_val = abs(last_row[slope_cols[0]]) if slope_cols else 0.0
        adx_val = last_row[adx_cols[0]] if adx_cols else 0.0

        # Евристика сили (slope_val тепер це відношення нахилу до ATR)
        if adx_val > 40 or slope_val > 0.15:
            return "STRONG"
        elif adx_val > 25 or slope_val > 0.08:
            return "MEDIUM"
        else:
            return "SLOW"

    def _adapt_weights(self, regime: str, trend_strength: str) -> dict:
        """
        Одна регім-залежна таблиця ваг (замість попереднього подвійного
        накладання "Golden Oscillator" базової таблиці + market_state-override,
        які суперечили одне одному). Вибір ваг ґрунтується на усталеній теорії
        технічного аналізу, а не підгоні під власний бектест (Раунди 1-2 показали,
        що підгін під наші дані не узагальнюється):

        TREND — королі трендові індикатори (MACD/SMA/EMA-Cross/ADX), осцилятори
        приглушені, але НЕ занулені (можуть дати вхід за трендом на відкаті —
        контр-трендове використання додатково штрафується окремо, крок 5.5).

        FLAT — королі осцилятори й канали (та сама "Golden Oscillator" таблиця,
        що вже випадково давала найкращий WR), трендові індикатори майже в нуль
        (у флеті вони лише шум), рівні (NN_Support/Resistance) підсилені —
        у флеті логічно більше опиратись на рівні.
        """
        if regime == "TREND":
            weights = {
                "MACD": 1.8, "SMA_Cross": 1.6, "EMA_Cross": 1.6, "ADX": 1.4,
                "RSI": 0.4, "Stochastic": 0.4, "CCI": 0.4, "WilliamsR": 0.4,
                "Bollinger": 0.4, "Keltner": 0.4,
                "Bullish_OB": 0.8, "Bearish_OB": 0.8,
                "Bullish_FVG": 0.6, "Bearish_FVG": 0.6,
                "WCE": 0.6, "NGram": 0.6, "Anomaly": 0.7,
                "Levels": 0.5, "Liquidity_Sweep": 0.5,
                "NN_Support_Level": 1.0, "NN_Resistance_Level": 1.0,
            }
        else:  # FLAT (і VOLATILE — не має значення, торгівля все одно блокується)
            weights = {
                "RSI": 2.0, "Stochastic": 2.0, "CCI": 1.0, "WilliamsR": 1.0,
                "Bollinger": 1.5, "Keltner": 1.5,
                "MACD": 0.15, "SMA_Cross": 0.15, "EMA_Cross": 0.15, "ADX": 0.15,
                "Bullish_OB": 0.8, "Bearish_OB": 0.8,
                "Bullish_FVG": 0.0, "Bearish_FVG": 0.0,
                "WCE": 0.6, "NGram": 0.6, "Anomaly": 0.7,
                "Levels": 0.8, "Liquidity_Sweep": 0.8,
                "NN_Support_Level": 1.3, "NN_Resistance_Level": 1.3,
            }

        # Додаємо патерни з базової ваги (не перекриті регім-таблицею вище)
        for p in self.base_weights.keys():
            if p not in weights:
                weights[p] = self.base_weights[p]

        # Адаптація за силою тренду (як було в оригіналі) — застосовується
        # лише коли regime == TREND, бо інакше trend_strength завжди "NONE"
        if trend_strength == "STRONG":
            for k in weights.keys():
                if weights[k] > 0.6: weights[k] *= 1.2
        elif trend_strength == "SLOW":
            for k in weights.keys(): weights[k] *= 0.8

        return weights

    def _get_aggression_threshold(self, trend_strength: str, market_state: str) -> float:
        """
        Піднімаємо поріг до 0.65, щоб відсіяти невпевнені сигнали та дотягнути до 60% WR.

        ПРИМІТКА: те саме, що і в _adapt_weights — trend_strength/market_state
        приймаються, але ігноруються навмисно в цій версії. Окремий підозрюваний
        для наступного ablation-прогону.
        """
        return 0.65

    def _apply_context_rules(self, market_state: str, signals: dict, last_row: pd.Series, mr_explosion: float = 0.0) -> dict:
        """
        Правила гри, що лишились після Раунду 3: контр-тренд і "гасіння біля
        рівнів" тепер обробляються окремо (крок 5.5 у analyze_window — штраф
        замість жорсткого вето). Тут — лише абсолютний MR-блок при ризику
        вибуху і стара індикаторна система (VOLATILE/FLAT) як незалежний
        додатковий запобіжник.
        """
        filtered = signals.copy()

        # Абсолютний пріоритет: mr_explosion — бінарний BCE-класифікатор
        # (таргет 0/1), природна межа рішення мережі — 0.5.
        if mr_explosion > 0.5:
            for k in list(filtered.keys()): filtered[k] = 0
            return filtered

        # Повна заборона торгівлі в Хаосі (стара індикаторна система, незалежний запобіжник)
        if market_state == "VOLATILE":
            for k in list(filtered.keys()):
                filtered[k] = 0

        # Правило Флету: без дотику до меж каналу відключаємо трендові індикатори
        if market_state == "FLAT":
            has_band_touch = ('Bollinger' in signals and signals['Bollinger'] != 0) or \
                             ('Keltner' in signals and signals['Keltner'] != 0)
            if not has_band_touch:
                for k in ['MACD', 'SMA_Cross', 'EMA_Cross', 'ADX']:
                    if k in filtered: filtered[k] = 0
        return filtered

    def _gather_signals(self, last_row: pd.Series, df: pd.DataFrame, nn_support: float = 0.0, nn_resistance: float = 0.0, regime: str = "FLAT", direction: str = None) -> dict:
        """
        Збирає поточні сигнали (1 для BUY, -1 для SELL, 0 для очікування)
        з усіх наявних у last_row колонок.
        """
        signals = {}

        # ==========================================
        # 1. Трендові індикатори
        # ==========================================
        macd_cols = [c for c in last_row.index if c.startswith('MACD_') and 'Hist' not in c and 'Signal' not in c]
        macd_hist_cols = [c for c in last_row.index if c.startswith('MACD_Hist')]
        if macd_hist_cols:
            hist = last_row[macd_hist_cols[0]]
            prev_hist = df.iloc[-2][macd_hist_cols[0]] if len(df) > 1 else hist
            if hist > 0 and prev_hist <= 0: signals['MACD'] = 1
            elif hist < 0 and prev_hist >= 0: signals['MACD'] = -1

        sma_cross_cols = [c for c in last_row.index if c.startswith('SMA_Cross')]
        if sma_cross_cols:
            val = last_row[sma_cross_cols[0]]
            signals['SMA_Cross'] = 1 if val > 0 else (-1 if val < 0 else 0)

        ema_cross_cols = [c for c in last_row.index if c.startswith('EMA_Cross')]
        if ema_cross_cols:
            val = last_row[ema_cross_cols[0]]
            signals['EMA_Cross'] = 1 if val > 0 else (-1 if val < 0 else 0)

        # ==========================================
        # 3. Алгоритмічні (рівні та структура)
        # ==========================================
        algo_mult = 1.0

        if 'Near_Support' in last_row.index and last_row['Near_Support']:
            signals['Levels'] = 1 * algo_mult
        elif 'Near_Resistance' in last_row.index and last_row['Near_Resistance']:
            signals['Levels'] = -1 * algo_mult

        if 'Sweep_Low' in last_row.index and last_row['Sweep_Low']:
            signals['Liquidity_Sweep'] = 1 * algo_mult
        elif 'Sweep_High' in last_row.index and last_row['Sweep_High']:
            signals['Liquidity_Sweep'] = -1 * algo_mult

        # ==========================================
        # 4. Осцилятори
        # ==========================================
        rsi_cols = [c for c in last_row.index if c.startswith('RSI')]
        if rsi_cols:
            rsi = last_row[rsi_cols[0]]
            prev_rsi = df.iloc[-2][rsi_cols[0]] if len(df) > 1 else rsi
            if rsi < 30 and prev_rsi >= 30: signals['RSI'] = 1  # Перетин знизу вгору (вихід з перепроданості)
            elif rsi > 70 and prev_rsi <= 70: signals['RSI'] = -1 # Перетин зверху вниз (вихід з перекупленості)

        stoch_k_cols = [c for c in last_row.index if c.startswith('Stochastic_K')]
        stoch_d_cols = [c for c in last_row.index if c.startswith('Stochastic_D')]
        if stoch_k_cols and stoch_d_cols:
            k = last_row[stoch_k_cols[0]]
            d = last_row[stoch_d_cols[0]]
            if k < 20 and k > d: signals['Stochastic'] = 1
            elif k > 80 and k < d: signals['Stochastic'] = -1

        cci_cols = [c for c in last_row.index if c.startswith('CCI')]
        if cci_cols:
            cci = last_row[cci_cols[0]]
            if cci < -100: signals['CCI'] = 1
            elif cci > 100: signals['CCI'] = -1

        will_cols = [c for c in last_row.index if c.startswith('WilliamsR')]
        if will_cols:
            will = last_row[will_cols[0]]
            if will < -80: signals['WilliamsR'] = 1
            elif will > -20: signals['WilliamsR'] = -1

        # ==========================================
        # 3. Смуги та Канали (повернення до середнього)
        # ==========================================
        close = last_row['close'] if 'close' in last_row.index else 0

        boll_lower = [c for c in last_row.index if c.startswith('Bollinger_Lower')]
        boll_upper = [c for c in last_row.index if c.startswith('Bollinger_Upper')]
        if boll_lower and boll_upper and close:
            if close <= last_row[boll_lower[0]]: signals['Bollinger'] = 1
            elif close >= last_row[boll_upper[0]]: signals['Bollinger'] = -1

        kelt_lower = [c for c in last_row.index if c.startswith('Keltner_Lower')]
        kelt_upper = [c for c in last_row.index if c.startswith('Keltner_Upper')]
        if kelt_lower and kelt_upper and close:
            if close <= last_row[kelt_lower[0]]: signals['Keltner'] = 1
            elif close >= last_row[kelt_upper[0]]: signals['Keltner'] = -1

        # ==========================================
        # 4. Патерни та Volume Validation
        # ==========================================
        vol_avg_cols = [c for c in last_row.index if c.startswith('Volume_Avg')]
        vol_valid = True
        if vol_avg_cols and 'volume' in last_row.index:
            # Якщо об'єм нижче середнього, сила патерну зменшується вдвічі
            vol_valid = last_row['volume'] >= last_row[vol_avg_cols[0]]

        vol_mult = 1.0 if vol_valid else 0.5
        
        atr_cols = [c for c in last_row.index if c.startswith('ATR')]
        body_valid = True
        if atr_cols and 'open' in last_row.index and 'close' in last_row.index:
            atr_val = last_row[atr_cols[0]]
            body = abs(last_row['close'] - last_row['open'])
            if atr_val > 0:
                body_valid = body >= 0.8 * atr_val
                
        smc_mult = 1.0 if (vol_valid and body_valid) else 0.5

        # ПОВЕРНУТО ПАТЕРНИ ЗІ ЗМЕНШЕНОЮ ВАГОЮ (1/3)
        pattern_mult = 0.33
        if 'Engulfing' in last_row.index:
            if last_row['Engulfing'] == 1: signals['Engulfing_Bullish'] = 1 * vol_mult * pattern_mult
            elif last_row['Engulfing'] == -1: signals['Engulfing_Bearish'] = -1 * vol_mult * pattern_mult

        pattern_mappings = {
            'Morning_Star': 1,
            'Hammer': 1,
            'Inverted_Hammer': 1,
            'Piercing_Pattern': 1,
            'Three_White_Soldiers': 1,
            'Evening_Star': -1,
            'Shooting_Star': -1,
            'Dark_Cloud_Cover': -1,
            'Three_Black_Crows': -1,
            'Hanging_Man': -1
        }

        for pat, dir_val in pattern_mappings.items():
            if pat in last_row.index and last_row[pat] > 0:
                signals[pat] = dir_val * vol_mult * pattern_mult

        # ==========================================
        # 5. SMC (Fair Value Gaps & Order Blocks) з AlgorithmProcessor
        # ==========================================
        
        # ФІЛЬТР: SMC сигнали беремо ТІЛЬКИ якщо вони співпадають із напрямком глобального тренду!
        # Якщо ми у флеті (regime != "TREND"), SMC можна торгувати як відбій від границь,
        # але набагато безпечніше вимагати узгодженості тренду.
        can_trade_bullish_smc = (regime == "TREND" and direction == "UP") or (nn_support >= 0.5)
        can_trade_bearish_smc = (regime == "TREND" and direction == "DOWN") or (nn_resistance >= 0.5)

        if can_trade_bullish_smc:
            if 'FVG_Up' in last_row.index and last_row['FVG_Up']:
                signals['Bullish_FVG'] = 1 * smc_mult
            if 'Bullish_OB' in last_row.index and last_row['Bullish_OB']:
                signals['Bullish_OB'] = 1 * smc_mult
                
        if can_trade_bearish_smc:
            if 'FVG_Down' in last_row.index and last_row['FVG_Down']:
                signals['Bearish_FVG'] = -1 * smc_mult
            if 'Bearish_OB' in last_row.index and last_row['Bearish_OB']:
                signals['Bearish_OB'] = -1 * smc_mult

        # ==========================================
        # 6. Симбіоз (Контекстна фільтрація)
        # ==========================================
        if 'SMA_Cross' in signals and 'MACD' in signals:
            if signals['SMA_Cross'] > 0 and signals['MACD'] < 0: signals['SMA_Cross'] = 0
            elif signals['SMA_Cross'] < 0 and signals['MACD'] > 0: signals['SMA_Cross'] = 0

        if 'EMA_Cross' in signals and 'MACD' in signals:
            if signals['EMA_Cross'] > 0 and signals['MACD'] < 0: signals['EMA_Cross'] = 0
            elif signals['EMA_Cross'] < 0 and signals['MACD'] > 0: signals['EMA_Cross'] = 0

        return signals


# Приклад використання (для тестування):
if __name__ == "__main__":
    # Генерація фейкового датафрейму для тесту
    data = {
        'close': [100, 102, 101, 105],
        'Market_State_Linear_20': [1, 1, 1, 1], # UPTREND
        'Market_Slope_20': [0.1, 0.2, 0.35, 0.4], # STRONG
        'ADX_14': [20, 25, 30, 45], # STRONG
        'MACD_Hist_12_26_9': [-0.1, 0.0, 0.1, 0.2], # Перетин вверх -> BUY
        'RSI_14': [50, 60, 65, 75], # Overbought
        'Engulfing': [0, 0, 0, 1] # Bullish Engulfing
    }
    df = pd.DataFrame(data)

    logic = CopilotAlgorithmicLogic()
    res = logic.analyze_window(df)

    print("Результат аналізу:")
    for k, v in res.items():
        if isinstance(v, list):
            print(f"{k}:")
            for item in v:
                print(f"  - {item}")
        else:
            print(f"{k}: {v}")
