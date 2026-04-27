"""Chat-with-logs: SSE streaming Q&A grounded on the recent log buffer.

Uses Gemini's streaming API when AI_API_KEY is configured; otherwise falls
back to a deterministic mock answer based on simple keyword matching.
"""

from __future__ import annotations

import json
import os
import time
from typing import Iterable, Iterator

from dotenv import load_dotenv

from log_reader import read_latest_logs, get_error_logs
from analyzer import get_last_analysis
from oncall_features import compute_health_summary

load_dotenv()


def _sse(data: dict) -> bytes:
    return f"data: {json.dumps(data)}\n\n".encode("utf-8")


def _done() -> bytes:
    return b"data: [DONE]\n\n"


def _build_context() -> str:
    logs = read_latest_logs(100)
    error_logs = get_error_logs(100)
    last_analysis = get_last_analysis()
    health = None
    try:
        health = compute_health_summary(600)
    except Exception:
        pass

    parts: list[str] = []
    if health is not None:
        parts.append(
            f"## Service health\n"
            f"- Status: {health.status}\n"
            f"- Error rate (last 15m avg): {health.error_rate_per_min}/min\n"
            f"- Active incidents (last 60m, P0+P1): {health.active_incidents}\n"
            + (f"- Top error: {health.top_error.message_template} (\u00d7{health.top_error.count}, {health.top_error.severity})\n" if health.top_error else "")
            + (f"- MTTR: {health.mttr_minutes} min\n" if health.mttr_minutes is not None else "")
        )

    if last_analysis is not None:
        parts.append(
            f"## Last analysis\n"
            f"- Title: {last_analysis.title}\n"
            f"- Severity: {last_analysis.severity}\n"
            f"- Confidence: {last_analysis.confidence:.2f}\n"
            f"- Root cause: {last_analysis.root_cause}\n"
            + (f"- User impact: {last_analysis.user_impact}\n" if last_analysis.user_impact else "")
        )

    if error_logs:
        parts.append("## Recent error/warn lines (top 20)")
        for log in error_logs[:20]:
            parts.append(f"- [{log.timestamp}] {log.level} {log.message[:200]}")

    if logs:
        parts.append("\n## Last 30 raw log lines")
        for log in logs[-30:]:
            parts.append(f"[{log.timestamp}] {log.level} {log.message[:200]}")

    return "\n".join(parts) if parts else "No log data available."


def _build_prompt(question: str, history: list[dict], context: str) -> str:
    history_text = "\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in history[-6:]
    )
    return f"""You are LogLens, an AI on-call assistant. Answer the engineer's question using ONLY the log/analysis context below. Be concise (1\u20133 short paragraphs or a small bullet list). Use markdown for code, file paths, and lists. If the context lacks the info, say so.

# Context (read-only, do not echo back wholesale)
{context}

# Conversation so far
{history_text}

# Question
{question}

# Answer
"""


def _mock_answer(question: str, context: str) -> str:
    q = question.lower()
    if "checkout" in q:
        return "From the recent logs, checkout requests are failing because of a NullPointerException in `checkout_service.py` \u2014 the auth middleware is passing a `None` session and the service does not null-check it. Fix: add a null guard for `session.user_id` and have the middleware raise a 401 instead of silently returning `None`."
    if "auth" in q or "login" in q:
        return "I see a spike of authentication failures (12 failures in 60s) coming from a single IP. This looks like a brute-force attempt rather than a real outage. Recommend: enable IP blocking after the rate-limit threshold, add CAPTCHA for repeated failures, and confirm no accounts were compromised."
    if "memory" in q or "oom" in q:
        return "There is an OutOfMemoryError in the data processor. The `process_batch` worker loads all records into memory at once. Fix: switch to chunked / streaming processing and add memory alerts at 70% / 90% thresholds."
    if "payment" in q or "stripe" in q:
        return "Stripe is returning 503s, causing failed charges. Recommended: enable retry with exponential backoff for 503 responses, queue failed payments for automatic retry, and check status.stripe.com for an ongoing incident."
    if "summari" in q or "last" in q:
        return "**Recent activity (last 15 min):** elevated error rate driven mostly by database connection timeouts and a few 503s from the payment gateway. No P0 incidents currently active. Nothing requires immediate paging \u2014 keep monitoring the connection-pool metrics."
    return "I do not have enough information in the recent log window to answer that confidently. Try asking about checkout, auth, memory, payments, or the last few minutes \u2014 or click \u201cAnalyze\u201d to run a structured analysis first."


_GEMINI_FALLBACKS = ["gemini-2.0-flash", "gemini-1.5-flash"]


def _stream_gemini(prompt: str) -> Iterator[str]:
    api_key = os.getenv("AI_API_KEY", "")
    primary = (os.getenv("AI_MODEL") or "gemini-2.0-flash").strip()
    if not api_key:
        return iter(())
    candidates = [primary] + [m for m in _GEMINI_FALLBACKS if m != primary]
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"[chat] gemini SDK unavailable: {e}")
        return iter(())
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt, stream=True)
            if model_name != primary:
                print(
                    f"[chat] WARNING: AI_MODEL='{primary}' rejected; "
                    f"used fallback '{model_name}'."
                )

            def gen() -> Iterator[str]:
                for chunk in response:
                    try:
                        text = chunk.text  # type: ignore[attr-defined]
                    except Exception:
                        text = ""
                    if text:
                        yield text

            return gen()
        except Exception as e:
            print(f"[chat] '{model_name}' failed: {e}")
            continue
    return iter(())


def _fake_stream(text: str, delay: float = 0.012) -> Iterable[str]:
    """Token-by-token simulated stream for the mock answer."""
    # Stream in small word chunks for a natural feel
    words = text.split(" ")
    for i, w in enumerate(words):
        yield (w if i == 0 else " " + w)
        time.sleep(delay)


def chat_stream(question: str, history: list[dict]):
    """Generator yielding SSE bytes."""
    context = _build_context()
    prompt = _build_prompt(question, history, context)

    used_llm = False
    try:
        for delta in _stream_gemini(prompt):
            used_llm = True
            yield _sse({"delta": delta})
    except Exception as e:
        print(f"[chat] streaming error: {e}")

    if used_llm:
        yield _done()
        return

    # Fallback: mock answer with simulated streaming
    answer = _mock_answer(question, context)
    for d in _fake_stream(answer):
        yield _sse({"delta": d})
    yield _done()
