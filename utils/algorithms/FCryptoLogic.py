import math
import pandas as pd
from models.FFB.FFB import FFB
from models.FRS.FRS import FRS
from models.FMR.FMR import FMR

class FCryptoLogic:

    #------------------------------
    # Initialization
    #------------------------------

    # Крипто-моделі вантажимо ОДИН раз на весь клас (кеш), а не на кожне
    # вікно/екземпляр — інакше бектест перевантажував би їх щосвічки.
    _fmr = None
    _ffb = None
    _frs = None

    # --- Сім'ї сигналів (для конфлюенсу незалежних джерел) ---
    # Тригери всередині однієї сім'ї СКОРЕЛЬОВАНІ (по суті одне й те саме), тому рахуються
    # як ОДИН незалежний голос, а не додаються кожен окремо. Вхід дозволено лише за збігом
    # ≥2 РІЗНИХ сімей АБО спрацюванням структурного тригера (сім'я 'zone') — він сам по собі
    # багатофакторний (НН + зона + сила зони) і має право стояти один.
    _PRIMARY_FAMILY = 'zone'
    _FAMILY_OF = {
        # Структурний тригер (первинний, може стояти один)
        'fb_zone': 'zone',
        'trend_zone': 'zone',
        # Структура ринку (Smart Money)
        'smc_bos': 'smc',
        'smc_choch': 'smc',
        'smc_liquidity_sweep': 'smc',
        # Нові SMC-концепції — КОЖНА окрема незалежна сім'я (різні механізми)
        'smc_order_block': 'order_block',       # ретест зони попиту/пропозиції
        'smc_fvg': 'fvg',                       # імбаланс (дисплейсмент)
        'smc_premium_discount': 'pd_zone',      # місце ціни в діапазоні
        # Осцилятори (mean-reversion) — одна сім'я (скорельовані клони)
        'ind_rsi': 'oscillators', 'ind_stoch': 'oscillators', 'ind_cci': 'oscillators',
        'ind_willr': 'oscillators', 'ind_boll': 'oscillators', 'ind_kelt': 'oscillators',
        # Трендові індикатори — одна сім'я
        'ind_macd': 'trend_follow', 'ind_sma': 'trend_follow', 'ind_ema': 'trend_follow',
        # Свічкові патерни — одна сім'я
        'pattern': 'patterns',
    }

    # Масштаб перетворення накопиченої переконаності у впевненість 0..1 (насичення).
    # Чим більше/важче незалежних підтверджень — тим вища впевненість. Не підганяється
    # під результат тесту: це просто шкала, щоб впевненість осмислено лягала в пороги.
    _CONFIDENCE_SCALE = 0.9

    def __init__(self, df: pd.DataFrame):
        "Моделі підвантажуються один раз (кеш класу), далі беруться з кешу"
        if FCryptoLogic._ffb is None:
            FCryptoLogic._fmr = FMR()
            FCryptoLogic._ffb = FFB()
            FCryptoLogic._frs = FRS()

        self.mr = FCryptoLogic._fmr
        self.fb = FCryptoLogic._ffb
        self.rs = FCryptoLogic._frs

        # Поріг впевненості для генерації сигналу
        self.fb_threshold = 0.65 # Знижено для більшої кількості сигналів після жорсткої фільтрації зонами

        # Система ваг тригерів ПО СЦЕНАРІЯХ (режимах). Ваги фіксовані й змінюються
        # ЛИШЕ зі сценарієм — як у старому боті, без підгону під бектест.
        # Внесок тригера у скоринг = вага × впевненість. Нові тригери просто
        # додаються у відповідний режим із власною вагою.
        # Індикатори та свічкові патерни ПОВЕРНЕНО як окремі сім'ї (капнуті — один голос
        # на сім'ю, щоб клони не роздували). У FLAT королі — осцилятори; у TREND — трендові.
        self.weights = {
            'FLAT': {
                'fb_zone': 1.0,               # фейд хибного пробою в горизонтальній зоні
                'smc_premium_discount': 0.4,  # покупка в дисконті / продаж у премії
                # Осцилятори (mean-reversion) — королі флету
                'ind_rsi': 0.5, 'ind_stoch': 0.5, 'ind_cci': 0.4,
                'ind_willr': 0.4, 'ind_boll': 0.5, 'ind_kelt': 0.5,
                # Свічкові патерни біля зони
                'pattern': 0.5,
            },
            'TREND': {
                'trend_zone': 1.0,            # відкат до динамічного рівня EMA за трендом
                # SMC (структура ринку)
                'smc_bos': 0.6,
                'smc_choch': 0.6,
                'smc_order_block': 0.6,       # ретест Order Block за трендом
                'smc_fvg': 0.5,               # імбаланс/дисплейсмент
                'smc_premium_discount': 0.4,  # не купувати в премії / не продавати в дисконті
                # Трендові індикатори — королі тренду
                'ind_macd': 0.6, 'ind_sma': 0.5, 'ind_ema': 0.5,
                # Свічкові патерни за трендом
                'pattern': 0.4,
            },
            'EXPLOSION': {
                'smc_liquidity_sweep': 0.8,   # Робота з Liquidity Sweep на імпульсах
            }
        }

        self.df_processed = df.copy()

    #==============================
    # Methods for analysis. Input data
    #==============================

    #------------------------------
    # Generation of data. Market state
    #------------------------------

    def _add_market_regime(self) -> pd.DataFrame:
        "Додає інформацію про стан ринку (MR)"
        return self.mr.process(self.df_processed)

    #------------------------------
    # Generation of data. Support and resistance levels
    #------------------------------

    def _add_support_resistance(self) -> pd.DataFrame:
        "Додає інформацію про рівні підтримки та опору (RS)"
        return self.rs.process(self.df_processed)

    #------------------------------
    # Generation of data. False breakouts
    #------------------------------

    def _add_false_breakouts(self) -> pd.DataFrame:
        "Додає інформацію про хибні пробої (FB)"
        return self.fb.process(self.df_processed)

    #------------------------------
    # Generation of data. Technical Analysis & Patterns
    #------------------------------

    def _add_technical_analysis(self) -> pd.DataFrame:
        "Додає інформацію з індикаторів, патернів та алгоритмів SMC"
        from utils.algorithms.indicators.DataProcessingManager import DataProcessingManager
        
        # Ініціалізуємо DataProcessingManager без жорстких параметрів, 
        # щоб він за замовчуванням підтягнув ВСІ доступні методи з класів.
        dpm = DataProcessingManager(
            data=self.df_processed,
            indicators_params=None,
            pattern_params=None,
            algorithm_params=None
        )
        return dpm.process_all()

    #------------------------------
    # Combining data (INPUT DATA)
    #------------------------------

    def _enrich_data(self) -> pd.DataFrame:
        "Єдиний метод, який запускає всі інші для збагачення даних"
        
        # Підключаємо тех. аналіз та патерни
        self.df_processed = self._add_technical_analysis()
        
        # Послідовно пропускаємо через усі мережі
        self.df_processed = self._add_market_regime()
        self.df_processed = self._add_support_resistance()
        self.df_processed = self._add_false_breakouts()
        
        return self.df_processed

    #==============================
    # Methods of Logic
    #==============================

    #------------------------------
    # Triggering FB logic
    #------------------------------

    def _logic_fb_trigger(self) -> pd.DataFrame:
        "Метод логіки: оцінює хибні пробої та рівні, додаючи колонки тригерів до датафрейму"
        df_logic = self.df_processed.copy()
        
        def evaluate_row(row):
            # Аналіз стану ринку (MR)
            states = {'TREND': row.get('FMR_Trend', 0.0), 'FLAT': row.get('FMR_Flat', 0.0), 'EXPLOSION': row.get('FMR_Explosion', 0.0)}
            market_state = max(states, key=states.get)
            
            fb_bull = row.get('FFB_Bullish', 0.0)
            fb_bear = row.get('FFB_Bearish', 0.0)
            
            sup_prox = row.get('FRS_sup_proximity', 0.0)
            sup_str = row.get('FRS_sup_strength', 0.0)
            res_prox = row.get('FRS_res_proximity', 0.0)
            res_str = row.get('FRS_res_strength', 0.0)
            
            if market_state != 'FLAT':
                return pd.Series(['NEUTRAL', 0.0, f"Тригер FB не активний для режиму {market_state}", market_state])
                
            min_strength = 0.20
            
            if fb_bull >= self.fb_threshold and fb_bull > fb_bear:
                if sup_prox > 0.5:
                    if sup_str >= min_strength:
                        return pd.Series(['BUY', fb_bull, None, market_state])
                    else:
                        return pd.Series(['NEUTRAL', 0.0, f"Сигнал BUY ігноровано: зона Підтримки занадто слабка", market_state])
                else:
                    return pd.Series(['NEUTRAL', 0.0, "Сигнал BUY ігноровано: ціна не в зоні Підтримки", market_state])
            
            elif fb_bear >= self.fb_threshold and fb_bear > fb_bull:
                if res_prox > 0.5:
                    if res_str >= min_strength:
                        return pd.Series(['SELL', fb_bear, None, market_state])
                    else:
                        return pd.Series(['NEUTRAL', 0.0, f"Сигнал SELL ігноровано: зона Опору занадто слабка", market_state])
                else:
                    return pd.Series(['NEUTRAL', 0.0, "Сигнал SELL ігноровано: ціна не в зоні Опору", market_state])
                    
            return pd.Series(['NEUTRAL', 0.0, "Немає сильного сигналу від НН", market_state])

        # Застосовуємо логіку та створюємо нові колонки тригеру
        df_logic[['Logic_Signal', 'Logic_Confidence', 'Logic_BlockReason', 'Logic_MarketState']] = df_logic.apply(evaluate_row, axis=1)
        
        return df_logic

    #------------------------------
    # Triggering Trend-zone logic
    #------------------------------

    def _logic_trend_trigger(self) -> pd.DataFrame:
        "Тригер трендових зон: відкат до динамічного рівня EMA ЗА трендом (моментум)"
        df_logic = self.df_processed.copy()

        def evaluate_row(row):
            states = {'TREND': row.get('FMR_Trend', 0.0), 'FLAT': row.get('FMR_Flat', 0.0), 'EXPLOSION': row.get('FMR_Explosion', 0.0)}
            market_state = max(states, key=states.get)

            if market_state != 'TREND':
                return pd.Series(['NEUTRAL', 0.0, f"Трендовий тригер не активний для режиму {market_state}"])

            t_sup_prox = row.get('FRS_trend_sup_proximity', 0.0)   # up-тренд: EMA як підтримка
            t_sup_str = row.get('FRS_trend_sup_strength', 0.0)
            t_res_prox = row.get('FRS_trend_res_proximity', 0.0)   # down-тренд: EMA як опір
            t_res_str = row.get('FRS_trend_res_strength', 0.0)

            min_prox = 0.6   # ціна має відкотитись близько до трендового рівня
            min_str = 0.4    # тренд має бути достатньо сильним

            # Висхідний тренд: купуємо відкат до EMA-підтримки
            if t_sup_str >= min_str and t_sup_prox > min_prox:
                return pd.Series(['BUY', t_sup_str, None])
            # Низхідний тренд: продаємо відкат до EMA-опору
            if t_res_str >= min_str and t_res_prox > min_prox:
                return pd.Series(['SELL', t_res_str, None])

            return pd.Series(['NEUTRAL', 0.0, "Немає відкату до трендового рівня"])

        df_logic[['Logic_Trend_Signal', 'Logic_Trend_Confidence', 'Logic_Trend_BlockReason']] = df_logic.apply(evaluate_row, axis=1)

        return df_logic

    #------------------------------
    # Triggering SMC Logic (Smart Money)
    #------------------------------

    def _logic_smc_trigger(self) -> pd.DataFrame:
        "Аналізує структуру ринку (BOS, CHoCH, Sweep, Order Block, FVG, Премія/Дисконт)"
        df_logic = self.df_processed.copy()

        # Премія/Дисконт: позиція ціни в ковзному діапазоні (свінг High/Low за PD_LOOKBACK).
        # Рахуємо векторно ДО apply, бо це вимагає вікна, а не одного рядка.
        PD_LOOKBACK = 50
        roll_high = df_logic['high'].rolling(PD_LOOKBACK, min_periods=PD_LOOKBACK).max()
        roll_low = df_logic['low'].rolling(PD_LOOKBACK, min_periods=PD_LOOKBACK).min()
        rng = roll_high - roll_low
        df_logic['_pd_pos'] = ((df_logic['close'] - roll_low) / rng).where(rng > 0, 0.5).fillna(0.5)

        def eval_smc(row):
            sweep_high = row.get('Sweep_High', False)
            sweep_low = row.get('Sweep_Low', False)
            bos = row.get('BOS', False)
            choch = row.get('CHoCH', False)
            struct = row.get('Market_Structure_Type', None)

            sig_sweep = ('SELL', 0.9) if sweep_high else ('BUY', 0.9) if sweep_low else ('NEUTRAL', 0.0)

            sig_bos = ('NEUTRAL', 0.0)
            sig_choch = ('NEUTRAL', 0.0)
            # Бичача структура (аптренд) — HH/HL; ведмежа (даунтренд) — LH/LL.
            if struct in ['HH', 'HL']:
                if bos: sig_bos = ('BUY', 0.8)
                if choch: sig_choch = ('BUY', 0.8)
            elif struct in ['LH', 'LL']:
                if bos: sig_bos = ('SELL', 0.8)
                if choch: sig_choch = ('SELL', 0.8)

            # --- НОВІ ТРИГЕРИ ---

            # 1) Order Block: ретест (mitigation) блоку. Bullish_OB — ціна повернулась
            #    у зону попиту → BUY; Bearish_OB — у зону пропозиції → SELL.
            ob_bull = row.get('Bullish_OB', False)
            ob_bear = row.get('Bearish_OB', False)
            sig_ob = ('BUY', 0.8) if ob_bull else ('SELL', 0.8) if ob_bear else ('NEUTRAL', 0.0)

            # 2) Fair Value Gap: імбаланс (момент утворення = дисплейсмент/моментум).
            #    FVG_Up — бичачий → BUY, FVG_Down — ведмежий → SELL.
            fvg_up = row.get('FVG_Up', False)
            fvg_down = row.get('FVG_Down', False)
            sig_fvg = ('BUY', 0.7) if fvg_up else ('SELL', 0.7) if fvg_down else ('NEUTRAL', 0.0)

            # 3) Премія/Дисконт: у нижній чверті діапазону (дисконт) — BUY, у верхній
            #    (премія) — SELL. Сила росте з глибиною. У середині — мовчить.
            pos = row.get('_pd_pos', 0.5)
            if pos < 0.25:
                strength = min(1.0, (0.25 - pos) / 0.25)
                sig_pd = ('BUY', round(0.5 + 0.5 * strength, 3))
            elif pos > 0.75:
                strength = min(1.0, (pos - 0.75) / 0.25)
                sig_pd = ('SELL', round(0.5 + 0.5 * strength, 3))
            else:
                sig_pd = ('NEUTRAL', 0.0)

            return pd.Series([
                sig_sweep[0], sig_sweep[1], sig_bos[0], sig_bos[1], sig_choch[0], sig_choch[1],
                sig_ob[0], sig_ob[1], sig_fvg[0], sig_fvg[1], sig_pd[0], sig_pd[1]
            ])

        columns = [
            'L_SMC_Sweep_Sig', 'L_SMC_Sweep_Conf', 'L_SMC_BOS_Sig', 'L_SMC_BOS_Conf', 'L_SMC_CHoCH_Sig', 'L_SMC_CHoCH_Conf',
            'L_SMC_OB_Sig', 'L_SMC_OB_Conf', 'L_SMC_FVG_Sig', 'L_SMC_FVG_Conf', 'L_SMC_PD_Sig', 'L_SMC_PD_Conf'
        ]
        df_logic[columns] = df_logic.apply(eval_smc, axis=1)
        return df_logic

    #------------------------------
    # Triggering Indicators (осцилятори + трендові)
    #------------------------------

    def _logic_indicators_trigger(self) -> pd.DataFrame:
        "Класичні індикатори: осцилятори (крос-події) + трендові (SMA/EMA/MACD) із симбіозом"
        df_logic = self.df_processed.copy()
        # Попередні значення для крос-подій (RSI, MACD-гістограма)
        df_logic['_prev_rsi'] = df_logic['RSI_14'].shift(1) if 'RSI_14' in df_logic.columns else 50.0
        df_logic['_prev_macd'] = df_logic['MACD_Hist_12_26_9'].shift(1) if 'MACD_Hist_12_26_9' in df_logic.columns else 0.0

        def eval_ind(row):
            close = row.get('close', 0)
            # --- Осцилятори (mean-reversion, події виходу з екстремуму) ---
            rsi = row.get('RSI_14', 50); prsi = row.get('_prev_rsi', 50)
            sig_rsi = ('BUY', 0.8) if (rsi >= 30 and prsi < 30) else ('SELL', 0.8) if (rsi <= 70 and prsi > 70) else ('NEUTRAL', 0.0)
            stoch = row.get('Stochastic_K_14', 50)
            sig_stoch = ('BUY', 0.8) if stoch < 20 else ('SELL', 0.8) if stoch > 80 else ('NEUTRAL', 0.0)
            cci = row.get('CCI_20', 0)
            sig_cci = ('BUY', 0.8) if cci < -100 else ('SELL', 0.8) if cci > 100 else ('NEUTRAL', 0.0)
            wr = row.get('WilliamsR_14', -50)
            sig_wr = ('BUY', 0.8) if wr < -80 else ('SELL', 0.8) if wr > -20 else ('NEUTRAL', 0.0)
            bl = row.get('Bollinger_Lower_20_2', 0); bu = row.get('Bollinger_Upper_20_2', 0)
            sig_boll = ('BUY', 0.7) if (bl > 0 and close <= bl) else ('SELL', 0.7) if (bu > 0 and close >= bu) else ('NEUTRAL', 0.0)
            kl = row.get('Keltner_Lower_20', 0); ku = row.get('Keltner_Upper_20', 0)
            sig_kelt = ('BUY', 0.7) if (kl > 0 and close <= kl) else ('SELL', 0.7) if (ku > 0 and close >= ku) else ('NEUTRAL', 0.0)
            # --- Трендові (події перетину) ---
            mh = row.get('MACD_Hist_12_26_9', 0); pmh = row.get('_prev_macd', 0)
            sig_macd = ('BUY', 0.7) if (mh > 0 and pmh <= 0) else ('SELL', 0.7) if (mh < 0 and pmh >= 0) else ('NEUTRAL', 0.0)
            smc = row.get('SMA_Cross_10_50', 0)
            sig_sma = ('BUY', 0.8) if smc == 1 else ('SELL', 0.8) if smc == -1 else ('NEUTRAL', 0.0)
            emc = row.get('EMA_Cross_10_50', 0)
            sig_ema = ('BUY', 0.8) if emc == 1 else ('SELL', 0.8) if emc == -1 else ('NEUTRAL', 0.0)
            # Симбіоз: SMA/EMA анулюються, якщо суперечать MACD
            if sig_macd[0] != 'NEUTRAL':
                if sig_sma[0] not in ('NEUTRAL', sig_macd[0]): sig_sma = ('NEUTRAL', 0.0)
                if sig_ema[0] not in ('NEUTRAL', sig_macd[0]): sig_ema = ('NEUTRAL', 0.0)

            return pd.Series([
                sig_rsi[0], sig_rsi[1], sig_stoch[0], sig_stoch[1], sig_cci[0], sig_cci[1],
                sig_wr[0], sig_wr[1], sig_boll[0], sig_boll[1], sig_kelt[0], sig_kelt[1],
                sig_macd[0], sig_macd[1], sig_sma[0], sig_sma[1], sig_ema[0], sig_ema[1]
            ])

        cols = [
            'L_Ind_RSI_Sig', 'L_Ind_RSI_Conf', 'L_Ind_Stoch_Sig', 'L_Ind_Stoch_Conf',
            'L_Ind_CCI_Sig', 'L_Ind_CCI_Conf', 'L_Ind_WillR_Sig', 'L_Ind_WillR_Conf',
            'L_Ind_Boll_Sig', 'L_Ind_Boll_Conf', 'L_Ind_Kelt_Sig', 'L_Ind_Kelt_Conf',
            'L_Ind_MACD_Sig', 'L_Ind_MACD_Conf', 'L_Ind_SMA_Sig', 'L_Ind_SMA_Conf',
            'L_Ind_EMA_Sig', 'L_Ind_EMA_Conf'
        ]
        df_logic[cols] = df_logic.apply(eval_ind, axis=1)
        df_logic.drop(columns=['_prev_rsi', '_prev_macd'], inplace=True)
        return df_logic

    #------------------------------
    # Triggering Candlestick Patterns
    #------------------------------

    def _logic_patterns_trigger(self) -> pd.DataFrame:
        "Свічкові патерни БІЛЯ зони, з валідацією об'єму й тіла (один голос-сім'я)"
        df_logic = self.df_processed.copy()

        def eval_pat(row):
            near_sup = max(row.get('FRS_sup_proximity', 0.0), row.get('FRS_trend_sup_proximity', 0.0)) > 0.5
            near_res = max(row.get('FRS_res_proximity', 0.0), row.get('FRS_trend_res_proximity', 0.0)) > 0.5

            vol_avg = row.get('Volume_Avg_20', 0.0)
            vol_ok = (row.get('volume', 0.0) >= vol_avg) if vol_avg > 0 else True
            atr = row.get('ATR_14', 0.0)
            body = abs(row.get('close', 0.0) - row.get('open', 0.0))
            body_ok = (body >= 0.8 * atr) if atr > 0 else True
            conf = 0.8 * (1.0 if (vol_ok and body_ok) else 0.5)   # слабкий об'єм/мале тіло → ×0.5

            bull = (row.get('Hammer', 0) or row.get('Inverted_Hammer', 0) or row.get('Morning_Star', 0)
                    or row.get('Piercing_Pattern', 0) or row.get('Three_White_Soldiers', 0)
                    or row.get('Engulfing', 0) == 1)
            bear = (row.get('Shooting_Star', 0) or row.get('Hanging_Man', 0) or row.get('Evening_Star', 0)
                    or row.get('Dark_Cloud_Cover', 0) or row.get('Three_Black_Crows', 0)
                    or row.get('Engulfing', 0) == -1)

            if bull and near_sup:
                return pd.Series(['BUY', conf])
            if bear and near_res:
                return pd.Series(['SELL', conf])
            return pd.Series(['NEUTRAL', 0.0])

        df_logic[['L_Pat_Sig', 'L_Pat_Conf']] = df_logic.apply(eval_pat, axis=1)
        return df_logic

    #------------------------------
    # Applying logic triggers
    #------------------------------

    def _apply_logic_triggers(self) -> pd.DataFrame:
        "Єдиний метод, який запускає всі логічні тригери"

        self.df_processed = self._logic_fb_trigger()
        self.df_processed = self._logic_trend_trigger()
        self.df_processed = self._logic_smc_trigger()
        self.df_processed = self._logic_indicators_trigger()
        self.df_processed = self._logic_patterns_trigger()

        return self.df_processed

    #------------------------------
    # Trigger Calculation
    #------------------------------

    def _calculate_final_signal(self) -> dict:
        "Метод підрахунку тригерів та формування фінального сигналу"
        last_row = self.df_processed.iloc[-1]
        return self._calculate_row_signal(last_row)
        
    def _calculate_row_signal(self, last_row: pd.Series) -> dict:
        "Оцінює конкретний рядок (використовується для бектесту)"
        # 1. Аналіз стану ринку (MR)
        states = {
            'TREND': last_row.get('FMR_Trend', 0.0), 
            'FLAT': last_row.get('FMR_Flat', 0.0), 
            'EXPLOSION': last_row.get('FMR_Explosion', 0.0)
        }
        market_state = max(states, key=states.get)
        
        # Умова щодо EXPLOSION: угоди не беруться до уваги
        if market_state == 'EXPLOSION':
            return {
                "signal": "NEUTRAL",
                "confidence": 0.0,
                "block_reason": "Ринок у стані EXPLOSION. Торги заборонено.",
                "market_state": market_state,
                "active_triggers": 0
            }
            
        # 2. Збираємо активні тригери ПОТОЧНОГО режиму: (назва, сигнал, впевненість, причина).
        #    Кожен новий тригер просто додається сюди й у таблицю ваг self.weights.
        regime_weights = self.weights.get(market_state, {})
        triggers = []
        mapping = {}

        if market_state == 'FLAT':
            mapping = {
                'fb_zone': ('Logic_Signal', 'Logic_Confidence', 'Logic_BlockReason'),
                'smc_premium_discount': ('L_SMC_PD_Sig', 'L_SMC_PD_Conf', None),
                # Осцилятори (королі флету)
                'ind_rsi': ('L_Ind_RSI_Sig', 'L_Ind_RSI_Conf', None),
                'ind_stoch': ('L_Ind_Stoch_Sig', 'L_Ind_Stoch_Conf', None),
                'ind_cci': ('L_Ind_CCI_Sig', 'L_Ind_CCI_Conf', None),
                'ind_willr': ('L_Ind_WillR_Sig', 'L_Ind_WillR_Conf', None),
                'ind_boll': ('L_Ind_Boll_Sig', 'L_Ind_Boll_Conf', None),
                'ind_kelt': ('L_Ind_Kelt_Sig', 'L_Ind_Kelt_Conf', None),
                # Свічкові патерни
                'pattern': ('L_Pat_Sig', 'L_Pat_Conf', None),
            }
        elif market_state == 'TREND':
            mapping = {
                'trend_zone': ('Logic_Trend_Signal', 'Logic_Trend_Confidence', 'Logic_Trend_BlockReason'),
                'smc_bos': ('L_SMC_BOS_Sig', 'L_SMC_BOS_Conf', None),
                'smc_choch': ('L_SMC_CHoCH_Sig', 'L_SMC_CHoCH_Conf', None),
                'smc_order_block': ('L_SMC_OB_Sig', 'L_SMC_OB_Conf', None),
                'smc_fvg': ('L_SMC_FVG_Sig', 'L_SMC_FVG_Conf', None),
                'smc_premium_discount': ('L_SMC_PD_Sig', 'L_SMC_PD_Conf', None),
                # Трендові індикатори (королі тренду)
                'ind_macd': ('L_Ind_MACD_Sig', 'L_Ind_MACD_Conf', None),
                'ind_sma': ('L_Ind_SMA_Sig', 'L_Ind_SMA_Conf', None),
                'ind_ema': ('L_Ind_EMA_Sig', 'L_Ind_EMA_Conf', None),
                # Свічкові патерни
                'pattern': ('L_Pat_Sig', 'L_Pat_Conf', None),
            }
        elif market_state == 'EXPLOSION':
            mapping = {
                'smc_liquidity_sweep': ('L_SMC_Sweep_Sig', 'L_SMC_Sweep_Conf', None),
            }

        for key, (sig_col, conf_col, reason_col) in mapping.items():
            sig = last_row.get(sig_col, 'NEUTRAL')
            conf = last_row.get(conf_col, 0.0)
            reason = last_row.get(reason_col, None) if reason_col else None
            triggers.append((key, sig, conf, reason))

        # 3. Групуємо тригери в СІМ'Ї незалежних джерел. Скорельовані тригери (напр. BOS і
        #    CHoCH зі структури) підсумовуються ВСЕРЕДИНІ сім'ї й дають ОДИН голос — інакше
        #    клони роздували б переконаність. Внесок тригера = вага (за режимом) × впевненість.
        families = {}   # family -> {'buy': score, 'sell': score, 'cap': max_weight}
        fired = []      # окремі тригери, що дали сигнал — для UI/діагностики
        block_reasons = []

        for name, sig, conf, reason in triggers:
            w = regime_weights.get(name, 0.0)
            fam = self._FAMILY_OF.get(name, name)
            f = families.setdefault(fam, {'buy': 0.0, 'sell': 0.0, 'cap': 0.0})
            f['cap'] = max(f['cap'], w)   # стеля сім'ї = «одне сильне підтвердження»
            if sig == 'BUY':
                f['buy'] += w * conf
                fired.append({'name': name, 'family': fam, 'signal': sig, 'weight': w, 'contribution': round(w * conf, 3)})
            elif sig == 'SELL':
                f['sell'] += w * conf
                fired.append({'name': name, 'family': fam, 'signal': sig, 'weight': w, 'contribution': round(w * conf, 3)})
            elif reason:
                block_reasons.append(f"{name}: {reason}")

        # 4. Кожна сім'я дає ОДИН голос: напрямок = чистий (buy−sell), сила обмежена
        #    стелею сім'ї (щоб кілька SMC-тригерів не переважили структурний числом).
        buy_score = 0.0
        sell_score = 0.0
        buy_families = set()
        sell_families = set()

        for fam, f in families.items():
            net = f['buy'] - f['sell']
            if net > 0:
                buy_score += min(net, f['cap'])
                buy_families.add(fam)
            elif net < 0:
                sell_score += min(-net, f['cap'])
                sell_families.add(fam)

        # 4.5 Штраф контр-тренду (лише TREND): не торгувати ПРОТИ тренду, окрім як біля
        #     сильної протилежної зони. Напрямок тренду беремо з FRS-трендової зони,
        #     послаблення — з близькості/сили горизонтальної зони на боці входу.
        counter_trend_penalty = 0.0
        if market_state == 'TREND':
            t_sup = last_row.get('FRS_trend_sup_strength', 0.0)   # висхідний тренд
            t_res = last_row.get('FRS_trend_res_strength', 0.0)   # низхідний тренд
            max_penalty = 0.6
            if t_sup > t_res and t_sup > 0:            # up-тренд → SELL контр-трендовий
                relax = min(1.0, last_row.get('FRS_res_proximity', 0.0) * last_row.get('FRS_res_strength', 0.0))
                counter_trend_penalty = max_penalty * t_sup * (1.0 - relax)
                sell_score *= (1.0 - counter_trend_penalty)
            elif t_res > t_sup and t_res > 0:          # down-тренд → BUY контр-трендовий
                relax = min(1.0, last_row.get('FRS_sup_proximity', 0.0) * last_row.get('FRS_sup_strength', 0.0))
                counter_trend_penalty = max_penalty * t_res * (1.0 - relax)
                buy_score *= (1.0 - counter_trend_penalty)

        active_triggers = len(fired)

        # 5. Переможець + перевірка КОНФЛЮЕНСУ незалежних джерел.
        if buy_score > sell_score and buy_score > 0:
            win_dir, win_score, win_fams = 'BUY', buy_score, buy_families
        elif sell_score > buy_score and sell_score > 0:
            win_dir, win_score, win_fams = 'SELL', sell_score, sell_families
        else:
            win_dir, win_score, win_fams = 'NEUTRAL', 0.0, set()

        final_signal = 'NEUTRAL'
        final_confidence = 0.0
        final_reason = "Недостатньо тригерів для входу"

        if win_dir != 'NEUTRAL':
            # Вхід дозволено: або ≥2 РІЗНІ сім'ї згодні, або спрацював структурний тригер
            # (сім'я 'zone') — він сам багатофакторний і має право стояти один.
            if len(win_fams) >= 2 or self._PRIMARY_FAMILY in win_fams:
                final_signal = win_dir
                # Впевненість зростає з накопиченою переконаністю (насичення), а не є
                # середнім одного тригера: один слабкий сигнал → низька впевненість.
                final_confidence = 1.0 - math.exp(-win_score / self._CONFIDENCE_SCALE)
                final_reason = None
            else:
                fam_list = ", ".join(sorted(win_fams))
                final_reason = (f"Сигнал {win_dir} відхилено: лише одне джерело ({fam_list}); "
                                f"потрібен збіг ≥2 сімей або структурний тригер")
        elif active_triggers == 0 and block_reasons:
            final_reason = " | ".join(block_reasons)

        return {
            "signal": final_signal,
            "confidence": round(final_confidence, 3) if final_confidence > 0 else 0.0,
            "block_reason": final_reason,
            "market_state": market_state,
            "active_triggers": active_triggers,
            "counter_trend_penalty": round(counter_trend_penalty, 3),
            "confluence_families": sorted(win_fams) if final_signal != 'NEUTRAL' else [],
            "active_signals": fired,
            "support_price": last_row.get('FRS_sup_price'),
            "resistance_price": last_row.get('FRS_res_price')
        }

    #==============================
    # Main method
    #==============================

    def process(self) -> dict:
        "Єдиний метод, який запускає всі інші для отримання реального сигналу"

        self.df_processed = self._enrich_data()
        self.df_processed = self._apply_logic_triggers()
        
        return self._calculate_final_signal()
        