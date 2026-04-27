#!/usr/bin/env python3
"""
AI Error Analyzer — analyze_and_create_issue.py

This script is invoked by the custom GitHub Action
'.github/actions/ai-error-analyzer'.  It:

  1. Reads the aggregated pipeline error log produced by previous steps.
  2. Builds a detailed prompt and sends it to either Google Gemini (default)
     or Anthropic Claude, depending on the model name.
  3. Parses the model response to extract an issue title and body.
  4. Creates a GitHub issue in the same repository using the GitHub REST API.

Required environment variables
-------------------------------
  AI_API_KEY          – API key for the selected AI provider (set by workflow)
  AI_MODEL            – model ID (e.g. 'gemini-2.0-flash' or 'claude-3-5-sonnet-20241022')
                        Leave empty for Gemini default. Provider is inferred from model name.
  GITHUB_TOKEN        – GitHub token with issues:write permission (automatically provided)
  REPO                – '<owner>/<repo>' string (set automatically in Actions)
  RUN_ID              – GitHub Actions run ID
  COMMIT_SHA          – HEAD commit SHA

Optional environment variables
-------------------------------
  LOG_FILE     – path to the error log (default: pipeline_errors.log)
  GITHUB_OUTPUT – path to the GitHub Actions output file
"""

import datetime
import os
import sys
import traceback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_log_file(path: str) -> str:
    """Return the contents of the error log file, or an empty string."""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def ensure_labels(repo: str, token: str, labels: list[dict]) -> None:
    """
    Create GitHub issue labels if they do not already exist.
    Failures are logged but do not abort the script.
    """
    import requests

    for label in labels:
        url = f"https://api.github.com/repos/{repo}/labels"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        # 422 means the label already exists – that is fine
        resp = requests.post(url, headers=headers, json=label, timeout=15)
        if resp.status_code not in (201, 422):
            print(
                f"[WARN] Could not create label '{label['name']}': "
                f"{resp.status_code} {resp.text}",
                file=sys.stderr,
            )


def build_prompt(error_logs: str, repo: str, run_id: str, commit_sha: str) -> str:
    """
    Return the prompt sent to the AI model.

    The prompt asks the model to act as a senior engineer, analyse the logs,
    and respond in a structured format that maps directly to a GitHub issue.
    """
    short_sha = commit_sha[:7] if commit_sha and commit_sha != "unknown" else "unknown"
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""You are a senior software engineer and DevOps specialist.
A CI/CD pipeline has failed.  Analyse the error logs below and produce a
detailed GitHub issue so the engineering team can understand and fix the
problems quickly.

## Pipeline context
- Repository : {repo}
- Run ID     : {run_id}
- Commit     : {short_sha}
- Timestamp  : {timestamp}

## Error logs captured during the pipeline run

```
{error_logs}
```

## Instructions

Respond with a **GitHub-flavoured Markdown** document that will be used
verbatim as a GitHub issue.  Structure your response exactly as follows:

```
# <concise issue title – max 80 characters>

## Summary
<one-paragraph executive summary of what went wrong>

## Errors Detected

### Error 1 – <error type, e.g. MemoryError / TypeError>
**Step:** <which pipeline step failed>
**Root cause:** <explain why this error occurred>
**Affected code:** <file / function if identifiable from the logs>

*(repeat for each distinct error)*

## Impact Assessment
**Severity:** <Critical | High | Medium | Low>
<explain the business / operational impact>

## Recommended Fixes

### Fix for Error 1
```python
# Before (buggy)
...

# After (fixed)
...
```
<written explanation>

*(repeat for each error)*

## Prevention Measures
- <bullet list of process / code changes that would prevent recurrence>

## References
- [Pipeline run](https://github.com/{repo}/actions/runs/{run_id})
- Commit: `{short_sha}`
```

Do **not** add any text outside the markdown document.
"""


# ---------------------------------------------------------------------------
# AI provider calls
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, model: str, api_key: str) -> str:
    """Call the Google Gemini API and return the text response."""
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text


def call_claude(prompt: str, model: str, api_key: str) -> str:
    """Call the Anthropic Claude API and return the text response."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def call_ai(prompt: str, provider: str, model: str, api_key: str) -> str:
    """Route the request to the appropriate AI provider."""
    provider = provider.lower().strip()
    if provider == "gemini":
        return call_gemini(prompt, model, api_key)
    elif provider == "claude":
        return call_claude(prompt, model, api_key)
    else:
        raise ValueError(
            f"Unknown AI_PROVIDER: {provider!r}. "
            "Supported values are 'gemini' (default) and 'claude'."
        )


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def parse_response(response_text: str, run_id: str) -> tuple[str, str]:
    """
    Extract (title, body) from the model's markdown response.

    Expects the first line to be '# <title>'.  Falls back gracefully.
    """
    lines = response_text.strip().splitlines()
    title = f"[AI] Pipeline failure analysis – run #{run_id}"
    body_lines = lines

    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body_lines = lines[1:]

    body = "\n".join(body_lines).strip()
    return title, body


def create_github_issue(
    repo: str, title: str, body: str, token: str, labels: list[str]
) -> dict:
    """POST a new issue to the GitHub REST API."""
    import requests

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    payload = {"title": title, "body": body, "labels": labels}
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 201:
        raise RuntimeError(
            f"GitHub API returned {resp.status_code}: {resp.text}"
        )
    return resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[INFO] ============================================================")
    print("[INFO]  AI Error Analyzer — analyze_and_create_issue.py")
    print("[INFO] ============================================================")

    # --- collect environment variables ---
    api_key    = os.environ.get("AI_API_KEY", "")
    model      = os.environ.get("AI_MODEL", "").strip()
    gh_token   = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    repo       = os.environ.get("REPO", "")
    run_id     = os.environ.get("RUN_ID", "unknown")
    commit_sha = os.environ.get("COMMIT_SHA", "unknown")
    
    # Infer provider from model name and set defaults
    if not model:
        # Default to Gemini
        provider = "gemini"
        model = "gemini-3-flash-preview"
    elif "claude" in model.lower():
        provider = "claude"
    else:
        provider = "gemini"
    log_file   = os.environ.get("LOG_FILE", "pipeline_errors.log")
    github_output = os.environ.get("GITHUB_OUTPUT", "")

    print(f"[INFO] AI provider : {provider}")
    print(f"[INFO] AI model    : {model}")

    # --- validate required secrets ---
    missing = []
    if not api_key:
        missing.append("AI_API_KEY")
    if not gh_token:
        missing.append("GH_TOKEN / GITHUB_TOKEN")
    if not repo:
        missing.append("REPO")
    if missing:
        print(
            f"[ERROR] Missing required environment variable(s): {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- read logs ---
    print(f"[INFO] Reading error log: {log_file}")
    error_logs = read_log_file(log_file)

    if not error_logs.strip():
        print("[INFO] No errors found in the pipeline log.  Skipping issue creation.")
        if github_output:
            with open(github_output, "a") as fh:
                fh.write("issue-url=\n")
        return

    print(f"[INFO] Log size: {len(error_logs):,} bytes")

    # --- call AI model ---
    print(f"[INFO] Sending logs to {provider} model: {model}")
    prompt = build_prompt(error_logs, repo, run_id, commit_sha)
    try:
        response_text = call_ai(prompt, provider, model, api_key)
    except Exception as exc:
        print(f"[ERROR] AI API call failed: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Received analysis from {provider}.")

    # --- parse response ---
    title, body = parse_response(response_text, run_id)
    short_sha = commit_sha[:7] if commit_sha != "unknown" else "unknown"
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Append pipeline metadata footer
    footer = (
        "\n\n---\n"
        "**Pipeline Metadata**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| Repository | `{repo}` |\n"
        f"| Run | [#{run_id}](https://github.com/{repo}/actions/runs/{run_id}) |\n"
        f"| Commit | `{short_sha}` |\n"
        f"| AI provider | `{provider}` |\n"
        f"| AI model | `{model}` |\n"
        f"| Generated | {timestamp} |\n"
    )
    full_body = body + footer

    # --- ensure labels exist ---
    label_defs = [
        {"name": "bug",              "color": "d73a4a", "description": "Something isn't working"},
        {"name": "ai-analysis",      "color": "0075ca", "description": "Created by AI error analysis"},
        {"name": "pipeline-failure", "color": "e4e669", "description": "CI/CD pipeline failure"},
    ]
    label_names = [lbl["name"] for lbl in label_defs]
    print("[INFO] Ensuring issue labels exist...")
    ensure_labels(repo, gh_token, label_defs)

    # --- create issue ---
    print(f"[INFO] Creating GitHub issue: {title!r}")
    try:
        issue = create_github_issue(repo, title, full_body, gh_token, label_names)
    except Exception as exc:
        print(f"[ERROR] Failed to create GitHub issue: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    issue_url = issue.get("html_url", "")
    issue_number = issue.get("number", "?")
    print(f"[INFO] Issue created successfully: #{issue_number}")
    print(f"[INFO]    {issue_url}")

    # Expose the issue URL as a step output
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"issue-url={issue_url}\n")


if __name__ == "__main__":
    main()
