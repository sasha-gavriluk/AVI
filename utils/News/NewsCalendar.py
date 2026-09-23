import datetime

from utils.OtherUtils import _handle_error

#==============================
# Календар макро-подій
#==============================
#
# ДВІ РІЗНІ ЗАДАЧІ, і плутати їх не можна.
#
# Щоб зупинитись ЗА кілька свічок ДО новини, потрібен РОЗКЛАД — знання, що
# подія буде. Стрічка новин цього не дає за побудовою: вона розповідає про
# минуле. Але найважливіші події мають опублікований розклад на місяці вперед,
# і цього вистачає, щоб закрити левову частку того, що рухає ринок.
#
# Щоб зупинитись ПІСЛЯ несподіванки, потрібна СТРІЧКА. Це інший модуль.
#
# Тут — розклад. Події описані ПРАВИЛОМ повторення, а не списком дат: NFP
# виходить у першу п'ятницю місяця, CPI приблизно в середині. Так таблиця
# не протухає щомісяця, а оновлювати треба лише засідання ФРС — їх вісім
# на рік і вони публікуються наперед.
#==============================


class NewsCalendar:
    "Знає, коли будуть важливі макро-події, і чи ми зараз поруч із ними"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    # Скільки свічок мовчати до й після події. За домовленістю 02.09.2026:
    # рівно 20 свічок з кожного боку, разом 40. Було по 15.
    BARS_BEFORE = 20
    BARS_AFTER = 20
    MINUTES_PER_BAR = 15

    # Засідання ФРС — єдине, що доводиться вписувати руками. Публікуються
    # на рік уперед, оновлювати раз на квартал. Час у UTC.
    FOMC_MEETINGS = [
        # (рік, місяць, день, година UTC)
        (2026, 9, 17, 18), (2026, 11, 5, 19), (2026, 12, 17, 19),
    ]

    # Регулярні події: (назва, правило, година UTC)
    RECURRING = [
        ('NFP', 'first_friday', 12),      # зайнятість у США, 8:30 ET
        ('CPI', 'mid_month', 12),    # інфляція, приблизно 10-15 число
    ]

    #------------------------------
    # Правила повторення
    #------------------------------

    @staticmethod
    def _first_friday(year: int, month: int) -> int:
        "День першої п'ятниці місяця"
        d = datetime.date(year, month, 1)
        shift = (4 - d.weekday()) % 7      # 4 = п'ятниця
        return 1 + shift

    @staticmethod
    def _mid_month(year: int, month: int) -> int:
        "CPI виходить близько 13-го. Точну дату дає лише офіційний розклад"
        return 13

    #------------------------------
    # Події навколо дати
    #------------------------------

    @_handle_error
    def events_of_month(self, year: int, month: int) -> list:
        "Усі відомі події цього місяця як мітки часу UTC"
        events = []

        for name, rule, hour in self.RECURRING:
            day = (self._first_friday(year, month) if rule == 'first_friday'
                   else self._mid_month(year, month))
            when = datetime.datetime(year, month, day, hour,
                                     tzinfo=datetime.timezone.utc)
            events.append((name, when))

        for (y, mo, dd, hh) in self.FOMC_MEETINGS:
            if (y, mo) == (year, month):
                events.append(('FOMC', datetime.datetime(y, mo, dd, hh,
                                                         tzinfo=datetime.timezone.utc)))
        return events

    #------------------------------
    # Головна перевірка
    #------------------------------

    @_handle_error
    def has_high_impact_event_soon(self, current_time, window_minutes: int = None) -> bool:
        """
        Чи ми в забороненому вікні навколо важливої події.

        :param current_time: мітка часу в мілісекундах або datetime
        :param window_minutes: перебити вікно вручну. None — узяти зі сталих
        """
        event = self.next_event(current_time, window_minutes)
        return event is not None

    @_handle_error
    def next_event(self, current_time, window_minutes: int = None):
        """
        Повертає подію, у чиє вікно ми потрапили, або None.

        :return: (назва, коли, хвилин_до) або None
        """
        now = self._to_datetime(current_time)
        if now is None:
            return None

        before = window_minutes or self.BARS_BEFORE * self.MINUTES_PER_BAR
        after = window_minutes or self.BARS_AFTER * self.MINUTES_PER_BAR

        # Дивимось сусідні місяці — подія може бути на межі місяця
        events = []
        for shift in (-1, 0, 1):
            month = now.month + shift
            year = now.year
            if month < 1:
                month += 12
                year -= 1
            elif month > 12:
                month -= 12
                year += 1
            events.extend(self.events_of_month(year, month))

        for name, when in events:
            diff = (when - now).total_seconds() / 60.0
            if -after <= diff <= before:
                return (name, when, diff)
        return None

    #------------------------------
    # Розбір часу
    #------------------------------

    @staticmethod
    def _to_datetime(value):
        "Приймає мілісекунди, секунди або datetime"
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            return value if value.tzinfo else value.replace(
                tzinfo=datetime.timezone.utc)
        try:
            ts = float(value)
        except (TypeError, ValueError):
            return None
        if ts > 1e11:
            ts /= 1000.0
        return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
