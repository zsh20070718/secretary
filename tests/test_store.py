from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from secretary.store import Store


class StoreTest(unittest.TestCase):
    def test_schedule_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp) / "secretary.sqlite3") as store:
                schedule_id = store.add_schedule(
                    owner_id="open_id_1",
                    receive_id_type="open_id",
                    receive_id="open_id_1",
                    due_at_utc="2026-06-25T06:30:00Z",
                    message="meeting",
                )

                self.assertEqual(schedule_id, 1)
                self.assertEqual(len(store.list_schedules("open_id_1")), 1)
                self.assertEqual(len(store.due_schedules("2026-06-25T06:30:00Z")), 1)
                self.assertTrue(store.cancel_schedule("open_id_1", schedule_id))
                self.assertEqual(len(store.list_schedules("open_id_1")), 0)

    def test_todo_and_note_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp) / "secretary.sqlite3") as store:
                todo_id = store.add_todo("user", "write tests")
                note_id = store.add_note("user", "passport in drawer")

                self.assertEqual(todo_id, 1)
                self.assertEqual(note_id, 1)
                self.assertEqual(store.list_todos("user")[0]["title"], "write tests")
                self.assertTrue(store.finish_todo("user", todo_id))
                self.assertEqual(store.list_todos("user"), [])
                self.assertEqual(store.list_notes("user")[0]["content"], "passport in drawer")

    def test_event_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp) / "secretary.sqlite3") as store:
                self.assertTrue(store.mark_event_seen("evt_1"))
                self.assertFalse(store.mark_event_seen("evt_1"))


if __name__ == "__main__":
    unittest.main()
