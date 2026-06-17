import os
import sys
import shutil
import platform

class PathManager:
    """
    Керує всіма шляхами в програмі.
    Розрізняє роботу з вихідного коду та зсередини зкомпільованого .exe.
    Створює користувацьку папку при першому запуску.
    """
    
    # Назва нашої папки в системі користувача
    APP_NAME = "AviTradingSystem"
    
    @classmethod
    def get_app_dir(cls):
        """
        Повертає папку, де лежить КОД або ЗКОМПІЛЬОВАНІ файли.
        """
        # getattr(sys, 'frozen', False) повертає True, якщо це зкомпільована програма (через PyInstaller)
        if getattr(sys, 'frozen', False):
            # sys._MEIPASS - це спеціальна тимчасова папка, куди PyInstaller розпаковує файли
            return sys._MEIPASS
        else:
            # Якщо запускаємо з main.py, то повертаємо папку Code
            return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            
    @classmethod
    def get_user_data_dir(cls):
        """
        Повертає захищеню папку користувача (AppData на Windows, .config на Linux).
        Саме тут будуть жити main.duckdb, settings.json та стратегії користувача.
        """
        system = platform.system()
        if system == 'Windows':
            base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
        elif system == 'Darwin': # MacOS
            base_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
        else: # Linux
            base_dir = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
            
        app_data_dir = os.path.join(base_dir, cls.APP_NAME)
        
        # Перевіряємо чи папка існує, якщо ні - це ПЕРШИЙ запуск програми
        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)
            cls._initialize_user_data(app_data_dir)
            
        return app_data_dir

    @classmethod
    def _initialize_user_data(cls, user_data_dir):
        """
        Копіює стартові/дефолтні файли з папки з програмою в папку користувача.
        Виконується ТІЛЬКИ ОДИН РАЗ при першому запуску програми.
        """
        import json
        
        target_data_dir = os.path.join(user_data_dir, 'data')
        config_dir = os.path.join(target_data_dir, 'config')
        strategies_dir = os.path.join(target_data_dir, 'strategies')
        predictions_dir = os.path.join(target_data_dir, 'predictions')
        
        # Створюємо чисті папки
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(strategies_dir, exist_ok=True)
        os.makedirs(predictions_dir, exist_ok=True)
        
        # Створюємо rules.json та strategy_meta.json
        from utils.create_insurance import Insurance
        Insurance.ensure_files_exist(user_data_dir)
        
        # Створюємо дефолтний порожній/базовий файл налаштувань
        default_settings = {
            "trading_mode": {"type": "Standard", "bo_payout_percent": 80.0, "bo_bet_size": 10.0, "bo_expiration_bars": 1, "bo_fixed_time_enabled": False, "bo_fixed_time_minutes": 60},
            "risk_management": {"stop_loss_percent": 1.5, "max_drawdown_session": 5.0, "daily_loss_limit": 100.0},
            "copilot": {"half_life_days": 90, "min_score_for_best": 0.6, "update_threshold_weight": 15.0, "active_strategies": []},
            "downloader": {"massive_free_tier": True, "massive_api_delay_minutes": 15},
            "notifications": {"telegram_enabled": False}
        }
        with open(os.path.join(config_dir, 'settings.json'), 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=4)
            
        # Створюємо порожній файл свят
        with open(os.path.join(config_dir, 'market_holidays.json'), 'w', encoding='utf-8') as f:
            json.dump({"Forex_Weekends": {"description": "Standard Forex weekend close"}}, f, indent=4)
            
        # Створюємо базову навчальну стратегію
        demo_strategy_code = '''from utils.rules_engine import Indicator, Pattern, Algorithm, Strategy

TARGET_ASSETS = ["EURUSD", "GBPUSD"]
TARGET_TIMEFRAMES = ["15m", "1h"]

macd = Indicator("MACD", "macd", {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9})
rsi = Indicator("RSI", "rsi", {"timeperiod": 14})

buy_algo = Algorithm(
    "MACD_CrossUp_RSI",
    conditions=[
        ("MACD.macd", ">", "MACD.macdsignal"),
        ("RSI.rsi", "<", 70)
    ]
)

sell_algo = Algorithm(
    "MACD_CrossDown_RSI",
    conditions=[
        ("MACD.macd", "<", "MACD.macdsignal"),
        ("RSI.rsi", ">", 30)
    ]
)

strategy = Strategy(
    name="Basic_MACD_RSI",
    description="Базова навчальна стратегія. Відкриває угоди на перетині MACD з фільтром RSI.",
    algorithms=[buy_algo, sell_algo],
    direction="BOTH"
)
'''
        with open(os.path.join(strategies_dir, 'demo_strategy.py'), 'w', encoding='utf-8') as f:
            f.write(demo_strategy_code)
            
        print(f"📦 Ініціалізація даних: створено АБСОЛЮТНО ЧИСТЕ середовище з базовою стратегією в {user_data_dir}")

    # ==========================================
    # Конкретні шляхи до файлів (використовувати замість хардкоду)
    # ==========================================

    @classmethod
    def get_db_path(cls):
        """Шлях до main.duckdb"""
        return os.path.join(cls.get_user_data_dir(), "main.duckdb")
        
    @classmethod
    def get_settings_path(cls):
        """Шлях до settings.json"""
        return os.path.join(cls.get_user_data_dir(), "data", "config", "settings.json")
        
    @classmethod
    def get_holidays_path(cls):
        """Шлях до market_holidays.json"""
        return os.path.join(cls.get_user_data_dir(), "data", "config", "market_holidays.json")
        
    @classmethod
    def get_strategies_dir(cls):
        """Шлях до папки з пітонівськими стратегіями"""
        return os.path.join(cls.get_user_data_dir(), "data", "strategies")

    @classmethod
    def get_strategy_meta_path(cls):
        """Шлях до strategy_meta.json"""
        return os.path.join(cls.get_user_data_dir(), "data", "config", "strategy_meta.json")
