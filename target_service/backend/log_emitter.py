"""Append formatted log lines into the shared LogLens log file.

Format must match the regex used by `loglens/backend/log_reader.py`:
    YYYY-MM-DD HH:MM:SS.fff LEVEL [source] message
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

# By default, write into the LogLens backend's logs/app.log so the dashboard
# tails the same file. Override with TARGET_LOG_FILE env var.
_DEFAULT_LOG = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "logs" / "app.log"
)
LOG_FILE = Path(os.getenv("TARGET_LOG_FILE", str(_DEFAULT_LOG)))
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def _format(level: str, message: str, source: str | None) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    src = f" [{source}]" if source else ""
    return f"{ts} {level:<5}{src} {message}\n"


def emit(level: str, message: str, source: str | None = None) -> None:
    line = _format(level, message, source)
    with _lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)


def emit_info(message: str, source: str | None = None) -> None:
    emit("INFO", message, source)


def emit_warn(message: str, source: str | None = None) -> None:
    emit("WARN", message, source)


def emit_error(message: str, source: str | None = None) -> None:
    emit("ERROR", message, source)
