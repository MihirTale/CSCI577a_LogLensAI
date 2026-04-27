"""AI On-Call Assistant features: pattern detection, severity classification,
runbook suggestions, and incident timeline."""

import hashlib
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta

from models import (
    ErrorPattern, PatternsResponse,
    Incident, IncidentEvent, TimelineResponse,
    Runbook, RunbookStep, RunbooksResponse,
    HealthSummary, TopErrorSummary,
    SeverityBucket, SeveritySeriesResponse,
)
from log_reader import read_latest_logs

# Cache for target-service /health probe so we don't ping every request
_target_probe_cache: dict = {"ok": None, "ts": None}
_TARGET_PROBE_TTL = timedelta(seconds=10)


def _probe_target_service() -> bool | None:
    """Return True/False if `TARGET_SERVICE_URL` env is set and reachable.

    Returns None if no URL is configured (caller should fall back to a heuristic).
    Result is cached for 10 seconds.
    """
    url = os.getenv("TARGET_SERVICE_URL", "").strip()
    if not url:
        return None
    now = datetime.now()
    cached_ts = _target_probe_cache.get("ts")
    if cached_ts and (now - cached_ts) < _TARGET_PROBE_TTL:
        return _target_probe_cache.get("ok")
    try:
        import httpx
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(url.rstrip("/") + "/health")
        ok = resp.status_code == 200
    except Exception:
        ok = False
    _target_probe_cache["ok"] = ok
    _target_probe_cache["ts"] = now
    return ok


def _normalize_message(msg: str) -> str:
    """Strip variable parts (IDs, IPs, timestamps, numbers) to find patterns."""
    msg = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", msg)
    msg = re.sub(r"\b[a-f0-9]{8,}\b", "<ID>", msg)
    msg = re.sub(r"\b(usr|req|cus|job)_\w+\b", r"\1_<ID>", msg)
    msg = re.sub(r"\b\d+(\.\d+)?(ms|s|GB|MB|KB|%)\b", "<NUM>", msg)
    msg = re.sub(r"\$[\d,.]+", "$<AMT>", msg)
    msg = re.sub(r"\d+/\d+", "<RATIO>", msg)
    return msg


def detect_patterns(num_lines: int = 5000) -> PatternsResponse:
    """Group similar error/warning logs by normalized message pattern."""
    logs = read_latest_logs(num_lines)
    error_logs = [log for log in logs if log.level in ("ERROR", "WARN")]

    groups: dict[str, list] = defaultdict(list)
    templates: dict[str, str] = {}

    for log in error_logs:
        normalized = _normalize_message(log.message)
        pattern_hash = hashlib.md5(normalized.encode()).hexdigest()[:8]
        groups[pattern_hash].append(log)
        if pattern_hash not in templates:
            templates[pattern_hash] = normalized

    patterns = []
    for pid, group_logs in sorted(groups.items(), key=lambda x: -len(x[1])):
        severity = _classify_severity(group_logs)
        patterns.append(ErrorPattern(
            pattern_id=pid,
            message_template=templates[pid],
            count=len(group_logs),
            first_seen=group_logs[0].timestamp,
            last_seen=group_logs[-1].timestamp,
            severity=severity,
            sample_logs=[log.message[:150] for log in group_logs[:3]],
        ))

    total = sum(len(g) for g in groups.values())
    return PatternsResponse(patterns=patterns, total_errors=total)


def _classify_severity(logs: list) -> str:
    """Auto-classify severity as P0-P3 based on keywords and frequency."""
    messages = " ".join(log.message.lower() for log in logs)
    count = len(logs)

    # P0: critical keywords or very high frequency
    p0_keywords = ["outofmemory", "oom", "heap", "crash", "fatal", "data loss", "corruption"]
    if any(kw in messages for kw in p0_keywords) or count >= 20:
        return "P0"

    # P1: service-impacting keywords or moderate frequency
    p1_keywords = ["timeout", "circuit breaker", "connection pool", "500", "revenue", "failed"]
    if any(kw in messages for kw in p1_keywords) or count >= 10:
        return "P1"

    # P2: security or performance keywords
    p2_keywords = ["auth", "token", "brute force", "rate limit", "degraded", "503"]
    if any(kw in messages for kw in p2_keywords) or count >= 5:
        return "P2"

    return "P3"


def build_timeline(num_lines: int = 5000) -> TimelineResponse:
    """Build incident timeline by grouping errors that are close in time."""
    logs = read_latest_logs(num_lines)
    error_logs = [log for log in logs if log.level in ("ERROR", "WARN")]

    if not error_logs:
        return TimelineResponse(incidents=[])

    incidents: list[Incident] = []
    current_events: list[IncidentEvent] = []
    last_ts: datetime | None = None

    for log in error_logs:
        try:
            ts = datetime.strptime(log.timestamp, "%Y-%m-%d %H:%M:%S.%f")
        except (ValueError, TypeError):
            ts = datetime.now()

        event = IncidentEvent(
            timestamp=log.timestamp,
            level=log.level,
            message=log.message,
            source=log.source,
        )

        # Group events within 60 seconds of each other into the same incident
        if last_ts and (ts - last_ts) > timedelta(seconds=60):
            if current_events:
                incidents.append(_create_incident(current_events, len(incidents)))
            current_events = [event]
        else:
            current_events.append(event)
        last_ts = ts

    if current_events:
        incidents.append(_create_incident(current_events, len(incidents)))

    return TimelineResponse(incidents=incidents)


def _create_incident(events: list[IncidentEvent], index: int) -> Incident:
    severity = _classify_severity_from_events(events)
    return Incident(
        incident_id=f"INC-{index + 1:04d}",
        started_at=events[0].timestamp,
        ended_at=events[-1].timestamp if len(events) > 1 else None,
        events=events,
        severity=severity,
        status="active",
    )


def _classify_severity_from_events(events: list[IncidentEvent]) -> str:
    messages = " ".join(e.message.lower() for e in events)
    count = len(events)
    if any(kw in messages for kw in ["oom", "crash", "fatal"]):
        return "P0"
    if any(kw in messages for kw in ["timeout", "circuit", "500"]):
        return "P1"
    if count >= 5:
        return "P1"
    return "P2"


RUNBOOK_DATABASE = {
    "timeout": Runbook(
        error_pattern="Database/Connection Timeout",
        title="Database Timeout Runbook",
        severity="P1",
        steps=[
            RunbookStep(step=1, action="Check database connection pool metrics", command="SELECT count(*) FROM pg_stat_activity;"),
            RunbookStep(step=2, action="Identify long-running queries", command="SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 10;"),
            RunbookStep(step=3, action="Check for connection leaks in application logs", command="grep -c 'connection' logs/app.log"),
            RunbookStep(step=4, action="Restart connection pool if necessary"),
            RunbookStep(step=5, action="Scale up database connections or add read replicas if recurring"),
        ],
    ),
    "null": Runbook(
        error_pattern="NullPointerException / AttributeError",
        title="Null Reference Error Runbook",
        severity="P1",
        steps=[
            RunbookStep(step=1, action="Identify the exact line and variable that is null from the stack trace"),
            RunbookStep(step=2, action="Check upstream middleware/service for silent failures"),
            RunbookStep(step=3, action="Add null guards and proper error responses"),
            RunbookStep(step=4, action="Deploy hotfix and verify error rate drops"),
            RunbookStep(step=5, action="Add regression test for the null case"),
        ],
    ),
    "memory": Runbook(
        error_pattern="OutOfMemoryError / Heap Exhaustion",
        title="OOM / Memory Exhaustion Runbook",
        severity="P0",
        steps=[
            RunbookStep(step=1, action="Restart affected workers/pods immediately", command="kubectl rollout restart deployment/data-processor"),
            RunbookStep(step=2, action="Check heap dump or memory profiler output"),
            RunbookStep(step=3, action="Identify memory-heavy operations (batch loads, caches)"),
            RunbookStep(step=4, action="Implement streaming/pagination for large data sets"),
            RunbookStep(step=5, action="Set memory limits and alerts at 70% and 90% thresholds"),
        ],
    ),
    "auth": Runbook(
        error_pattern="Authentication / Token Failures",
        title="Auth Failure Runbook",
        severity="P2",
        steps=[
            RunbookStep(step=1, action="Check if failures are from a single IP or distributed"),
            RunbookStep(step=2, action="Review rate limiter status and thresholds"),
            RunbookStep(step=3, action="Block suspicious IPs if brute force is confirmed", command="iptables -A INPUT -s <suspicious_ip> -j DROP"),
            RunbookStep(step=4, action="Verify no accounts were compromised"),
            RunbookStep(step=5, action="Enable enhanced logging for auth events"),
        ],
    ),
    "payment": Runbook(
        error_pattern="Payment / External API Failure",
        title="Payment Gateway Failure Runbook",
        severity="P1",
        steps=[
            RunbookStep(step=1, action="Check external provider status page (e.g., status.stripe.com)"),
            RunbookStep(step=2, action="Enable retry queue for failed payments"),
            RunbookStep(step=3, action="Notify affected customers about delays"),
            RunbookStep(step=4, action="Switch to fallback payment provider if available"),
            RunbookStep(step=5, action="Calculate revenue impact and file incident report"),
        ],
    ),
}


def compute_health_summary(num_lines: int = 5000, window_minutes: int = 60) -> HealthSummary:
    """Compute service-health KPIs from recent logs.

    - error_rate_per_min: avg ERROR/WARN per minute across the rolling window
    - error_rate_series: one bucket per minute (oldest → newest)
    - active_incidents: count of P0/P1 incidents across ALL logs (cumulative)
    - severity_counts: total ERROR/WARN by severity across ALL logs (cumulative)
    - top_error: most-frequent error pattern in window (kept for back-compat)
    - mttr_minutes: mean duration of resolved incidents (best-effort, single-process)
    - status: healthy | degraded | down
        • If TARGET_SERVICE_URL is set: down iff target /health is unreachable
        • Else: down iff no logs at all in last 5 minutes (target likely silent)
        • degraded layer applied on top when error volume is elevated
    """
    logs = read_latest_logs(num_lines)
    now = datetime.now()
    window_start = now - timedelta(minutes=window_minutes)
    recent_activity_cutoff = now - timedelta(minutes=5)

    buckets = [0] * window_minutes
    severity_counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}

    error_logs_window: list = []
    last_log_ts: datetime | None = None

    for log in logs:
        try:
            ts = datetime.strptime(log.timestamp, "%Y-%m-%d %H:%M:%S.%f")
        except (ValueError, TypeError):
            continue
        if last_log_ts is None or ts > last_log_ts:
            last_log_ts = ts
        if log.level not in ("ERROR", "WARN"):
            continue

        # Cumulative severity counts (all-time, not windowed)
        sev = _classify_severity([log])
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Windowed metrics (rolling)
        if ts < window_start:
            continue
        error_logs_window.append(log)
        minutes_ago = int((now - ts).total_seconds() // 60)
        idx = (window_minutes - 1) - minutes_ago
        if 0 <= idx < window_minutes:
            buckets[idx] += 1

    total_window = sum(buckets)
    error_rate_per_min = total_window / float(window_minutes)

    # Top error in window (kept for API back-compat)
    top_error: TopErrorSummary | None = None
    if error_logs_window:
        groups: dict[str, list] = defaultdict(list)
        templates: dict[str, str] = {}
        for log in error_logs_window:
            normalized = _normalize_message(log.message)
            key = hashlib.md5(normalized.encode()).hexdigest()[:8]
            groups[key].append(log)
            templates.setdefault(key, normalized)
        top_key = max(groups.keys(), key=lambda k: len(groups[k]))
        top_error = TopErrorSummary(
            message_template=templates[top_key][:120],
            count=len(groups[top_key]),
            severity=_classify_severity(groups[top_key]),
        )

    # Active incidents (P0/P1) across ALL logs (cumulative, not windowed)
    timeline = build_timeline(num_lines)
    active_incidents = 0
    durations: list[float] = []
    for inc in timeline.incidents:
        try:
            started = datetime.strptime(inc.started_at, "%Y-%m-%d %H:%M:%S.%f")
        except (ValueError, TypeError):
            continue
        if inc.severity in ("P0", "P1"):
            active_incidents += 1
        if inc.ended_at and inc.ended_at != inc.started_at:
            try:
                ended = datetime.strptime(inc.ended_at, "%Y-%m-%d %H:%M:%S.%f")
                durations.append((ended - started).total_seconds() / 60.0)
            except (ValueError, TypeError):
                pass

    mttr_minutes = (sum(durations) / len(durations)) if durations else None

    # Status: target-service availability is the canonical "up/down" signal,
    # error volume only modulates between healthy / degraded.
    target_ok = _probe_target_service()  # None if not configured
    if target_ok is False:
        status = "down"
    elif target_ok is None and (last_log_ts is None or last_log_ts < recent_activity_cutoff):
        # No probe configured AND nothing has written to the log file recently → silent
        status = "down"
    elif error_rate_per_min >= 1 or active_incidents >= 1:
        status = "degraded"
    else:
        status = "healthy"

    return HealthSummary(
        error_rate_per_min=round(error_rate_per_min, 2),
        error_rate_series=buckets,
        window_minutes=window_minutes,
        active_incidents=active_incidents,
        severity_counts=severity_counts,
        top_error=top_error,
        mttr_minutes=round(mttr_minutes, 1) if mttr_minutes is not None else None,
        status=status,
    )


def compute_severity_series(num_lines: int = 5000, window_minutes: int = 60) -> SeveritySeriesResponse:
    """Per-minute counts of ERROR/WARN logs split by severity over the last N minutes.

    Severity is assigned by classifying each *log message in isolation* using the
    same heuristic as `_classify_severity` (which expects a list).
    """
    logs = read_latest_logs(num_lines)
    now = datetime.now()
    window_start = now - timedelta(minutes=window_minutes)

    # buckets indexed 0..window_minutes-1 (0 = oldest, window_minutes-1 = current)
    counts: list[dict[str, int]] = [
        {"P0": 0, "P1": 0, "P2": 0, "P3": 0, "total": 0}
        for _ in range(window_minutes)
    ]

    for log in logs:
        if log.level not in ("ERROR", "WARN"):
            continue
        try:
            ts = datetime.strptime(log.timestamp, "%Y-%m-%d %H:%M:%S.%f")
        except (ValueError, TypeError):
            continue
        if ts < window_start or ts > now:
            continue
        minutes_ago = int((now - ts).total_seconds() // 60)
        idx = (window_minutes - 1) - minutes_ago
        if idx < 0 or idx >= window_minutes:
            continue
        sev = _classify_severity([log])
        counts[idx][sev] = counts[idx].get(sev, 0) + 1
        counts[idx]["total"] += 1

    buckets = [
        SeverityBucket(
            minute_offset=i - (window_minutes - 1),  # negative = past, 0 = current
            P0=c["P0"], P1=c["P1"], P2=c["P2"], P3=c["P3"], total=c["total"],
        )
        for i, c in enumerate(counts)
    ]
    return SeveritySeriesResponse(buckets=buckets, window_minutes=window_minutes)


def suggest_runbooks(num_lines: int = 5000) -> RunbooksResponse:
    """Match current error patterns to relevant runbooks."""
    logs = read_latest_logs(num_lines)
    error_logs = [log for log in logs if log.level in ("ERROR", "WARN")]

    if not error_logs:
        return RunbooksResponse(runbooks=[])

    all_messages = " ".join(log.message.lower() for log in error_logs)

    matched_runbooks = []
    keyword_map = {
        "timeout": ["timeout", "connection", "pool"],
        "null": ["none", "null", "attribute", "nonetype"],
        "memory": ["memory", "oom", "heap", "gc"],
        "auth": ["auth", "token", "brute", "credential"],
        "payment": ["payment", "charge", "503", "stripe", "gateway"],
    }

    for key, keywords in keyword_map.items():
        if any(kw in all_messages for kw in keywords):
            matched_runbooks.append(RUNBOOK_DATABASE[key])

    return RunbooksResponse(runbooks=matched_runbooks)
