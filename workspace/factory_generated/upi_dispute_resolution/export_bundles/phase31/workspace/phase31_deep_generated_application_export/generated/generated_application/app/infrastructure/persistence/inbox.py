from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone


class SqliteInbox:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def process_once(self, message_id: str, handler: Callable[[], None]) -> bool:
        try:
            self.connection.execute(
                "insert into inbox(message_id, consumed_at_utc) values (?, ?)",
                (message_id, datetime.now(timezone.utc).isoformat()),
            )
        except sqlite3.IntegrityError:
            return False
        try:
            handler()
        except Exception:
            self.connection.execute("delete from inbox where message_id = ?", (message_id,))
            raise
        return True
