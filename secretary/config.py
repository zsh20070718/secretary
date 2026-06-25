from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from datetime import UTC, timezone, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if not value:
        return default
    return int(value)


def _path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path.cwd() / path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_path: Path
    default_timezone: tzinfo
    scheduler_poll_seconds: int
    feishu_base_url: str
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str
    feishu_webhook_url: str
    bing_search_api_key: str
    bing_search_endpoint: str


def load_settings() -> Settings:
    load_dotenv(Path.cwd() / ".env")
    default_tz = _env("SECRETARY_DEFAULT_TIMEZONE", "UTC")
    return Settings(
        host=_env("SECRETARY_HOST", "0.0.0.0"),
        port=_env_int("SECRETARY_PORT", 8080),
        database_path=_path(_env("SECRETARY_DATABASE", "data/secretary.sqlite3")),
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
