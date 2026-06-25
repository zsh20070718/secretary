from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .timeutils import format_utc, utc_now


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL,
                    receive_id_type TEXT NOT NULL,
                    receive_id TEXT NOT NULL,
                    due_at_utc TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    created_at_utc TEXT NOT NULL,
                    sent_at_utc TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_schedules_due
                ON schedules(status, due_at_utc)
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at_utc TEXT NOT NULL,
                    done_at_utc TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_todos_owner
                ON todos(owner_id, status, id)
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY,
                    created_at_utc TEXT NOT NULL
                )
                """
            )

    def mark_event_seen(self, event_id: str) -> bool:
        if not event_id:
            return True
        with self._lock, self._conn:
            try:
                self._conn.execute(
                    "INSERT INTO processed_events(event_id, created_at_utc) VALUES (?, ?)",
                    (event_id, format_utc(utc_now())),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def add_schedule(
        self,
        owner_id: str,
        receive_id_type: str,
        receive_id: str,
        due_at_utc: str,
        message: str,
    ) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO schedules(
                    owner_id, receive_id_type, receive_id, due_at_utc,
                    message, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_id,
                    receive_id_type,
                    receive_id,
                    due_at_utc,
                    message,
                    format_utc(utc_now()),
                ),
            )
            return int(cursor.lastrowid)

    def list_schedules(self, owner_id: str, limit: int = 10) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self._conn.execute(
                    """
                    SELECT * FROM schedules
                    WHERE owner_id = ? AND status = 'pending'
                    ORDER BY due_at_utc ASC
                    LIMIT ?
                    """,
                    (owner_id, limit),
                )
            )

    def due_schedules(self, now_utc: str, limit: int = 20) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self._conn.execute(
                    """
                    SELECT * FROM schedules
                    WHERE status = 'pending' AND due_at_utc <= ?
                    ORDER BY due_at_utc ASC
                    LIMIT ?
                    """,
                    (now_utc, limit),
                )
            )

    def mark_schedule_sent(self, schedule_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE schedules
                SET status = 'sent', sent_at_utc = ?, last_error = ''
                WHERE id = ?
                """,
                (format_utc(utc_now()), schedule_id),
            )

    def record_schedule_error(self, schedule_id: int, error: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE schedules
                SET attempts = attempts + 1, last_error = ?
                WHERE id = ?
                """,
                (error[:500], schedule_id),
            )

    def cancel_schedule(self, owner_id: str, schedule_id: int) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                UPDATE schedules
                SET status = 'cancelled'
                WHERE owner_id = ? AND id = ? AND status = 'pending'
                """,
                (owner_id, schedule_id),
            )
            return cursor.rowcount > 0

    def add_todo(self, owner_id: str, title: str) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO todos(owner_id, title, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (owner_id, title, format_utc(utc_now())),
            )
            return int(cursor.lastrowid)

    def list_todos(self, owner_id: str, include_done: bool = False) -> list[sqlite3.Row]:
        sql = "SELECT * FROM todos WHERE owner_id = ?"
        params: list[object] = [owner_id]
        if not include_done:
            sql += " AND status = 'open'"
        sql += " ORDER BY id ASC"
        with self._lock:
            return list(self._conn.execute(sql, params))

    def finish_todo(self, owner_id: str, todo_id: int) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                UPDATE todos
                SET status = 'done', done_at_utc = ?
                WHERE owner_id = ? AND id = ? AND status = 'open'
                """,
                (format_utc(utc_now()), owner_id, todo_id),
            )
            return cursor.rowcount > 0

    def add_note(self, owner_id: str, content: str) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO notes(owner_id, content, created_at_utc)
                VALUES (?, ?, ?)
                """,
                (owner_id, content, format_utc(utc_now())),
            )
            return int(cursor.lastrowid)

    def list_notes(self, owner_id: str, limit: int = 10) -> list[sqlite3.Row]:
        with self._lock:
            return list(
                self._conn.execute(
                    """
                    SELECT * FROM notes
                    WHERE owner_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (owner_id, limit),
                )
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
