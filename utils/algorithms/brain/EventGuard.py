from utils.OtherUtils import _handle_error

#------------------------------
# Захист від новин
#------------------------------

class EventGuard:
    "Зупиняє торгівлю навколо важливих макро-подій"

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, calendar=None):
        """
        :param calendar: NewsCalendar. None — створити свій.
                         Передати None явно неможливо: без календаря вартовий
                         пропускав би все, а це найгірший із можливих станів —
                         виглядає як робота, а насправді захисту немає.
        """
        if calendar is None:
            from utils.News.NewsCalendar import NewsCalendar
            calendar = NewsCalendar()
        self.calendar = calendar

    #------------------------------
    # Перевірка безпеки часу
    #------------------------------

    @_handle_error
    def is_safe_to_trade(self, current_time, news_calendar=None) -> bool:
        """
        Чи можна торгувати в цей момент.

        :param news_calendar: перебити календар ззовні (для тестів і бектесту)
        """
        calendar = news_calendar or self.calendar
        if calendar is None or current_time is None:
            return True
        return not calendar.has_high_impact_event_soon(current_time)

    #------------------------------
    # Чому саме заборонено
    #------------------------------

    @_handle_error
    def reason(self, current_time, news_calendar=None) -> str:
        "Текст для журналу: яка подія й за скільки хвилин"
        calendar = news_calendar or self.calendar
        event = calendar.next_event(current_time) if calendar else None
        if not event:
            return ''
        name, when, minutes = event
        word = 'через' if minutes >= 0 else 'було'
        return f"{name} {word} {abs(minutes):.0f} хв ({when:%d.%m %H:%M} UTC)"
