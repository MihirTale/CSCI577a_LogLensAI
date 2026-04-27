import os
import re
from datetime import datetime
from models import LogEntry

LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "app.log")

LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+(ERROR|WARN|INFO|DEBUG)\s*(?:\[([^\]]+)\])?\s*(.+)$"
)


def parse_log_line(line: str) -> LogEntry | None:
    line = line.strip()
    if not line:
        return None
    match = LOG_PATTERN.match(line)
    if match:
        return LogEntry(
            timestamp=match.group(1),
            level=match.group(2),
            message=match.group(4),
            source=match.group(3),
        )
    return LogEntry(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        level="INFO",
        message=line,
    )


def read_latest_logs(n: int = 50) -> list[LogEntry]:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    recent = lines[-n:] if len(lines) > n else lines
    entries = []
    for line in recent:
        entry = parse_log_line(line)
        if entry:
            entries.append(entry)
    return entries


def get_error_logs(n: int = 50) -> list[LogEntry]:
    logs = read_latest_logs(n * 2)  # read more to find enough errors
    return [log for log in logs if log.level in ("ERROR", "WARN")]


def get_raw_lines(n: int = 50) -> list[str]:
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    recent = lines[-n:] if len(lines) > n else lines
    return [l.strip() for l in recent if l.strip()]
