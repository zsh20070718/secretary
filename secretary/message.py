from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass

from .config import Settings
from .feishu import FeishuClient
from .logging_utils import get_logger
from .router import CommandContext, Router
from .search import SearchClient
from .store import Store


_AT_RE = re.compile(r"^\s*(<at\b[^>]*>.*?</at>\s*)+", re.IGNORECASE)
logger = get_logger(__name__)


@dataclass(frozen=True)
class IncomingMessage:
    event_id: str
    owner_id: str
    receive_id_type: str
    receive_id: str
    text: str


def parse_text_content(content: object) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return content.strip()
    elif isinstance(content, dict):
        data = content
    else:
        return str(content).strip()
    return str(data.get("text") or "").strip()


def strip_bot_mention(text: str) -> str:
    return _AT_RE.sub("", text).strip()


class MessageProcessor:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        router: Router,
        feishu: FeishuClient,
    ):
        self.settings = settings
        self.store = store
        self.router = router
        self.feishu = feishu
        self.search_client = SearchClient(settings)

    def process_async(self, incoming: IncomingMessage) -> None:
        threading.Thread(
            target=self.process,
            args=(incoming,),
            name=f"feishu-event-{incoming.event_id or 'unknown'}",
            daemon=True,
        ).start()

    def process(self, incoming: IncomingMessage) -> None:
        if not self.store.mark_event_seen(incoming.event_id):
            logger.info("Skipped duplicate event event_id=%s", incoming.event_id or "-")
            return
        logger.info(
            "Processing message event_id=%s receive_id_type=%s text=%r",
            incoming.event_id or "-",
            incoming.receive_id_type,
            incoming.text,
        )

        ctx = CommandContext(
            owner_id=incoming.owner_id,
            receive_id_type=incoming.receive_id_type,
            receive_id=incoming.receive_id,
            raw_text=incoming.text,
            store=self.store,
            settings=self.settings,
            search_client=self.search_client,
            feishu=self.feishu,
        )
        reply = self.router.dispatch(ctx, incoming.text)
        if not reply:
            logger.info("Command produced empty reply event_id=%s", incoming.event_id or "-")
            return
        try:
            self.feishu.send_text(incoming.receive_id_type, incoming.receive_id, reply)
        except Exception as exc:
            logger.exception("Failed to send Feishu reply: %s", exc)
            return
        logger.info("Sent Feishu reply event_id=%s", incoming.event_id or "-")
