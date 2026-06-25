from __future__ import annotations

import signal
import threading
from dataclasses import dataclass

from .commands import load_commands
from .config import load_settings
from .feishu import FeishuClient
from .logging_utils import get_logger, setup_logging
from .long_connection import LongConnectionClient
from .router import Router
from .scheduler import Scheduler
from .server import SecretaryServer
from .store import Store


logger = get_logger(__name__)


@dataclass
class App:
    store: Store
    server: SecretaryServer | None
    long_connection: LongConnectionClient | None
    scheduler: Scheduler
    stop_event: threading.Event

    def run(self) -> None:
        if self.long_connection is not None:
            self.long_connection.validate()

        self.scheduler.start()
        logger.info("Scheduler started")
        if self.server is not None:
            logger.info(
                "Secretary listening on http://%s:%s",
                self.server.settings.host,
                self.server.settings.port,
            )
            logger.info("Feishu webhook endpoint: /feishu/events")
            self.server.serve_forever()
            return

        if self.long_connection is None:
            raise RuntimeError("No Feishu event receiver configured.")
        logger.info("Starting Feishu long connection mode")
        logger.info("Send /help to the bot in Feishu after the app is installed")
        self.long_connection.start()

    def close(self) -> None:
        self.stop_event.set()
        if self.server is not None:
            self.server.close()
        self.store.close()


def build_app() -> App:
    settings = load_settings()
    setup_logging(settings.log_file)
    logger.info(
        "Loaded settings mode=%s database=%s log_file=%s",
        settings.feishu_event_mode,
        settings.database_path,
        settings.log_file,
    )
    store = Store(settings.database_path)
    router = Router()
    load_commands(router)
    feishu = FeishuClient(settings)
    stop_event = threading.Event()
    scheduler = Scheduler(settings, store, feishu, stop_event)
    mode = settings.feishu_event_mode.lower()
    if mode in ("webhook", "http"):
        server = SecretaryServer(settings, store, router, feishu)
        return App(
            store=store,
            server=server,
            long_connection=None,
            scheduler=scheduler,
            stop_event=stop_event,
        )
    if mode in ("long_connection", "ws", "websocket"):
        long_connection = LongConnectionClient(settings, store, router, feishu)
        return App(
            store=store,
            server=None,
            long_connection=long_connection,
            scheduler=scheduler,
            stop_event=stop_event,
        )
    raise ValueError(
        "SECRETARY_FEISHU_EVENT_MODE must be long_connection or webhook."
    )


def main() -> None:
    app = build_app()
    try:
        if app.server is not None:
            def request_stop(signum: int, frame: object) -> None:
                app.stop_event.set()
                if app.server is not None:
                    threading.Thread(target=app.server.shutdown, daemon=True).start()

            signal.signal(signal.SIGINT, request_stop)
            signal.signal(signal.SIGTERM, request_stop)
        app.run()
    except RuntimeError as exc:
        print(f"Startup error: {exc}")
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        print("Secretary stopped.")
    finally:
        app.close()
