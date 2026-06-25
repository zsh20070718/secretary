from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(log_file: Path) -> None:
    logger = logging.getLogger("secretary")
    if logger.handlers:
        return

    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        "%Y-%m-%dT%H:%M:%S%z",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    if name.startswith("secretary"):
        return logging.getLogger(name)
    return logging.getLogger(f"secretary.{name}")

