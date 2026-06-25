from __future__ import annotations

import threading

from .config import Settings
from .feishu import FeishuClient
from .store import Store
from .timeutils import format_utc, utc_now


class Scheduler:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        feishu: FeishuClient,
        stop_event: threading.Event,
    ):
        self.settings = settings
        self.store = store
        self.feishu = feishu
        self.stop_event = stop_event
        self._thread = threading.Thread(target=self._run, name="scheduler", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        self.tick()
        while not self.stop_event.wait(self.settings.scheduler_poll_seconds):
            self.tick()

    def tick(self) -> None:
        due = self.store.due_schedules(format_utc(utc_now()))
        for schedule in due:
            text = (
                f"提醒 #{schedule['id']}\n"
                f"UTC: {schedule['due_at_utc']}\n"
                f"{schedule['message']}"
            )
            try:
                self.feishu.send_text(
                    schedule["receive_id_type"],
                    schedule["receive_id"],
                    text,
                )
            except Exception as exc:
                self.store.record_schedule_error(schedule["id"], str(exc))
                continue
            self.store.mark_schedule_sent(schedule["id"])

