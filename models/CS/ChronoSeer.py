import os
import json
import joblib
import numpy as np
import pandas as pd
import torch

from .ArchitectureNN import ChronoSeer as ChronoSeerNet
from utils.OtherUtils import _handle_error

#==============================
# ChronoSeer — обгортка над мережею
#==============================
#
# Мережа дивиться на вікно з 1000 свічок і каже, куди піде ціна на кожному
# з горизонтів, та наскільки вона в цьому впевнена.
#
# ЩО ВАЖЛИВО ЗНАТИ ПРО ЦЮ ОБГОРТКУ:
#
# 1. Порядок фічей священний. Мережа читає колонки за НОМЕРОМ, а не за назвою.
#    Якщо порядок зсунеться, помилки не буде — будуть упевнені випадкові рішення.
#    Тому порядок береться з паспорта (inputs.json), а не складається на місці.
#
# 2. Нормалізатор мусить бути ТОЙ САМИЙ, що при навчанні. Він лежить поруч
#    із вагами й прив'язаний до дати: вчився на свічках до 2026-06-07 01:45.
#
# 3. Тейк і стоп мережа НЕ рахує. Її голови тейка й стопа не навчені, і всі
#    виміряні результати отримані з правила ATR × 1.5 при R:R = 2. Правило тут
#    же й реалізоване, щоб жива торгівля робила рівно те, що перевірялось.
#==============================


class ChronoSeer:
    "Готує вікно, проганяє через мережу й повертає вердикт по кожному горизонту"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    ROOT = os.path.dirname(__file__)
    D_MODEL = 256
    N_HEAD = 8

    # Правило рівнів. Мусить збігатися з тим, на чому міряли результат.
    ATR_STOP_MULT = 1.5
    RISK_REWARD = 2.0

    SCALED_CLIP = 10.0

    # Мережу й паспорт вантажимо ОДИН раз на весь клас
    _net = None
    _passport = None
    _scalers = {}

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, device: str = None):
        """
        :param device: 'cuda' або 'cpu'. None — обрати автоматично
        """
        self.device = torch.device(device or ('cuda' if torch.cuda.is_available() else 'cpu'))

        if ChronoSeer._passport is None:
            with open(os.path.join(self.ROOT, 'inputs.json'), encoding='utf-8') as f:
                ChronoSeer._passport = json.load(f)

        if ChronoSeer._net is None:
            ChronoSeer._net = self._load_net()

        self.passport = ChronoSeer._passport
        self.net = ChronoSeer._net

    #------------------------------
    # Завантаження мережі
    #------------------------------

    def _load_net(self):
        "Створює мережу за паспортом і ставить у неї ваги"
        p = ChronoSeer._passport
        net = ChronoSeerNet(
            input_dim=p['input_dim'],
            d_model=self.D_MODEL,
            nhead=self.N_HEAD,
            num_classes=len(p['classes']),
            horizons=p['horizons']
        ).to(self.device)

        weights = torch.load(os.path.join(self.ROOT, p['weights']),
                             map_location=self.device, weights_only=True)
        net.load_state_dict(weights)
        net.eval()
        return net

    #------------------------------
    # Нормалізатор пари
    #------------------------------

    def _scaler(self, pair: str):
        """
        Дільники для цієї монети. Кешуємо, бо файл читається з диска.

        :param pair: напр. 'SOLUSDT' — без суфікса таймфрейму
        """
        key = f"{pair}_Base"
        if key not in ChronoSeer._scalers:
            path = os.path.join(self.ROOT, 'Scalers', f"{key}.joblib")
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Немає нормалізатора для {pair}: {path}. "
                    f"Без нього мережа отримає інший масштаб, ніж при навчанні."
                )
            ChronoSeer._scalers[key] = joblib.load(path)
        return ChronoSeer._scalers[key]

    #------------------------------
    # Звірка колонок
    #------------------------------

    @_handle_error
    def check_columns(self, df: pd.DataFrame) -> None:
        """
        Кричить, якщо датафрейм не містить рівно тих фічей, що чекає мережа.

        Це найдешевша страховка від найдорожчої помилки: коли кількість
        збігається, а порядок ні — програма мовчки торгує навмання.
        """
        needed = self.passport['meta_features']
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ValueError(f"Бракує {len(missing)} фічей, напр.: {missing[:5]}")

    #------------------------------
    # Побудова вікна для мережі
    #------------------------------

    @_handle_error
    def build_window(self, df: pd.DataFrame, pair: str) -> torch.Tensor:
        """
        Перетворює останні 1000 свічок на вхід мережі.

        Ціни нормалізуються ВСЕРЕДИНІ вікна (відносно останнього закриття),
        обсяг — z-оцінкою в тому ж вікні. Мета-фічі ділить збережений
        нормалізатор. Так само, як це робив датасет при навчанні.

        :return: тензор [1, вікно, input_dim]
        """
        window = self.passport['window']
        if len(df) < window:
            raise ValueError(f"Замало свічок: {len(df)}, потрібно {window}")

        self.check_columns(df)
        d = df.iloc[-window:]

        # 1. Ціни й обсяг — локально у вікні
        ohlcv = d[['open', 'high', 'low', 'close', 'volume']].values.astype(np.float32)
        last_close = ohlcv[-1, 3]
        norm_prices = (ohlcv[:, 0:4] / last_close) - 1.0
        volume = ohlcv[:, 4]
        norm_vol = ((volume - volume.mean()) / (volume.std() + 1e-8)).reshape(-1, 1)

        # 2. Мета-фічі: масштабуємо ті, що масштабувались при навчанні
        meta = d[self.passport['meta_features']].copy()
        saved = self._scaler(pair)
        cols = saved['cols']
        meta[cols] = saved['scaler'].transform(meta[cols])
        meta[cols] = meta[cols].clip(-self.SCALED_CLIP, self.SCALED_CLIP)

        x = np.hstack([norm_prices, norm_vol, meta.values.astype(np.float32)])
        return torch.tensor(x, dtype=torch.float32).unsqueeze(0).to(self.device)

    #------------------------------
    # Рівні за правилом
    #------------------------------

    @_handle_error
    def levels(self, entry_price: float, atr_pct: float, direction: str) -> dict:
        """
        Стоп і ціль за правилом ATR. Мережа їх НЕ рахує — її голови не навчені.

        :param atr_pct: ATR у відсоткових пунктах (колонка ATR_14)
        """
        stop_pct = max(atr_pct * self.ATR_STOP_MULT, 1e-6)
        take_pct = stop_pct * self.RISK_REWARD

        if direction == 'BUY':
            stop = entry_price * (1 - stop_pct / 100.0)
            target = entry_price * (1 + take_pct / 100.0)
        else:
            stop = entry_price * (1 + stop_pct / 100.0)
            target = entry_price * (1 - take_pct / 100.0)

        return {'stop_price': stop, 'target_price': target,
                'stop_pct': stop_pct, 'target_pct': take_pct}

    #------------------------------
    # Головний метод: вердикт мережі
    #------------------------------

    @_handle_error
    def process(self, df: pd.DataFrame, pair: str) -> dict:
        """
        Дивиться на останню свічку датафрейму й каже, що робити.

        :param df: готові дані з УСІМА фічами (після збірки й склейки таймфреймів)
        :param pair: 'SOLUSDT' — потрібна, щоб узяти правильний нормалізатор
        :return: вердикт по кожному горизонту
        """
        x = self.build_window(df, pair)

        with torch.no_grad():
            logits, _, _, _, feature_weights = self.net(x)
            probs = torch.softmax(logits.float(), dim=-1)[0]

        last = df.iloc[-1]
        price = float(last['close'])
        atr = float(last.get('ATR_14', 0.0))

        by_horizon = {}
        for i, horizon in enumerate(self.passport['horizons']):
            p = probs[i]
            idx = int(torch.argmax(p).item())
            direction = self.passport['classes'][idx]
            confidence = float(p[idx].item())
            by_horizon[horizon] = {
                'direction': direction,
                'confidence': confidence,
                'p_buy': float(p[0].item()),
                'p_sell': float(p[1].item()),
                **self.levels(price, atr, direction)
            }

        return {'price': price, 'atr_pct': atr, 'horizons': by_horizon}
