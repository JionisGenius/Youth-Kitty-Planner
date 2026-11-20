from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

DEFAULT_DATABASE = Path(__file__).resolve().parents[2] / "data" / "ykp.sqlite3"


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Database:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self, *, write=False):
        conn = sqlite3.connect(self.path, timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8-sig")
            conn.executescript("PRAGMA journal_mode = WAL; BEGIN IMMEDIATE;\n" + schema)

