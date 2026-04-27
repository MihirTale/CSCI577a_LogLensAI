"""Per-pattern analysis.

Detects error patterns (via `oncall_features.detect_patterns`) and produces a
structured `PatternAnalysis` for each. Tries one batched Gemini call first;
falls back to deterministic per-pattern mocks (re-using analyzer's mock helpers)
when the LLM is unavailable or returns garbage.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any

from dotenv import load_dotenv

from models import (
    ActionableFix,
    PatternAnalysis,
    PatternAnalysesResponse,
    LogEntry,
)
from log_reader import read_latest_logs
from oncall_features import detect_patterns
from analyzer import (
    _detect_provider_and_model,
    _format_issue_body,
    _normalize_labels,
    _mock_db_timeout,
    _mock_null_pointer,
    _mock_oom,
    _mock_auth_failure,
    _mock_api_failure,
    _mock_generic,
)

load_dotenv()

SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _logs_for_pattern(pattern_template: str, all_logs: list[LogEntry]) -> list[LogEntry]:
    """Return the actual LogEntry objects whose normalized form matches the pattern."""
    from oncall_features import _normalize_message

    target = pattern_template
    matches = [log for log in all_logs if _normalize_message(log.message) == target]
    if matches:
        return matches
    # Fallback: substring on the first 8 distinctive tokens of the template
    tokens = re.findall(r"[A-Za-z]{4,}", pattern_template)[:6]
    if not tokens:
        return matches
    return [log for log in all_logs if all(t in log.message for t in tokens)]


def _pick_mock_fn(message: str):
    """Choose a mock generator based on keywords in the message."""
    m = message.lower()
    if "timeout" in m or "connection" in m:
        return _mock_db_timeout
    if "none" in m or "null" in m or "attribute" in m:
        return _mock_null_pointer
    if "memory" in m or "oom" in m or "heap" in m:
        return _mock_oom
    if "auth" in m or "token" in m or "brute" in m:
        return _mock_auth_failure
    if "payment" in m or "503" in m or "stripe" in m:
        return _mock_api_failure
    return _mock_generic


def _mock_pattern_analysis(pattern, pattern_logs: list[LogEntry]) -> dict:
    sample = pattern_logs[0] if pattern_logs else None
    msg = sample.message if sample else pattern.message_template
    source = sample.source if sample else "unknown"
    fn = _pick_mock_fn(msg)
    return fn(msg, source, pattern_logs or [])


# ---------------------------------------------------------------------------
# LLM batched call
# ---------------------------------------------------------------------------


def _build_batched_prompt(patterns_with_logs: list[tuple]) -> str:
    """Build a single prompt asking the LLM to produce a JSON array of analyses."""
    blocks = []
    for i, (pat, logs) in enumerate(patterns_with_logs, start=1):
        sample_lines = "\n".join(f"  - [{l.timestamp}] {l.level} {l.message[:200]}" for l in logs[:5])
        blocks.append(
            f"## Pattern {i} (id: {pat.pattern_id})\n"
            f"- count: {pat.count}\n"
            f"- heuristic_severity: {pat.severity}\n"
            f"- first_seen: {pat.first_seen}\n"
            f"- last_seen: {pat.last_seen}\n"
            f"- template: {pat.message_template}\n"
            f"- sample logs:\n{sample_lines or '  (none)'}"
        )
    bundle = "\n\n".join(blocks)
    return (
        "You are LogLens, an AI on-call assistant. For EACH error pattern below, "
        "produce a concise structured analysis. Be specific and actionable; do not "
        "echo back the template verbatim. Respond with a JSON ARRAY (no prose, no "
        "markdown fences) where each element matches the schema:\n"
        "{\n"
        '  "pattern_id": "<copy from input>",\n'
        '  "title": "<short title>",\n'
        '  "severity": "P0|P1|P2|P3",\n'
        '  "root_cause": "<2-3 sentences, true root cause not symptom>",\n'
        '  "user_impact": "<1 sentence on user/business impact>",\n'
        '  "evidence": ["<3-4 strongest log excerpts>"],\n'
        '  "actionable_fixes": [\n'
        '    {"id": "fix_1", "description": "...", "code_snippet": "...|null", "file_path": "...|null", "priority": "high|medium|low"}\n'
        "  ],\n"
        '  "recommended_next_steps": ["...", "..."],\n'
        '  "confidence": 0.0-1.0,\n'
        '  "github_issue_title": "P<sev>: <title>",\n'
        '  "github_issue_labels": ["bug","ai-oncall","severity-pX","area-..."]\n'
        "}\n\n"
        "PATTERNS:\n\n" + bundle
    )


_GEMINI_FALLBACKS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]

# Module-level state so callers can read why the last call fell back to mock
_last_failure: dict = {"reason": None}


def _summarize_error(model_name: str, exc: Exception) -> str:
    """Convert a noisy Gemini exception into a one-line, user-friendly summary."""
    msg = str(exc)
    head = msg.split("\n", 1)[0][:200]
    if "429" in msg or "quota" in msg.lower():
        return f"{model_name}: quota exceeded (free-tier limit)"
    if "404" in msg or "not found" in msg.lower():
        return f"{model_name}: model not available"
    if "401" in msg or "403" in msg or "api key" in msg.lower():
        return f"{model_name}: invalid / unauthorized API key"
    return f"{model_name}: {head}"


def _call_gemini_batched(prompt: str) -> list[dict] | None:
    _last_failure["reason"] = None
    api_key = os.getenv("AI_API_KEY", "")
    primary = (os.getenv("AI_MODEL") or "gemini-2.5-flash").strip()
    if not api_key:
        _last_failure["reason"] = "AI_API_KEY is not set"
        return None

    candidates = [primary] + [m for m in _GEMINI_FALLBACKS if m != primary]
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
    except Exception as e:
        _last_failure["reason"] = f"google-generativeai SDK unavailable: {e}"
        print(f"[analyzer_patterns] Gemini SDK unavailable: {e}")
        return None

    failures: list[str] = []
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = (response.text or "").strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            data = json.loads(text)
            if isinstance(data, dict) and "analyses" in data:
                data = data["analyses"]
            if not isinstance(data, list):
                failures.append(f"{model_name}: unexpected response shape")
                continue
            if model_name != primary:
                print(
                    f"[analyzer_patterns] WARNING: AI_MODEL='{primary}' rejected; "
                    f"used fallback '{model_name}' instead. Update your .env to silence this."
                )
            return data
        except Exception as e:
            summary = _summarize_error(model_name, e)
            failures.append(summary)
            print(f"[analyzer_patterns] {summary}")
            continue
    _last_failure["reason"] = "All Gemini models failed → " + "; ".join(failures)
    return None


# ---------------------------------------------------------------------------
# Cache (so repeated polling/refreshes don't burn LLM quota)
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {"key": None, "result": None, "ts": None}
_CACHE_TTL = timedelta(seconds=30)


def _cache_key(patterns) -> str:
    return "|".join(f"{p.pattern_id}:{p.count}" for p in patterns)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def analyze_patterns(num_lines: int = 5000, force: bool = False) -> PatternAnalysesResponse:
    provider, model_name = _detect_provider_and_model()
    patterns_resp = detect_patterns(num_lines)
    patterns = patterns_resp.patterns

    if not patterns:
        return PatternAnalysesResponse(
            analyses=[], total_patterns=0, is_mock=False,
            ai_provider=provider, ai_model=model_name,
        )

    # Cache check
    key = _cache_key(patterns)
    now = datetime.utcnow()
    cached = _cache.get("result")
    cached_ts = _cache.get("ts")
    if not force and cached is not None and cached_ts and (now - cached_ts) < _CACHE_TTL and _cache.get("key") == key:
        return cached  # type: ignore[return-value]

    all_logs = read_latest_logs(num_lines)
    patterns_with_logs = [(p, _logs_for_pattern(p.message_template, all_logs)) for p in patterns]

    # Try batched LLM call
    llm_data = _call_gemini_batched(_build_batched_prompt(patterns_with_logs))
    failure_reason = _last_failure.get("reason")

    # Index llm responses by pattern_id where possible
    by_id: dict[str, dict] = {}
    if llm_data:
        for entry in llm_data:
            if isinstance(entry, dict) and entry.get("pattern_id"):
                by_id[str(entry["pattern_id"])] = entry

    analyses: list[PatternAnalysis] = []
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    repo = os.getenv("GITHUB_REPO", "unknown")

    for pat, pat_logs in patterns_with_logs:
        data = by_id.get(pat.pattern_id)
        per_is_mock = data is None
        if data is None:
            data = _mock_pattern_analysis(pat, pat_logs)

        # Parse fixes
        fixes: list[ActionableFix] = []
        for fd in data.get("actionable_fixes", []):
            if isinstance(fd, dict):
                try:
                    fixes.append(ActionableFix(**fd))
                except Exception:
                    pass

        severity = data.get("severity") or pat.severity
        user_impact = data.get("user_impact")
        next_steps = data.get("recommended_next_steps", [])
        root_cause = data.get("root_cause", f"Pattern observed {pat.count} time(s).")
        title = data.get("title") or f"{severity}: {pat.message_template[:80]}"

        # Build issue body
        issue_body = _format_issue_body(
            title=title,
            severity=severity,
            root_cause=root_cause,
            error_logs=pat_logs,
            fixes=data.get("actionable_fixes", []),
            user_impact=user_impact,
            next_steps=next_steps,
        )
        confidence = float(data.get("confidence", 0.6 if not per_is_mock else 0.55))
        footer = (
            "\n\n---\n"
            "**Issue Metadata**\n\n"
            "| Field | Value |\n"
            "|-------|-------|\n"
            "| Generated by | LogLens AI On-Call (per-pattern) |\n"
            f"| Repository | `{repo}` |\n"
            f"| Pattern ID | `{pat.pattern_id}` |\n"
            f"| Occurrences | {pat.count} |\n"
            f"| Severity | `{severity}` |\n"
            f"| Confidence | `{confidence:.2f}` |\n"
            f"| AI provider | `{provider}` |\n"
            f"| AI model | `{model_name}` |\n"
            f"| Generated at | {timestamp} |\n"
            f"| Mode | `{'mock' if per_is_mock else 'live'}` |\n"
        )
        issue_body = issue_body.rstrip() + footer

        labels = _normalize_labels(data.get("github_issue_labels"), severity)

        analyses.append(PatternAnalysis(
            pattern_id=pat.pattern_id,
            title=title,
            severity=severity,
            count=pat.count,
            message_template=pat.message_template,
            first_seen=pat.first_seen,
            last_seen=pat.last_seen,
            root_cause=root_cause,
            user_impact=user_impact,
            evidence=data.get("evidence", []) or [l.message for l in pat_logs[:4]],
            actionable_fixes=fixes,
            recommended_next_steps=next_steps,
            confidence=confidence,
            github_issue_title=data.get("github_issue_title", title),
            github_issue_body=issue_body,
            github_issue_labels=labels,
            is_mock=per_is_mock,
        ))

    # Sort by severity (P0 → P1 → P2 → P3), then by count desc
    analyses.sort(key=lambda a: (SEVERITY_RANK.get(a.severity, 9), -a.count))

    # Response-level is_mock is true only if EVERY pattern fell back to mocks
    response_is_mock = bool(analyses) and all(a.is_mock for a in analyses)

    result = PatternAnalysesResponse(
        analyses=analyses,
        total_patterns=len(analyses),
        is_mock=response_is_mock,
        mock_reason=failure_reason if response_is_mock else None,
        ai_provider=provider,
        ai_model=model_name,
    )
    _cache["key"] = key
    _cache["result"] = result
    _cache["ts"] = now
    return result
