from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import Settings
from .logging_utils import get_logger


class FeishuError(RuntimeError):
    pass


logger = get_logger(__name__)


class FeishuClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._token = ""
        self._token_expires_at = 0.0
        self._lock = threading.RLock()

    def send_text(self, receive_id_type: str, receive_id: str, text: str) -> None:
        logger.info(
            "Sending Feishu text receive_id_type=%s text_length=%s",
            receive_id_type,
            len(text),
        )
        if receive_id_type == "webhook":
            self._send_webhook(text)
            return
        if self.settings.feishu_app_id and self.settings.feishu_app_secret:
            self._send_app_message(receive_id_type, receive_id, text)
            return
        if self.settings.feishu_webhook_url:
            self._send_webhook(f"[{receive_id_type}:{receive_id}]\n{text}")
            return
        raise FeishuError("Feishu credentials or webhook URL are not configured.")

    def _send_app_message(self, receive_id_type: str, receive_id: str, text: str) -> None:
        token = self._tenant_access_token()
        query = urllib.parse.urlencode({"receive_id_type": receive_id_type})
        url = f"{self.settings.feishu_base_url}/open-apis/im/v1/messages?{query}"
        body = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        self._json_request(
            "POST",
            url,
            body,
            headers={"Authorization": f"Bearer {token}"},
        )
        logger.info("Feishu text sent receive_id_type=%s", receive_id_type)

    def _send_webhook(self, text: str) -> None:
        if not self.settings.feishu_webhook_url:
            raise FeishuError("FEISHU_WEBHOOK_URL is not configured.")
        self._json_request(
            "POST",
            self.settings.feishu_webhook_url,
            {
                "msg_type": "text",
                "content": {"text": text},
            },
        )

    def _tenant_access_token(self) -> str:
        now = time.time()
        with self._lock:
            if self._token and now < self._token_expires_at:
                return self._token

            url = f"{self.settings.feishu_base_url}/open-apis/auth/v3/tenant_access_token/internal"
            data = self._json_request(
                "POST",
                url,
                {
                    "app_id": self.settings.feishu_app_id,
                    "app_secret": self.settings.feishu_app_secret,
                },
                require_code_zero=False,
            )
            if data.get("code", 0) != 0:
                raise FeishuError(f"Failed to get tenant_access_token: {data}")
            token = str(data.get("tenant_access_token") or "")
            if not token:
                raise FeishuError("Feishu token response did not include tenant_access_token.")
            expire = int(data.get("expire", 7200))
            self._token = token
            self._token_expires_at = now + max(expire - 120, 60)
            logger.info("Refreshed Feishu tenant access token expires_in=%s", expire)
            return token

    def _json_request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        require_code_zero: bool = True,
    ) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                **(headers or {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise FeishuError(f"Feishu HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise FeishuError(f"Feishu request failed: {exc}") from exc

        data = json.loads(raw) if raw else {}
        if require_code_zero and data.get("code", 0) != 0:
            raise FeishuError(f"Feishu API returned error: {data}")
        return data
