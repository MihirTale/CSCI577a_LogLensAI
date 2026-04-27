import os
import random
import threading
import time
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
MAX_LOG_SIZE = 1_000_000  # 1MB, then rotate

os.makedirs(LOG_DIR, exist_ok=True)

_lock = threading.Lock()

INFO_MESSAGES = [
    "Request processed successfully | endpoint=/api/users | method=GET | duration=42ms",
    "Cache hit for session token | user_id=usr_8291 | ttl=300s",
    "Database query executed | table=orders | rows=156 | duration=18ms",
    "Health check passed | service=payment-gateway | latency=5ms",
    "Background job completed | job=email_digest | processed=230 | failed=0",
    "WebSocket connection established | client=dashboard-ui | channel=metrics",
    "Rate limiter check passed | ip=192.168.1.42 | remaining=98/100",
    "Config reloaded successfully | source=config.yaml | keys_updated=3",
    "Scheduled task started | task=cleanup_temp_files | interval=3600s",
    "API response sent | endpoint=/api/products | status=200 | size=4.2KB",
    "Authentication successful | user=admin@example.com | method=oauth2",
    "File upload completed | filename=report_q3.pdf | size=2.1MB | bucket=uploads",
    "Metric emitted | name=request_latency_p99 | value=125ms | tags=service:api",
]

ERROR_TEMPLATES = {
    "db_timeout": {
        "message": "Database connection timeout | host=db-primary.internal:5432 | timeout=30s | query=SELECT * FROM orders WHERE status='pending' | pool_active=48/50",
        "source": "backend/services/order_service.py:142",
        "followup": [
            "WARN  Connection pool near capacity | active=48/50 | waiting=12",
            "ERROR Retry 1/3 failed for database query | error=ConnectionTimeout",
            "ERROR Retry 2/3 failed for database query | error=ConnectionTimeout",
            "ERROR Circuit breaker OPEN for db-primary | failures=15 | threshold=10",
        ],
    },
    "null_pointer": {
        "message": "NullPointerException: 'NoneType' object has no attribute 'user_id' | endpoint=/api/checkout | request_id=req_abc123",
        "source": "backend/services/checkout_service.py:87",
        "followup": [
            "ERROR Traceback: File checkout_service.py line 87, in process_checkout | session.user_id",
            "ERROR Request failed | endpoint=/api/checkout | status=500 | request_id=req_abc123",
            "WARN  Unhandled exception rate increasing | current=5/min | threshold=10/min",
        ],
    },
    "oom": {
        "message": "OutOfMemoryError: Java heap space exceeded | service=data-processor | heap_used=3.8GB/4GB | gc_overhead=98%",
        "source": "backend/workers/data_processor.py:203",
        "followup": [
            "WARN  GC overhead limit exceeded | time_in_gc=95% | freed=12MB",
            "ERROR Worker thread terminated | thread=data-worker-3 | reason=OutOfMemoryError",
            "ERROR Job failed | job_id=job_7841 | type=batch_import | records_processed=45000/100000",
            "WARN  Service degraded | healthy_workers=2/5 | queue_depth=1240",
        ],
    },
    "auth_failure": {
        "message": "AuthenticationError: Invalid or expired token | endpoint=/api/admin/settings | token_prefix=eyJhb... | ip=203.0.113.42",
        "source": "backend/middleware/auth.py:56",
        "followup": [
            "WARN  Suspicious auth pattern detected | ip=203.0.113.42 | failed_attempts=12 | window=60s",
            "ERROR Token validation failed | reason=token_expired | issued_at=2024-01-15T08:00:00Z | expired_at=2024-01-15T09:00:00Z",
            "WARN  Potential brute force attack | source_ip=203.0.113.42 | blocked=false",
        ],
    },
    "api_failure": {
        "message": "ExternalAPIError: Payment gateway returned 503 | provider=stripe | endpoint=/v1/charges | retry_after=30s",
        "source": "backend/services/payment_service.py:118",
        "followup": [
            "WARN  Payment processing degraded | success_rate=62% | window=5min",
            "ERROR Charge failed | amount=$149.99 | customer=cus_9182 | error=service_unavailable",
            "ERROR Revenue impact detected | failed_charges=23 | total=$4,127.50 | window=10min",
        ],
    },
}


def _format_log(level: str, message: str, source: str | None = None) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    src = f" [{source}]" if source else ""
    return f"{ts} {level:<5}{src} {message}\n"


def _rotate_if_needed():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        backup = LOG_FILE + ".1"
        if os.path.exists(backup):
            os.remove(backup)
        os.rename(LOG_FILE, backup)


def write_log(level: str, message: str, source: str | None = None):
    with _lock:
        _rotate_if_needed()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(_format_log(level, message, source))


def write_info():
    msg = random.choice(INFO_MESSAGES)
    write_log("INFO", msg)


def simulate_error(error_type: str | None = None) -> str:
    if error_type is None or error_type not in ERROR_TEMPLATES:
        error_type = random.choice(list(ERROR_TEMPLATES.keys()))

    template = ERROR_TEMPLATES[error_type]
    write_log("ERROR", template["message"], template.get("source"))
    for line in template.get("followup", []):
        level = "ERROR" if line.startswith("ERROR") else "WARN"
        msg = line.split(None, 1)[1] if " " in line else line
        write_log(level, msg, template.get("source"))

    return error_type


def seed_logs():
    """Write initial seed logs so the app has data on first run."""
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        return
    write_log("INFO", "=== LogLens Application Started ===")
    write_log("INFO", "Service initialized | version=1.0.0 | env=development")
    write_log("INFO", "Database connected | host=db-primary.internal:5432 | pool_size=50")
    write_log("INFO", "Cache connected | host=redis.internal:6379 | max_memory=512MB")
    write_log("INFO", "API server listening | port=8000 | workers=4")
    for _ in range(8):
        write_info()


def _background_writer():
    """Background thread that writes periodic INFO logs."""
    while True:
        time.sleep(random.uniform(3, 7))
        write_info()


def start_background_writer():
    t = threading.Thread(target=_background_writer, daemon=True)
    t.start()
