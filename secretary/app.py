from __future__ import annotations

import signal
import threading
from dataclasses import dataclass

from .commands import load_commands
from .config import load_settings
from .feishu import FeishuClient
from .router import Router
from .scheduler import Scheduler
from .server import SecretaryServer
from .store import Store


@dataclass
class App:
    server: SecretaryServer
    scheduler: Scheduler
    stop_event: threading.Event


def build_app() -> App:
    settings = load_settings()
    store = Store(settings.database_path)
    router = Router()
    load_commands(router)
    feishu = FeishuClient(settings)
    stop_event = threading.Event()
    scheduler = Scheduler(settings, store, feishu, stop_event)
    server = SecretaryServer(settings, store, router, feishu)
    return App(server=server, scheduler=scheduler, stop_event=stop_event)


def main() -> None:
    app = build_app()

    def request_stop(signum: int, frame: object) -> None:
        app.stop_event.set()
        app.server.shutdown()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    app.scheduler.start()
    print(
        f"Secretary listening on http://{app.server.settings.host}:"
        f"{app.server.settings.port}"
    )
    print("Feishu events endpoint: /feishu/events")
    app.server.serve_forever()

