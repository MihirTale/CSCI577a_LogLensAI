"""Suspect commit detection.

Given an analysis result (file paths from actionable_fixes + keywords from
errors), score recent commits in GITHUB_REPO and return the most likely
culprit. Best-effort: returns None on any failure or when GitHub config
is missing. Cached briefly to avoid GitHub rate-limits.
"""

from __future__ import annotations

import os
import re
import time
from typing import Optional

import httpx
from dotenv import load_dotenv

from models import AnalysisResult, SuspectCommit

load_dotenv()

GITHUB_API = "https://api.github.com"
CACHE_TTL_SECONDS = 60

_cache: dict[str, tuple[float, list[dict]]] = {}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _fetch_recent_commits(repo: str, token: str, n: int = 20) -> list[dict]:
    cache_key = f"{repo}:{n}"
    now = time.time()
    cached = _cache.get(cache_key)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    url = f"{GITHUB_API}/repos/{repo}/commits"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, headers=_headers(token), params={"per_page": n})
        if resp.status_code != 200:
            print(f"[suspect_commit] commits list failed: {resp.status_code} {resp.text[:120]}")
            return []
        commits = resp.json() or []

        # Fetch file lists for each (capped to avoid heavy traffic)
        enriched: list[dict] = []
        for commit in commits[:n]:
            sha = commit.get("sha")
            if not sha:
                continue
            files: list[str] = []
            try:
                detail = client.get(
                    f"{GITHUB_API}/repos/{repo}/commits/{sha}",
                    headers=_headers(token),
                )
                if detail.status_code == 200:
                    files = [f.get("filename", "") for f in (detail.json().get("files") or [])]
            except Exception:
                pass
            enriched.append({**commit, "_files": files})

    _cache[cache_key] = (now, enriched)
    return enriched


def _extract_keywords(analysis: AnalysisResult) -> list[str]:
    """Pull error-type / module keywords from messages and root cause."""
    text = " ".join(
        [analysis.title or "", analysis.root_cause or "", " ".join(analysis.evidence or [])]
    ).lower()
    keywords: set[str] = set()
    for token in re.findall(r"[a-z][a-z_\-]{3,}", text):
        if token in {
            "timeout", "memory", "oom", "heap", "null", "none",
            "auth", "token", "payment", "stripe", "checkout",
            "database", "connection", "pool", "race", "deadlock",
            "retry", "rate", "limit", "queue", "worker", "session",
            "cache", "redis", "kafka", "leak", "overflow",
        }:
            keywords.add(token)
    return sorted(keywords)


def _score_commit(commit: dict, file_paths: list[str], keywords: list[str], rank: int) -> tuple[float, list[str]]:
    """Score in [0..1] with explanation parts."""
    parts: list[str] = []
    score = 0.0

    # Recency: more recent = higher (rank 0 is newest of the 20 fetched)
    recency = max(0.0, 1.0 - (rank / 20.0)) * 0.3
    score += recency

    # File overlap (fix file_path basenames vs commit files)
    fix_basenames = {os.path.basename(p).lower() for p in file_paths if p}
    commit_files = [f.lower() for f in commit.get("_files", [])]
    matched_files: list[str] = []
    for cf in commit_files:
        cf_base = os.path.basename(cf)
        if cf_base in fix_basenames or any(b and b in cf for b in fix_basenames):
            matched_files.append(cf)
    if matched_files:
        score += min(0.5, 0.2 + 0.1 * len(matched_files))
        parts.append(f"modified {len(matched_files)} relevant file(s): {', '.join(matched_files[:3])}")

    # Keyword match in commit message
    msg = ((commit.get("commit") or {}).get("message") or "").lower()
    matched_kw = [kw for kw in keywords if kw in msg]
    if matched_kw:
        score += min(0.3, 0.1 * len(matched_kw))
        parts.append(f"message mentions {', '.join(matched_kw[:3])}")

    return min(1.0, score), parts


def find_suspect_commit(analysis: AnalysisResult) -> Optional[SuspectCommit]:
    token = os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPO", "")
    if not token or not repo:
        return None

    file_paths = [f.file_path for f in analysis.actionable_fixes if f.file_path]
    keywords = _extract_keywords(analysis)

    try:
        commits = _fetch_recent_commits(repo, token, n=20)
    except Exception as e:
        print(f"[suspect_commit] fetch failed: {e}")
        return None

    if not commits:
        return None

    best_idx = -1
    best_score = 0.0
    best_parts: list[str] = []
    for i, c in enumerate(commits):
        s, parts = _score_commit(c, file_paths, keywords, i)
        if s > best_score:
            best_score = s
            best_idx = i
            best_parts = parts

    # Threshold: only surface if reasonably confident
    if best_idx < 0 or best_score < 0.35:
        return None

    c = commits[best_idx]
    sha = c.get("sha", "")
    commit_obj = c.get("commit") or {}
    author_obj = commit_obj.get("author") or {}
    message = (commit_obj.get("message") or "").splitlines()[0][:120]

    reasoning = "; ".join(best_parts) if best_parts else "Most recent commit prior to error window"

    return SuspectCommit(
        sha=sha,
        short_sha=sha[:7] if sha else "",
        message=message,
        author=author_obj.get("name") or (c.get("author") or {}).get("login") or "unknown",
        date=author_obj.get("date") or "",
        html_url=c.get("html_url", ""),
        score=round(best_score, 2),
        reasoning=reasoning,
    )
