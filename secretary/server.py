from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .config import Settings
from .feishu import FeishuClient
from .message import (
    IncomingMessage,
    MessageProcessor,
    parse_text_content,
    strip_bot_mention,
)
from .router import Router
from .store import Store


class SecretaryServer:
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
        self.processor = MessageProcessor(settings, store, router, feishu)
        handler = self._handler_class()
        self._server = ThreadingHTTPServer((settings.host, settings.port), handler)

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()

    def close(self) -> None:
        self._server.server_close()

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        parent = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "SecretaryHTTP/0.1"

            def do_GET(self) -> None:
                path = urlparse(self.path).path
                if path == "/health":
                    self._send_text(200, "ok\n")
                    return
                self._send_json(404, {"error": "not found"})

            def do_POST(self) -> None:
                path = urlparse(self.path).path
                if path != "/feishu/events":
                    self._send_json(404, {"error": "not found"})
                    return
                try:
                    status, payload = parent.handle_feishu_event(self._read_json())
                except PermissionError as exc:
                    self._send_json(403, {"error": str(exc)})
                    return
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(status, payload)

            def log_message(self, fmt: str, *args: object) -> None:
                print(f"{self.address_string()} - {fmt % args}")

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1024 * 1024:
                    raise ValueError("request too large")
                raw = self.rfile.read(length)
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _send_text(self, status: int, text: str) -> None:
                raw = text.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        return Handler

    def handle_feishu_event(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if "encrypt" in body:
            raise ValueError("encrypted Feishu events are not supported yet")

        self._verify_token(body)

        if body.get("type") == "url_verification" or body.get("challenge"):
            return 200, {"challenge": body.get("challenge", "")}

        incoming = self._extract_message(body)
        if incoming is None:
            return 200, {"code": 0}
        self.processor.process_async(incoming)
        return 200, {"code": 0}

    def _verify_token(self, body: dict[str, Any]) -> None:
        expected = self.settings.feishu_verification_token
        if not expected:
            return
        header = body.get("header") or {}
        actual = header.get("token") or body.get("token") or ""
        if actual != expected:
            raise PermissionError("invalid Feishu verification token")

    def _extract_message(self, body: dict[str, Any]) -> IncomingMessage | None:
        header = body.get("header") or {}
        event = body.get("event") or {}
        event_type = header.get("event_type") or event.get("type") or ""

        if event_type == "im.message.receive_v1":
            sender = event.get("sender") or {}
            if sender.get("sender_type") == "app":
                return None
            sender_id = sender.get("sender_id") or {}
            owner_id = (
                sender_id.get("open_id")
                or sender_id.get("user_id")
                or sender_id.get("union_id")
                or "unknown"
            )
            message = event.get("message") or {}
            if message.get("message_type") != "text":
                return None
            text = parse_text_content(message.get("content", ""))
            if not text:
                return None
            chat_type = message.get("chat_type") or ""
            chat_id = message.get("chat_id") or ""
            if chat_type == "group" and chat_id:
                receive_id_type = "chat_id"
                receive_id = chat_id
            else:
                receive_id_type = "open_id"
                receive_id = owner_id
            return IncomingMessage(
                event_id=header.get("event_id", ""),
                owner_id=owner_id,
                receive_id_type=receive_id_type,
                receive_id=receive_id,
                text=strip_bot_mention(text),
            )

        if body.get("type") == "event_callback" and event.get("type") == "message":
            text = event.get("text") or ""
            owner_id = event.get("open_id") or event.get("user_id") or "unknown"
            chat_id = event.get("open_chat_id") or event.get("chat_id") or ""
            receive_id_type = "chat_id" if chat_id else "open_id"
            receive_id = chat_id or owner_id
            return IncomingMessage(
                event_id=body.get("uuid", ""),
                owner_id=owner_id,
                receive_id_type=receive_id_type,
                receive_id=receive_id,
                text=strip_bot_mention(text),
            )

        return None
