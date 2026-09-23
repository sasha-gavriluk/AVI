import datetime

import pandas as pd

from utils.DataBaseManager import DataBaseManager
from utils.OtherUtils import _handle_error

#==============================
# Журнал угод
#==============================
#
# Кожна угода записується в базу ОДРАЗУ: рядок з'являється в момент відкриття
# і дописується в момент закриття. Не в кінці сесії, не пачкою — миттєво.
#
# НАВІЩО. Без журналу після дня торгівлі лишається тільки підсумковий баланс,
# і на питання «чому мережа зайшла ось тут» відповісти нічим. А з журналом
# видно все: якою була впевненість, який стоп поставило правило, скільки
# свічок трималась позиція, чим закінчилась і що стало з балансом.
#
# Це той самий журнал рішень, який у лабораторії робив бенчмарк
# (decisions_last_run.csv) — тільки тепер для живої торгівлі й у базі.
#==============================


class TradeJournal:
    "Пише кожну угоду в базу: рядок при відкритті, доповнення при закритті"

    #------------------------------
    # Constants (Можна змінювати)
    #------------------------------

    TABLE = 'trades'

    SCHEMA = {
        'id': 'VARCHAR',
        'pair': 'VARCHAR',
        'direction': 'VARCHAR',
        'status': 'VARCHAR',            # open / closed
        'confidence': 'DOUBLE',
        'horizon': 'INTEGER',
        'entry_price': 'DOUBLE',
        'stop_price': 'DOUBLE',
        'target_price': 'DOUBLE',
        'liquidation_price': 'DOUBLE',
        'position_size': 'DOUBLE',
        'margin': 'DOUBLE',
        'leverage': 'INTEGER',
        'opened_at': 'BIGINT',
        'closed_at': 'BIGINT',
        'exit_price': 'DOUBLE',
        'exit_reason': 'VARCHAR',
        'bars_held': 'INTEGER',
        'pnl': 'DOUBLE',
        'balance_after': 'DOUBLE',
        'model': 'VARCHAR',             # яка модель ухвалила рішення
        'mode': 'VARCHAR',              # paper / live
        'written_at': 'VARCHAR',
    }

    #------------------------------
    # Ініціалізація класу
    #------------------------------

    def __init__(self, db: DataBaseManager = None, model: str = 'ChronoSeer',
                 mode: str = 'paper'):
        """
        :param db: менеджер бази. None — створити свій
        :param model: підпис під рішенням. Знадобиться, коли моделей стане кілька
        :param mode: 'paper' або 'live'

        НАВІЩО РЕЖИМ. Паперові прогони пишуться в ту саму таблицю, що й реальні
        угоди. Без позначки історія рахунку рахувалась би разом із тестами —
        і будь-який підсумок по грошах був би вигадкою.
        """
        self.db = db or DataBaseManager()
        self.model = model
        self.mode = mode
        self._ready = False

    #------------------------------
    # Таблиця
    #------------------------------

    def _ensure_table(self) -> None:
        "Створює таблицю при першому зверненні"
        if self._ready:
            return
        if not self.db.table_exists(self.TABLE):
            schema_sql = ', '.join(f'"{col}" {typ}' for col, typ in self.SCHEMA.items())
            self.db.create_table(self.TABLE, schema_sql)
            self.db.create_index(self.TABLE, 'pair')
        else:
            self._add_missing_columns()
        self._ready = True

    def _add_missing_columns(self) -> None:
        """
        Дописує колонки, яких у старій таблиці ще немає.

        Таблиця угод переживе не одну зміну схеми, а стирати історію угод
        заради нової колонки не можна. Тому доганяємо схему на місці.
        """
        cursor = self.db._get_conn().cursor()
        have = {row[0] for row in cursor.execute(
            f'SELECT column_name FROM information_schema.columns '
            f"WHERE table_name = '{self.TABLE}'").fetchall()}
        for col, typ in self.SCHEMA.items():
            if col not in have:
                cursor.execute(f'ALTER TABLE {self.TABLE} ADD COLUMN "{col}" {typ}')
                print(f'[TradeJournal] Додано колонку {col}')

    def _table_columns(self) -> list:
        """
        Порядок стовпців, який СПРАВДІ в таблиці, а не той, що в SCHEMA.

        Це не педантизм. insert_data_from_pandas_append кладе рядок ПОЗИЦІЙНО,
        а ALTER TABLE дописує нову колонку в самий кінець — куди б її не
        поставили в SCHEMA. Розійшлись один раз: колонка mode отримала мітку
        часу з written_at, бо в схемі стояла перед нею, а в таблиці — після.
        """
        rows = self.db._get_conn().cursor().execute(
            f'SELECT column_name FROM information_schema.columns '
            f"WHERE table_name = '{self.TABLE}' ORDER BY ordinal_position").fetchall()
        return [r[0] for r in rows]

    def _sql(self, query: str) -> None:
        "Виконує запит. Оновлення рядка інакше не зробити"
        self.db._get_conn().cursor().execute(query)

    #------------------------------
    # Запис при відкритті
    #------------------------------

    @_handle_error
    def on_open(self, trade: dict, horizon: int = None,
                leverage: int = None, balance: float = None) -> None:
        "Кладе рядок у базу в момент відкриття позиції"
        self._ensure_table()

        row = {
            'id': trade.get('id'),
            'pair': trade.get('pair'),
            'direction': trade.get('direction'),
            'status': 'open',
            'confidence': float(trade.get('confidence') or 0.0),
            'horizon': int(horizon or 0),
            'entry_price': float(trade.get('entry_price') or 0.0),
            'stop_price': float(trade.get('stop_price') or 0.0),
            'target_price': float(trade.get('target_price') or 0.0),
            'liquidation_price': float(trade.get('liquidation_price') or 0.0),
            'position_size': float(trade.get('position_size') or 0.0),
            'margin': float(trade.get('margin') or 0.0),
            'leverage': int(leverage or 0),
            'opened_at': int(trade.get('opened_at') or 0),
            'closed_at': 0,
            'exit_price': 0.0,
            'exit_reason': '',
            'bars_held': 0,
            'pnl': 0.0,
            'balance_after': float(balance or 0.0),
            'model': self.model,
            'mode': self.mode,
            'written_at': datetime.datetime.now().isoformat(timespec='seconds'),
        }
        frame = pd.DataFrame([row])
        order = self._table_columns()
        if order:
            frame = frame.reindex(columns=order)
        self.db.insert_data_from_pandas_append(self.TABLE, frame)

    #------------------------------
    # Дозапис при закритті
    #------------------------------

    @_handle_error
    def on_close(self, trade: dict, exit_price: float, reason: str,
                 pnl: float, balance: float, closed_at=None) -> None:
        "Доповнює вже наявний рядок підсумками угоди"
        self._ensure_table()

        # Одинарні лапки в причині зламали б запит — прибираємо
        reason = str(reason).replace("'", "")
        self._sql(f"""
            UPDATE {self.TABLE} SET
                status = 'closed',
                closed_at = {int(closed_at or 0)},
                exit_price = {float(exit_price)},
                exit_reason = '{reason}',
                bars_held = {int(trade.get('bars_held') or 0)},
                pnl = {float(pnl)},
                balance_after = {float(balance)}
            WHERE id = '{trade.get('id')}'
        """)

    #------------------------------
    # Читання
    #------------------------------

    @_handle_error
    def open_trades(self) -> pd.DataFrame:
        "Угоди, які досі не закриті. Потрібні при перезапуску програми"
        self._ensure_table()
        return self.db._get_conn().cursor().execute(
            f"SELECT * FROM {self.TABLE} WHERE status = 'open' "
            f"AND mode = '{self.mode}' ORDER BY opened_at"
        ).fetchdf()

    @_handle_error
    def summary(self) -> dict:
        "Коротка статистика по закритих угодах"
        self._ensure_table()
        r = self.db._get_conn().cursor().execute(f"""
            SELECT COUNT(*) AS trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winners,
                   SUM(pnl) AS total_pnl,
                   AVG(CASE WHEN pnl > 0 THEN pnl END) AS avg_win,
                   AVG(CASE WHEN pnl <= 0 THEN pnl END) AS avg_loss,
                   AVG(bars_held) AS avg_bars
            FROM {self.TABLE} WHERE status = 'closed' AND mode = '{self.mode}'
        """).fetchdf()
        return r.iloc[0].to_dict() if not r.empty else {}
