from core.services.trading_service import TradingService
from PyQt6.QtCore import QObject

#==================================
# LiveTradingLogic
#==================================
class LiveTradingLogic(QObject):
    # ----------------------------------
    # __init__, ініціалізація логіки LiveTrading
    # ----------------------------------
    # Параметри:
    # copilot_logic: екземпляр CopilotLogic
    def __init__(self, copilot_logic):
        super().__init__()
        self.copilot = copilot_logic.trading_copilot
        self.service = TradingService()

    # ----------------------------------
    # start_trading, запуск торгівлі
    # ----------------------------------
    # Параметри:
    # mode (str): Режим торгівлі (demo, paper, real, signal)
    def start_trading(self, mode: str):
        self.service.set_mode(mode)
        self.service.start()

    # ----------------------------------
    # stop_trading, зупинка торгівлі
    # ----------------------------------
    # Параметри: немає
    def stop_trading(self):
        self.service.stop()
