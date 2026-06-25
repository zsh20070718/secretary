from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from datetime import UTC, timezone, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .codex_tui import CodexTuiConfig


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _unquote_env_value(value.strip())
        if not os.environ.get(key):
            os.environ[key] = value


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if not value:
        return default
    return int(value)


def _env_csv(name: str) -> frozenset[str]:
    value = _env(name)
    if not value:
        return frozenset()
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def _path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


@dataclass(frozen=True)
class Settings:
    feishu_event_mode: str
    host: str
    port: int
    database_path: Path
    log_file: Path
    default_timezone: tzinfo
    scheduler_poll_seconds: int
    feishu_base_url: str
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str
    feishu_webhook_url: str
    bing_search_api_key: str
    bing_search_endpoint: str
    allowed_open_ids: frozenset[str]
    codex_tui_config: CodexTuiConfig


def load_settings() -> Settings:
    load_dotenv(Path.cwd() / ".env")
    default_tz = _env("SECRETARY_DEFAULT_TIMEZONE", "UTC")
    feishu_event_mode = _env("SECRETARY_FEISHU_EVENT_MODE", "long_connection")
    return Settings(
        feishu_event_mode=feishu_event_mode,
        host=_env("SECRETARY_HOST", "0.0.0.0"),
        port=_env_int("SECRETARY_PORT", 8080),
        database_path=_path(_env("SECRETARY_DATABASE", "data/secretary.sqlite3")),
        log_file=_path(_env("SECRETARY_LOG_FILE", "data/secretary.log")),
        default_timezone=parse_timezone(default_tz),
        scheduler_poll_seconds=_env_int("SECRETARY_POLL_SECONDS", 15),
        feishu_base_url=_env("FEISHU_BASE_URL", "https://open.feishu.cn").rstrip("/"),
        feishu_app_id=_env("FEISHU_APP_ID"),
        feishu_app_secret=_env("FEISHU_APP_SECRET"),
        feishu_verification_token=_env("FEISHU_VERIFICATION_TOKEN"),
        feishu_webhook_url=_env("FEISHU_WEBHOOK_URL"),
        bing_search_api_key=_env("BING_SEARCH_API_KEY"),
        bing_search_endpoint=_env(
            "BING_SEARCH_ENDPOINT",
            "https://api.bing.microsoft.com/v7.0/search",
        ),
        allowed_open_ids=_env_csv("SECRETARY_ALLOWED_OPEN_IDS"),
        codex_tui_config=CodexTuiConfig(
            command=_env("CODEX_TUI_COMMAND", "codex"),
            workdir=_path(_env("CODEX_TUI_WORKDIR", "codex-workspace")),
            session=_env("CODEX_TUI_TMUX_SESSION", "secretary-codex"),
            capture_lines=_env_int("CODEX_TUI_CAPTURE_LINES", 160),
            response_timeout_seconds=_env_int("CODEX_TUI_RESPONSE_TIMEOUT_SECONDS", 30),
            stable_seconds=_env_int("CODEX_TUI_STABLE_SECONDS", 4),
            max_reply_chars=_env_int("CODEX_TUI_MAX_REPLY_CHARS", 3500),
        ),
    )


def parse_timezone(value: str) -> tzinfo:
    text = value.strip()
    if not text or text.upper() in ("UTC", "Z"):
        return UTC
    try:
        return ZoneInfo(text)
    except ZoneInfoNotFoundError:
        pass
    if text in ("Asia/Shanghai", "PRC", "Asia/Chongqing"):
        return timezone(timedelta(hours=8), name="Asia/Shanghai")
    sign = 1
    offset = text
    if offset.startswith("+"):
        offset = offset[1:]
    elif offset.startswith("-"):
        sign = -1
        offset = offset[1:]
    else:
        raise ValueError(
            f"Unknown timezone {value!r}. Use UTC, +08:00, or install tzdata."
        )
    hour_text, sep, minute_text = offset.partition(":")
    if not sep:
        minute_text = "0"
    hours = int(hour_text)
    minutes = int(minute_text)
    return timezone(sign * timedelta(hours=hours, minutes=minutes), name=value)
