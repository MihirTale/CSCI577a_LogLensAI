import json
import os
from datetime import datetime
from dotenv import load_dotenv

from models import AnalysisResult, ActionableFix, SuspectCommit
from log_reader import get_error_logs, get_raw_lines
from code_context import get_code_context

load_dotenv()

_last_analysis: AnalysisResult | None = None


def get_last_analysis() -> AnalysisResult | None:
    return _last_analysis


def _build_prompt(raw_lines: list[str], error_logs: list, code_context: str) -> str:
    error_text = "\n".join(
        f"[{log.timestamp}] {log.level} {f'[{log.source}] ' if log.source else ''}{log.message}"
        for log in error_logs
    )
    all_logs = "\n".join(raw_lines[-30:])

    return f"""You are a senior SRE / on-call engineer analysing production application logs. Your job is to produce a structured analysis suitable for an on-call dashboard AND a polished GitHub issue.

## Recent Logs (last 30 lines)
{all_logs}

## Error / Warning Lines
{error_text}

## Relevant Code Context
{code_context}

## Instructions
Return ONLY a JSON object (no markdown fencing, no commentary) with exactly these fields:

- "title": concise summary of the issue, max 80 chars (string)
- "severity": one of "P0" (critical, immediate), "P1" (high, same-day), "P2" (medium, sprint), "P3" (low, backlog) (string)
- "root_cause": detailed root cause analysis distinguishing symptom vs root cause (string)
- "evidence": specific log lines or patterns that support your analysis (list of strings)
- "actionable_fixes": list of objects, each with:
    - "id": unique string id like "fix_1"
    - "description": what to do (string)
    - "code_snippet": optional code fix (string or null)
    - "file_path": exact file path if known (string or null)
    - "priority": "high", "medium", or "low"
- "recommended_next_steps": ordered list of what the on-call engineer should do next (list of strings)
- "confidence": 0.0 to 1.0 (number)
- "user_impact": one-line concrete user/business impact, e.g. "Estimated 23 users affected, $4,127 revenue at risk" (string)
- "github_issue_title": "<P0|P1|P2|P3>: <concise title>" suitable for a GitHub issue (string, max 80 chars)
- "github_issue_labels": list of GitHub label names to apply, e.g. ["bug", "ai-oncall", "severity-p1", "area-payments"]. Always include "bug" and "ai-oncall". Add a severity label ("severity-p0"/"severity-p1"/"severity-p2"/"severity-p3") matching the chosen severity. Add 1-2 area/topic labels (e.g. "area-database", "area-auth", "area-payments", "memory", "race-condition") inferred from the error category.
- "github_issue_body": a polished GitHub-flavoured Markdown issue body with EXACTLY these sections in order:

```
## Summary
<one-paragraph executive summary>

## Errors Detected
### Error 1 \u2014 <ErrorType>
**Source:** <service / file or "unknown">
**Root cause:** <explanation>
**Affected code:** <file:line or "unknown">

(repeat for each distinct error)

## Impact Assessment
**Severity:** <P0|P1|P2|P3>
**User impact:** <one-line user_impact>
<paragraph on business / operational impact>

## Recommended Fixes
### Fix for Error 1
\\`\\`\\`<lang>
# Before (buggy)
...
# After (fixed)
...
\\`\\`\\`
<written explanation>

(repeat for each error)

## Prevention Measures
- <bullet list of process / code / monitoring changes>

## References
- Log window analysed: <first..last timestamp from evidence>
- See actionable fixes in the LogLens dashboard
```

Do NOT include the "# Title" heading at the top of `github_issue_body` (the title is a separate field). Do NOT add any text outside the JSON object."""


def _detect_provider_and_model() -> tuple[str, str]:
    model = (os.getenv("AI_MODEL") or "").strip()
    if not model:
        return "gemini", "gemini-2.0-flash"
    if "claude" in model.lower():
        return "claude", model
    return "gemini", model


_GEMINI_FALLBACKS = ["gemini-2.0-flash", "gemini-1.5-flash"]


def _call_gemini(prompt: str) -> dict | None:
    api_key = os.getenv("AI_API_KEY", "")
    primary = (os.getenv("AI_MODEL") or "gemini-2.0-flash").strip()
    if not api_key:
        return None
    candidates = [primary] + [m for m in _GEMINI_FALLBACKS if m != primary]
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Gemini SDK unavailable: {e}")
        return None
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            data = json.loads(text)
            if model_name != primary:
                print(
                    f"[analyzer] WARNING: AI_MODEL='{primary}' rejected; "
                    f"used fallback '{model_name}' instead."
                )
            return data
        except Exception as e:
            print(f"Gemini API call ('{model_name}') failed: {e}")
            continue
    return None


def _severity_label(severity: str) -> str:
    return f"severity-{severity.lower()}" if severity in ("P0", "P1", "P2", "P3") else "severity-p2"


def _normalize_labels(labels: list[str] | None, severity: str) -> list[str]:
    """Ensure required labels exist and de-dupe while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in (labels or []) + ["bug", "ai-oncall", _severity_label(severity)]:
        if not raw:
            continue
        lbl = str(raw).strip().lower().replace(" ", "-")
        if lbl and lbl not in seen:
            seen.add(lbl)
            out.append(lbl)
    return out


def _mock_analysis(error_logs: list) -> dict:
    """Deterministic mock analysis for when LLM is unavailable."""
    primary_error = error_logs[0] if error_logs else None
    msg = primary_error.message if primary_error else "Unknown error"
    source = primary_error.source if primary_error else "unknown"

    # Detect error type from message
    if "timeout" in msg.lower() or "connection" in msg.lower():
        return _mock_db_timeout(msg, source, error_logs)
    elif "none" in msg.lower() or "null" in msg.lower():
        return _mock_null_pointer(msg, source, error_logs)
    elif "memory" in msg.lower() or "oom" in msg.lower() or "heap" in msg.lower():
        return _mock_oom(msg, source, error_logs)
    elif "auth" in msg.lower() or "token" in msg.lower():
        return _mock_auth_failure(msg, source, error_logs)
    elif "payment" in msg.lower() or "503" in msg.lower():
        return _mock_api_failure(msg, source, error_logs)
    else:
        return _mock_generic(msg, source, error_logs)


def _mock_db_timeout(msg, source, error_logs):
    return {
        "title": "Database Connection Timeout — Connection Pool Exhaustion",
        "severity": "P1",
        "root_cause": "The database connection pool is near capacity (48/50 active connections), causing queries to timeout. The root cause is likely a connection leak or a long-running query holding connections open. The symptom is the 30s timeout, but the underlying issue is pool exhaustion.",
        "evidence": [log.message for log in error_logs[:4]],
        "actionable_fixes": [
            {"id": "fix_1", "description": "Add query timeout to the pending orders query", "code_snippet": 'result = db_session.execute(query, timeout=10)', "file_path": "backend/services/order_service.py", "priority": "high"},
            {"id": "fix_2", "description": "Increase connection pool size and add pool overflow", "code_snippet": 'engine = create_engine(url, pool_size=100, max_overflow=20)', "file_path": "backend/config/database.py", "priority": "high"},
            {"id": "fix_3", "description": "Add connection leak detection and idle connection cleanup", "code_snippet": None, "file_path": "backend/config/database.py", "priority": "medium"},
            {"id": "fix_4", "description": "Add index on orders.status column to speed up the query", "code_snippet": "CREATE INDEX idx_orders_status ON orders(status);", "file_path": "migrations/add_status_index.sql", "priority": "medium"},
        ],
        "recommended_next_steps": [
            "Check current connection pool metrics and identify any leaked connections",
            "Run EXPLAIN ANALYZE on the pending orders query to check for full table scans",
            "Monitor connection pool usage after deploying the fix",
            "Set up alerts for pool utilization > 80%",
        ],
        "confidence": 0.87,
        "user_impact": "Order checkout latency >30s; ~12% of orders failing in last 5 min.",
        "github_issue_title": "P1: Database connection timeout due to pool exhaustion",
        "github_issue_labels": ["bug", "ai-oncall", "severity-p1", "area-database", "performance"],
    }


def _mock_null_pointer(msg, source, error_logs):
    return {
        "title": "NullPointerException in Checkout Flow",
        "severity": "P1",
        "root_cause": "The checkout_service.py accesses session.user_id without null-checking the session object. The auth middleware may fail silently and pass a None session downstream. The symptom is the NullPointerException, but the root cause is missing null-safety in the auth middleware integration.",
        "evidence": [log.message for log in error_logs[:4]],
        "actionable_fixes": [
            {"id": "fix_1", "description": "Add null check for session before accessing user_id", "code_snippet": "if not session or not session.user_id:\n    raise HTTPException(status_code=401, detail='Invalid session')", "file_path": "backend/services/checkout_service.py", "priority": "high"},
            {"id": "fix_2", "description": "Fix auth middleware to raise exception instead of returning None", "code_snippet": None, "file_path": "backend/middleware/auth.py", "priority": "high"},
            {"id": "fix_3", "description": "Add integration test for checkout with expired/missing auth", "code_snippet": None, "file_path": "tests/test_checkout.py", "priority": "medium"},
        ],
        "recommended_next_steps": [
            "Deploy the null check fix immediately to stop 500 errors",
            "Investigate why auth middleware is failing silently",
            "Add monitoring for unhandled exception rates on /api/checkout",
            "Review other endpoints for similar null-safety issues",
        ],
        "confidence": 0.92,
        "user_impact": "Checkout endpoint returning 500s; ~8% of users blocked from completing purchases.",
        "github_issue_title": "P1: NullPointerException in checkout — missing session validation",
        "github_issue_labels": ["bug", "ai-oncall", "severity-p1", "area-checkout", "area-auth"],
    }


def _mock_oom(msg, source, error_logs):
    return {
        "title": "OutOfMemoryError in Data Processor — Unbounded Batch Loading",
        "severity": "P0",
        "root_cause": "The data processor loads all records into memory in process_batch() without streaming or pagination. With 100K records, the transform+enrich step creates large intermediate objects that exhaust the 4GB heap. The GC overhead (98%) confirms memory pressure before the OOM kill.",
        "evidence": [log.message for log in error_logs[:4]],
        "actionable_fixes": [
            {"id": "fix_1", "description": "Implement streaming/chunked processing instead of loading all records", "code_snippet": "def process_batch(self, records, chunk_size=1000):\n    for chunk in batched(records, chunk_size):\n        yield from (self.transform(r) for r in chunk)", "file_path": "backend/workers/data_processor.py", "priority": "high"},
            {"id": "fix_2", "description": "Increase heap size as temporary mitigation", "code_snippet": "JAVA_OPTS=-Xmx8g -Xms4g", "file_path": "docker-compose.yml", "priority": "medium"},
            {"id": "fix_3", "description": "Add memory usage monitoring and circuit breaker", "code_snippet": None, "file_path": "backend/workers/data_processor.py", "priority": "medium"},
        ],
        "recommended_next_steps": [
            "Restart affected workers immediately to restore service",
            "Deploy chunked processing fix",
            "Set up memory usage alerts at 70% and 90% thresholds",
            "Review other batch jobs for similar patterns",
        ],
        "confidence": 0.95,
        "user_impact": "Worker pods OOM-killed; batch processing pipeline stalled, downstream reports delayed.",
        "github_issue_title": "P0: OOM in data processor — unbounded memory allocation in batch processing",
        "github_issue_labels": ["bug", "ai-oncall", "severity-p0", "memory", "area-workers"],
    }


def _mock_auth_failure(msg, source, error_logs):
    return {
        "title": "Authentication Failures — Potential Brute Force Attack",
        "severity": "P2",
        "root_cause": "Expired/invalid tokens are being rejected correctly, but the high failure rate from a single IP (203.0.113.42) with 12 failed attempts in 60s suggests a brute force or credential stuffing attack. The rate limiter is detecting but not blocking the requests.",
        "evidence": [log.message for log in error_logs[:4]],
        "actionable_fixes": [
            {"id": "fix_1", "description": "Enable automatic IP blocking after rate limit threshold", "code_snippet": "if count > self.max_requests:\n    self.block_ip(ip, duration=3600)\n    raise RateLimitError(f'Blocked {ip}')", "file_path": "backend/middleware/auth.py", "priority": "high"},
            {"id": "fix_2", "description": "Add CAPTCHA or progressive delay for repeated auth failures", "code_snippet": None, "file_path": "backend/middleware/auth.py", "priority": "medium"},
            {"id": "fix_3", "description": "Set up real-time alerting for suspicious auth patterns", "code_snippet": None, "file_path": "backend/config/alerts.yaml", "priority": "medium"},
        ],
        "recommended_next_steps": [
            "Block IP 203.0.113.42 immediately if attack is confirmed",
            "Check if any accounts were compromised during the attack window",
            "Review rate limiter configuration and thresholds",
            "Enable WAF rules for credential stuffing protection",
        ],
        "confidence": 0.78,
        "user_impact": "12 failed login attempts in 60s from a single IP; legitimate users not yet impacted.",
        "github_issue_title": "P2: Authentication failures spike — suspected brute force from 203.0.113.42",
        "github_issue_labels": ["bug", "ai-oncall", "severity-p2", "area-auth", "security"],
    }


def _mock_api_failure(msg, source, error_logs):
    return {
        "title": "Payment Gateway 503 — External Service Degradation",
        "severity": "P1",
        "root_cause": "Stripe payment gateway is returning 503 (Service Unavailable) errors, causing charge failures. This is an external dependency issue. The 62% success rate and $4,127.50 in failed charges indicate significant revenue impact.",
        "evidence": [log.message for log in error_logs[:4]],
        "actionable_fixes": [
            {"id": "fix_1", "description": "Implement retry with exponential backoff for 503 responses", "code_snippet": "for attempt in range(3):\n    response = self.client.post(...)\n    if response.status_code != 503:\n        break\n    await asyncio.sleep(2 ** attempt)", "file_path": "backend/services/payment_service.py", "priority": "high"},
            {"id": "fix_2", "description": "Add fallback payment provider for high-value transactions", "code_snippet": None, "file_path": "backend/services/payment_service.py", "priority": "medium"},
            {"id": "fix_3", "description": "Queue failed payments for automatic retry when service recovers", "code_snippet": None, "file_path": "backend/workers/payment_retry.py", "priority": "high"},
        ],
        "recommended_next_steps": [
            "Check Stripe status page for ongoing incidents",
            "Enable payment retry queue to recover failed charges",
            "Notify affected customers about payment processing delays",
            "Monitor Stripe success rate and set up degradation alerts",
        ],
        "confidence": 0.85,
        "user_impact": "23 failed charges totalling $4,127.50 in last 10 min; success rate 62%.",
        "github_issue_title": "P1: Payment gateway returning 503 — revenue impact $4,127.50",
        "github_issue_labels": ["bug", "ai-oncall", "severity-p1", "area-payments", "external-dependency"],
    }


def _mock_generic(msg, source, error_logs):
    return {
        "title": "Application Error Detected",
        "severity": "P2",
        "root_cause": f"An error was detected: {msg}. Further investigation needed to determine root cause.",
        "evidence": [log.message for log in error_logs[:3]],
        "actionable_fixes": [
            {"id": "fix_1", "description": "Add detailed logging around the error location", "code_snippet": None, "file_path": source, "priority": "high"},
            {"id": "fix_2", "description": "Add error handling and graceful degradation", "code_snippet": None, "file_path": source, "priority": "medium"},
        ],
        "recommended_next_steps": [
            "Review the full stack trace and surrounding logs",
            "Check for recent deployments that may have introduced the issue",
            "Add monitoring for this error pattern",
        ],
        "confidence": 0.55,
        "user_impact": "Unknown user impact; further investigation needed.",
        "github_issue_title": f"P2: Application error — {msg[:60]}",
        "github_issue_labels": ["bug", "ai-oncall", "severity-p2"],
    }


def _format_issue_body(
    title: str,
    severity: str,
    root_cause: str,
    error_logs: list,
    fixes: list | None = None,
    user_impact: str | None = None,
    next_steps: list[str] | None = None,
) -> str:
    """Phase 1-style structured GitHub issue body."""
    fixes = fixes or []
    next_steps = next_steps or []

    # Errors Detected section
    errors_section_lines = []
    seen_msgs = set()
    error_idx = 0
    for log in error_logs[:3]:
        if log.message in seen_msgs:
            continue
        seen_msgs.add(log.message)
        error_idx += 1
        # Heuristic error type detection from message
        m = log.message
        if "NullPointer" in m or "NoneType" in m:
            etype = "NullPointerException"
        elif "Timeout" in m or "timeout" in m:
            etype = "TimeoutError"
        elif "Memory" in m or "OOM" in m:
            etype = "OutOfMemoryError"
        elif "503" in m or "ExternalAPI" in m:
            etype = "ExternalAPIError"
        elif "Auth" in m or "token" in m.lower():
            etype = "AuthenticationError"
        else:
            etype = "ApplicationError"
        errors_section_lines.append(
            f"### Error {error_idx} \u2014 {etype}\n"
            f"**Source:** `{log.source or 'unknown'}`\n"
            f"**Root cause:** {root_cause if error_idx == 1 else 'See root cause above.'}\n"
            f"**Affected code:** `{log.source or 'unknown'}`"
        )
    errors_section = "\n\n".join(errors_section_lines) if errors_section_lines else "_No structured error breakdown available._"

    # Recommended Fixes section
    fixes_section_lines = []
    for i, fix in enumerate(fixes[:5], start=1):
        desc = fix.get("description") if isinstance(fix, dict) else getattr(fix, "description", "")
        snippet = fix.get("code_snippet") if isinstance(fix, dict) else getattr(fix, "code_snippet", None)
        path = fix.get("file_path") if isinstance(fix, dict) else getattr(fix, "file_path", None)
        priority = fix.get("priority") if isinstance(fix, dict) else getattr(fix, "priority", "medium")
        block = f"### Fix {i} \u2014 {desc}"
        if path:
            block += f"\n**File:** `{path}`  "
        block += f"\n**Priority:** {priority}"
        if snippet:
            block += f"\n```\n{snippet}\n```"
        fixes_section_lines.append(block)
    fixes_section = "\n\n".join(fixes_section_lines) if fixes_section_lines else "_See actionable fixes in the LogLens dashboard._"

    # Prevention bullets
    prevention_section = (
        "\n".join(f"- {step}" for step in next_steps[:5])
        if next_steps
        else "- Add monitoring/alerting for this error pattern\n- Add regression tests covering this code path"
    )

    # Evidence (top 5)
    evidence_section = "\n".join(f"- `{log.message[:200]}`" for log in error_logs[:5])
    log_window = (
        f"{error_logs[0].timestamp} \u2192 {error_logs[-1].timestamp}"
        if error_logs
        else "unknown"
    )

    impact_line = user_impact or "User impact under investigation."

    return (
        "## Summary\n"
        f"{root_cause}\n\n"
        "## Errors Detected\n\n"
        f"{errors_section}\n\n"
        "## Evidence from Logs\n"
        f"{evidence_section}\n\n"
        "## Impact Assessment\n"
        f"**Severity:** {severity}  \n"
        f"**User impact:** {impact_line}\n\n"
        "## Recommended Fixes\n\n"
        f"{fixes_section}\n\n"
        "## Prevention Measures\n"
        f"{prevention_section}\n\n"
        "## References\n"
        f"- Log window analysed: `{log_window}`\n"
        "- See actionable fixes in the LogLens dashboard\n"
    )


def analyze(num_lines: int = 50) -> AnalysisResult:
    global _last_analysis

    raw_lines = get_raw_lines(num_lines)
    error_logs = get_error_logs(num_lines)
    provider, model_name = _detect_provider_and_model()

    if not error_logs:
        _last_analysis = AnalysisResult(
            title="No Errors Found",
            severity="P3",
            root_cause="No error or warning logs detected in the recent log window.",
            evidence=[],
            actionable_fixes=[],
            recommended_next_steps=["Continue monitoring", "No action required at this time"],
            confidence=1.0,
            user_impact="None observed.",
            github_issue_title="P3: No issues detected",
            github_issue_body="No errors found in the recent logs.",
            github_issue_labels=["ai-oncall", "severity-p3"],
            is_mock=True,
            ai_provider=provider,
            ai_model=model_name,
        )
        return _last_analysis

    code_context = get_code_context(error_logs)
    prompt = _build_prompt(raw_lines, error_logs, code_context)

    # Try LLM first
    llm_result = _call_gemini(prompt)
    is_mock = llm_result is None

    if is_mock:
        data = _mock_analysis(error_logs)
    else:
        data = llm_result

    # Parse actionable fixes
    fixes: list[ActionableFix] = []
    for fix_data in data.get("actionable_fixes", []):
        if isinstance(fix_data, dict):
            try:
                fixes.append(ActionableFix(**fix_data))
            except Exception:
                pass

    severity = data.get("severity", "P2")
    user_impact = data.get("user_impact")
    next_steps = data.get("recommended_next_steps", [])

    # Issue body: prefer LLM-supplied; otherwise build structured one
    issue_body = data.get("github_issue_body") or ""
    if not issue_body or "## Summary" not in issue_body:
        issue_body = _format_issue_body(
            title=data.get("title", ""),
            severity=severity,
            root_cause=data.get("root_cause", ""),
            error_logs=error_logs,
            fixes=data.get("actionable_fixes", []),
            user_impact=user_impact,
            next_steps=next_steps,
        )

    # Append metadata footer (Phase 1 style)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    repo = os.getenv("GITHUB_REPO", "unknown")
    confidence = float(data.get("confidence", 0.5))
    footer = (
        "\n\n---\n"
        "**Issue Metadata**\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        "| Generated by | LogLens AI On-Call |\n"
        f"| Repository | `{repo}` |\n"
        f"| Severity | `{severity}` |\n"
        f"| Confidence | `{confidence:.2f}` |\n"
        f"| AI provider | `{provider}` |\n"
        f"| AI model | `{model_name}` |\n"
        f"| Generated at | {timestamp} |\n"
        f"| Mode | `{'mock' if is_mock else 'live'}` |\n"
    )
    issue_body = issue_body.rstrip() + footer

    labels = _normalize_labels(data.get("github_issue_labels"), severity)

    _last_analysis = AnalysisResult(
        title=data.get("title", "Analysis Complete"),
        severity=severity,
        root_cause=data.get("root_cause", "See evidence for details"),
        evidence=data.get("evidence", []),
        actionable_fixes=fixes,
        recommended_next_steps=next_steps,
        confidence=confidence,
        user_impact=user_impact,
        github_issue_title=data.get("github_issue_title", data.get("title", "")),
        github_issue_body=issue_body,
        github_issue_labels=labels,
        is_mock=is_mock,
        ai_provider=provider,
        ai_model=model_name,
    )

    # Suspect commit (best-effort, never fail analysis on this)
    try:
        from suspect_commit import find_suspect_commit
        commit = find_suspect_commit(_last_analysis)
        if commit:
            _last_analysis.suspect_commit = commit
            # Append a References line about the suspect commit
            _last_analysis.github_issue_body = (
                _last_analysis.github_issue_body.rstrip()
                + f"\n\n**Suspect commit:** [`{commit.short_sha}`]({commit.html_url}) by {commit.author} \u2014 {commit.message}\n"
                + f"_Reasoning: {commit.reasoning}_\n"
            )
    except Exception as e:
        print(f"Suspect commit detection skipped: {e}")

    return _last_analysis
