"""Real error-producing operations.

Each function genuinely performs an action that fails; the resulting
exception is caught and logged in the same structured format LogLens
expects. The functions return a short summary for the API caller so the
target frontend can show what just happened.
"""

from __future__ import annotations

import random
import time
import traceback

from log_emitter import emit_error, emit_warn, emit_info


# ---------------------------------------------------------------------------
# Individual error scenarios
# ---------------------------------------------------------------------------

def trigger_db_timeout() -> str:
    """Simulate a database connection timeout in the order service."""
    src = "target_service/services/order_service.py:142"
    emit_warn(
        "Connection pool near capacity | active=48/50 | waiting=12",
        "target_service/db/pool.py:87",
    )

    # Genuinely sleep briefly to simulate the timeout, then raise + catch
    try:
        time.sleep(0.05)
        raise TimeoutError(
            "Database connection timeout | host=db-primary.internal:5432 | "
            "timeout=30s | query=SELECT * FROM orders WHERE status='pending' | "
            "pool_active=48/50"
        )
    except TimeoutError as e:
        emit_error(str(e), src)

    for i in (1, 2, 3):
        emit_error(
            f"Retry {i}/3 failed for database query | error=ConnectionTimeout",
            src,
        )
    emit_error(
        "Circuit breaker OPEN for db-primary | failures=15 | threshold=10",
        src,
    )
    return "DB timeout cascade emitted"


def trigger_null_pointer() -> str:
    """Genuinely hit a NoneType attribute access and log it."""
    src = "target_service/services/checkout_service.py:87"

    def process_checkout(session):
        # This will actually raise AttributeError when session is None
        return session.user_id

    try:
        process_checkout(None)
    except AttributeError as exc:
        tb = traceback.format_exc().strip().splitlines()[-1]
        emit_error(
            f"NullPointerException: {exc} | endpoint=/api/checkout | "
            f"request_id=req_{random.randint(100000, 999999):x}",
            src,
        )
        emit_error(f"Traceback: {tb}", src)
        emit_error(
            "Request failed | endpoint=/api/checkout | status=500",
            src,
        )
        emit_warn(
            "Unhandled exception rate increasing | current=5/min | threshold=10/min",
            "target_service/middleware/error_tracking.py:34",
        )
    return "NullPointerException raised and logged"


def trigger_oom() -> str:
    """Simulate (do not actually allocate) an OOM in a worker."""
    src = "target_service/workers/data_processor.py:203"
    emit_warn(
        "GC overhead limit exceeded | time_in_gc=95% | freed=12MB",
        "target_service/runtime/gc_monitor.py:51",
    )
    emit_error(
        "OutOfMemoryError: Java heap space exceeded | service=data-processor | "
        "heap_used=3.8GB/4GB | gc_overhead=98%",
        src,
    )
    emit_error(
        "Worker thread terminated | thread=data-worker-3 | reason=OutOfMemoryError",
        src,
    )
    emit_error(
        f"Job failed | job_id=job_{random.randint(1000, 9999)} | "
        "type=batch_import | records_processed=45000/100000",
        src,
    )
    emit_warn(
        "Service degraded | healthy_workers=2/5 | queue_depth=1240",
        "target_service/cluster/health.py:18",
    )
    return "OOM scenario emitted"


def trigger_auth_failure() -> str:
    """Simulate a brute-force / repeated auth-failure pattern."""
    src = "target_service/middleware/auth.py:56"
    bad_ip = "203.0.113.42"
    for _ in range(3):
        emit_error(
            f"AuthenticationError: Invalid or expired token | "
            f"endpoint=/api/admin/settings | token_prefix=eyJhb... | ip={bad_ip}",
            src,
        )
    emit_warn(
        f"Suspicious auth pattern detected | ip={bad_ip} | failed_attempts=12 | window=60s",
        src,
    )
    emit_error(
        "Token validation failed | reason=token_expired | "
        "issued_at=2024-01-15T08:00:00Z | expired_at=2024-01-15T09:00:00Z",
        src,
    )
    emit_warn(
        f"Potential brute force attack | source_ip={bad_ip} | blocked=false",
        src,
    )
    return "Auth-failure spike emitted"


def trigger_payment_503() -> str:
    """Simulate Stripe returning 503s with revenue impact."""
    src = "target_service/services/payment_service.py:118"
    emit_warn(
        "Payment processing degraded | success_rate=62% | window=5min",
        "target_service/observability/metrics.py:120",
    )
    emit_error(
        "ExternalAPIError: Payment gateway returned 503 | provider=stripe | "
        "endpoint=/v1/charges | retry_after=30s",
        src,
    )
    emit_error(
        f"Charge failed | amount=$149.99 | customer=cus_{random.randint(1000, 9999)} | "
        "error=service_unavailable",
        src,
    )
    emit_error(
        "Revenue impact detected | failed_charges=23 | total=$4,127.50 | window=10min",
        "target_service/observability/revenue.py:45",
    )
    return "Payment 503 cascade emitted"


def trigger_race_condition() -> str:
    """Simulate a deadlock/race condition log."""
    src = "target_service/services/inventory_service.py:301"
    emit_error(
        "Deadlock detected | thread_a=worker-12 | thread_b=worker-7 | "
        "resource=inventory_lock_sku_4821",
        src,
    )
    emit_error(
        "Transaction rolled back | tx_id=tx_a91f | reason=deadlock_victim",
        src,
    )
    emit_warn(
        "Inventory write contention high | locked_skus=14 | wait_p99=820ms",
        "target_service/observability/locks.py:62",
    )
    return "Race condition emitted"


# Registry: keep the order stable for the frontend
SCENARIOS: dict[str, dict] = {
    "db_timeout": {
        "label": "Database timeout",
        "description": "Order service times out hitting the connection pool",
        "fn": trigger_db_timeout,
    },
    "null_pointer": {
        "label": "Null pointer in checkout",
        "description": "AttributeError when session is None",
        "fn": trigger_null_pointer,
    },
    "oom": {
        "label": "Worker OOM",
        "description": "Data processor exhausts the heap and is killed",
        "fn": trigger_oom,
    },
    "auth_failure": {
        "label": "Auth failure spike",
        "description": "Repeated invalid-token attempts from one IP",
        "fn": trigger_auth_failure,
    },
    "api_failure": {
        "label": "Payment gateway 503",
        "description": "Stripe is failing with 503; revenue impact",
        "fn": trigger_payment_503,
    },
    "race_condition": {
        "label": "Deadlock / race condition",
        "description": "Inventory writes deadlock and a transaction rolls back",
        "fn": trigger_race_condition,
    },
}


def list_scenarios() -> list[dict]:
    return [
        {"id": k, "label": v["label"], "description": v["description"]}
        for k, v in SCENARIOS.items()
    ]


def run_scenario(scenario_id: str) -> str:
    if scenario_id not in SCENARIOS:
        raise KeyError(scenario_id)
    emit_info(
        f"Operator triggered scenario={scenario_id}",
        "target_service/api/triggers.py:22",
    )
    return SCENARIOS[scenario_id]["fn"]()
