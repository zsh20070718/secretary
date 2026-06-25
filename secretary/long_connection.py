from __future__ import annotations

from typing import Any

from .config import Settings
from .feishu import FeishuClient
from .logging_utils import get_logger
from .message import (
    IncomingMessage,
    MessageProcessor,
    parse_text_content,
    strip_bot_mention,
)
from .router import Router
from .store import Store


logger = get_logger(__name__)


class LongConnectionClient:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        router: Router,
        feishu: FeishuClient,
    ):
        self.settings = settings
        self.processor = MessageProcessor(settings, store, router, feishu)

    def validate(self) -> None:
        if not self.settings.feishu_app_id or not self.settings.feishu_app_secret:
            raise RuntimeError(
                "Long connection mode requires FEISHU_APP_ID and FEISHU_APP_SECRET."
            )

    def start(self) -> None:
        self.validate()

        try:
            import lark_oapi as lark
            from lark_oapi.ws import Client as WsClient
        except ImportError as exc:
            raise RuntimeError(
                "Long connection mode requires lark-oapi. "
                "Run: python -m pip install -r requirements.txt"
            ) from exc

        handler = (
            lark.EventDispatcherHandler.builder(
                "",
                self.settings.feishu_verification_token,
            )
            .register_p2_im_message_receive_v1(self._handle_message)
            .register_p2_customized_event(
                "im.chat.access_event.bot_p2p_chat_entered_v1",
                self._ignore_event,
            )
            .register_p2_customized_event(
                "im.message.message_read_v1",
                self._ignore_event,
            )
            .build()
        )
        logger.info(
            "Starting Feishu websocket client app_id=%s domain=%s",
            self.settings.feishu_app_id,
            self.settings.feishu_base_url,
        )
        client = WsClient(
            self.settings.feishu_app_id,
            self.settings.feishu_app_secret,
            event_handler=handler,
            domain=self.settings.feishu_base_url,
        )
        client.start()

    def _handle_message(self, event: Any) -> None:
        event_id = getattr(getattr(event, "header", None), "event_id", "")
        logger.info("Received Feishu message event event_id=%s", event_id or "-")
        incoming = self._extract_message(event)
        if incoming is None:
            logger.info("Ignored Feishu event event_id=%s", event_id or "-")
            return
        self.processor.process_async(incoming)

    def _ignore_event(self, event: Any) -> None:
        event_type = getattr(event, "type", "") or getattr(
            getattr(event, "header", None),
            "event_type",
            "",
        )
        logger.info("Ignored Feishu auxiliary event type=%s", event_type or "-")

    def _extract_message(self, event: Any) -> IncomingMessage | None:
        header = getattr(event, "header", None)
        data = getattr(event, "event", None)
        if data is None:
            logger.info("Ignored event because event data is missing")
            return None

        sender = getattr(data, "sender", None)
        if sender is None or getattr(sender, "sender_type", "") == "app":
            logger.info("Ignored event because sender is missing or is app")
            return None

        sender_id = getattr(sender, "sender_id", None)
        owner_id = (
            getattr(sender_id, "open_id", "")
            or getattr(sender_id, "user_id", "")
            or getattr(sender_id, "union_id", "")
            or "unknown"
        )

        message = getattr(data, "message", None)
        if message is None or getattr(message, "message_type", "") != "text":
            logger.info(
                "Ignored event because message is missing or non-text type=%s",
                getattr(message, "message_type", None),
            )
            return None

        text = parse_text_content(getattr(message, "content", ""))
        if not text:
            logger.info("Ignored text message because parsed text is empty")
            return None

        chat_type = getattr(message, "chat_type", "") or ""
        chat_id = getattr(message, "chat_id", "") or ""
        if chat_type == "group" and chat_id:
            receive_id_type = "chat_id"
            receive_id = chat_id
        else:
            receive_id_type = "open_id"
            receive_id = owner_id

        incoming = IncomingMessage(
            event_id=getattr(header, "event_id", "") if header is not None else "",
            owner_id=owner_id,
            receive_id_type=receive_id_type,
            receive_id=receive_id,
            text=strip_bot_mention(text),
        )
        logger.info(
            "Parsed incoming message event_id=%s receive_id_type=%s chat_type=%s text=%r",
            incoming.event_id or "-",
            incoming.receive_id_type,
            chat_type or "-",
            incoming.text,
        )
        return incoming
