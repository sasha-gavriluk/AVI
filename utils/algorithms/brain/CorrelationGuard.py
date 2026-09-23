from utils.OtherUtils import _handle_error

#------------------------------
# Контроль корельованих позицій
#------------------------------

class CorrelationGuard:
    "Ріже розмір нової позиції, якщо вже є відкриті в тому ж напрямку"

    #------------------------------
    # Коригування розміру
    #------------------------------

    @_handle_error
    def adjust_size(self, new_asset: str, new_direction: str, active_positions: list) -> float:
        """
        Повертає множник розміру. Крипто-активи вважаємо скорельованими між собою:
        три лонги на різних монетах — це фактично одна ставка потрійного розміру.

        :return: множник 1.0, 0.5, 0.25 ... — по разу за кожну позицію в той самий бік
        """
        multiplier = 1.0

        for pos in active_positions:
            if pos.get('direction') == new_direction:
                multiplier *= 0.5

        return multiplier
