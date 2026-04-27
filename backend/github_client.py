import os
import httpx
from dotenv import load_dotenv
from models import CreateIssueRequest, GitHubIssueResponse

load_dotenv()

GITHUB_API = "https://api.github.com"

# Curated label palette: name -> (color hex without #, description)
LABEL_PALETTE: dict[str, tuple[str, str]] = {
    "bug": ("d73a4a", "Something isn't working"),
    "ai-oncall": ("0075ca", "Created by LogLens AI On-Call"),
    "severity-p0": ("b60205", "Critical \u2014 immediate action"),
    "severity-p1": ("d93f0b", "High \u2014 same-day fix"),
    "severity-p2": ("fbca04", "Medium \u2014 sprint priority"),
    "severity-p3": ("0e8a16", "Low \u2014 backlog"),
    "performance": ("c5def5", "Performance / latency"),
    "memory": ("c5def5", "Memory / OOM"),
    "race-condition": ("c5def5", "Race condition / flakiness"),
    "security": ("ee0701", "Security related"),
    "external-dependency": ("d4c5f9", "Caused by an external service"),
    "area-database": ("bfdadc", "Database area"),
    "area-auth": ("bfdadc", "Auth area"),
    "area-payments": ("bfdadc", "Payments area"),
    "area-checkout": ("bfdadc", "Checkout area"),
    "area-workers": ("bfdadc", "Background workers"),
}
DEFAULT_LABEL_COLOR = "ededed"


def _get_config():
    token = os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPO", "")
    return token, repo


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _ensure_labels(repo: str, token: str, labels: list[str], client: httpx.Client) -> None:
    """Best-effort: create missing labels with sensible colors. Never raises."""
    for name in labels:
        if not name:
            continue
        color, description = LABEL_PALETTE.get(name, (DEFAULT_LABEL_COLOR, ""))
        url = f"{GITHUB_API}/repos/{repo}/labels"
        payload = {"name": name, "color": color, "description": description}
        try:
            resp = client.post(url, json=payload, headers=_headers(token))
            # 201 = created; 422 = already exists \u2014 both fine
            if resp.status_code not in (201, 422):
                print(f"[WARN] Could not ensure label {name!r}: {resp.status_code} {resp.text[:120]}")
        except Exception as e:
            print(f"[WARN] Label ensure error for {name!r}: {e}")


def create_issue(request: CreateIssueRequest) -> GitHubIssueResponse:
    token, repo = _get_config()

    # Append selected fixes to body if provided
    body = request.body
    if request.selected_fixes:
        fixes_text = "\n".join(f"- [x] {fix}" for fix in request.selected_fixes)
        body += f"\n\n### Selected Fixes to Implement\n{fixes_text}"

    # Normalize labels: lowercase, dedupe, strip
    labels: list[str] = []
    seen: set[str] = set()
    for raw in request.labels:
        lbl = (raw or "").strip().lower().replace(" ", "-")
        if lbl and lbl not in seen:
            seen.add(lbl)
            labels.append(lbl)

    payload = {
        "title": request.title,
        "body": body,
        "labels": labels,
    }

    # If not configured, return preview
    if not token or not repo:
        return GitHubIssueResponse(
            success=True,
            preview=True,
            payload=payload,
            message="GitHub not configured \u2014 returning preview payload. Set GITHUB_TOKEN and GITHUB_REPO in .env to create real issues.",
        )

    # Create real issue
    try:
        with httpx.Client(timeout=20) as client:
            # Ensure labels exist (best-effort, won't fail issue creation)
            _ensure_labels(repo, token, labels, client)

            url = f"{GITHUB_API}/repos/{repo}/issues"
            response = client.post(url, json=payload, headers=_headers(token))
            response.raise_for_status()
            data = response.json()

        return GitHubIssueResponse(
            success=True,
            issue_url=data.get("html_url"),
            issue_number=data.get("number"),
            payload=payload,
            message=f"Issue #{data.get('number')} created successfully",
        )
    except httpx.HTTPStatusError as e:
        return GitHubIssueResponse(
            success=False,
            payload=payload,
            message=f"GitHub API error: {e.response.status_code} \u2014 {e.response.text[:200]}",
        )
    except Exception as e:
        return GitHubIssueResponse(
            success=False,
            payload=payload,
            message=f"Failed to create issue: {str(e)}",
        )
