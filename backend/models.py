from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class HealthResponse(BaseModel):
    status: str = "ok"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    source: Optional[str] = None


class LogsResponse(BaseModel):
    logs: list[LogEntry]
    total: int


class SimulateErrorRequest(BaseModel):
    error_type: Optional[str] = None  # e.g. "db_timeout", "null_pointer", "oom", "auth_failure"


class SimulateErrorResponse(BaseModel):
    success: bool
    message: str


class ActionableFix(BaseModel):
    id: str
    description: str
    code_snippet: Optional[str] = None
    file_path: Optional[str] = None
    priority: str = "medium"  # high, medium, low


class SuspectCommit(BaseModel):
    sha: str
    short_sha: str
    message: str
    author: str
    date: str
    html_url: str
    score: float
    reasoning: str


class AnalysisResult(BaseModel):
    title: str
    severity: str  # P0, P1, P2, P3
    root_cause: str
    evidence: list[str]
    actionable_fixes: list[ActionableFix]
    recommended_next_steps: list[str]
    confidence: float  # 0.0 - 1.0
    user_impact: Optional[str] = None  # business / user impact line
    github_issue_title: str
    github_issue_body: str
    github_issue_labels: list[str] = Field(default_factory=lambda: ["bug", "ai-oncall"])
    suspect_commit: Optional[SuspectCommit] = None
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_mock: bool = False
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None


class AnalyzeRequest(BaseModel):
    log_lines: Optional[int] = 50  # how many recent lines to analyze


class CreateIssueRequest(BaseModel):
    title: str
    body: str
    labels: list[str] = Field(default_factory=lambda: ["bug", "ai-oncall"])
    selected_fixes: list[str] = Field(default_factory=list)


class GitHubIssueResponse(BaseModel):
    success: bool
    issue_url: Optional[str] = None
    issue_number: Optional[int] = None
    preview: bool = False
    payload: Optional[dict] = None
    message: str


class ErrorPattern(BaseModel):
    pattern_id: str
    message_template: str
    count: int
    first_seen: str
    last_seen: str
    severity: str
    sample_logs: list[str]


class PatternsResponse(BaseModel):
    patterns: list[ErrorPattern]
    total_errors: int


class IncidentEvent(BaseModel):
    timestamp: str
    level: str
    message: str
    source: Optional[str] = None


class Incident(BaseModel):
    incident_id: str
    started_at: str
    ended_at: Optional[str] = None
    events: list[IncidentEvent]
    severity: str
    status: str  # active, resolved


class TimelineResponse(BaseModel):
    incidents: list[Incident]


class RunbookStep(BaseModel):
    step: int
    action: str
    command: Optional[str] = None


class Runbook(BaseModel):
    error_pattern: str
    title: str
    severity: str
    steps: list[RunbookStep]


class RunbooksResponse(BaseModel):
    runbooks: list[Runbook]


class TopErrorSummary(BaseModel):
    message_template: str
    count: int
    severity: str


class HealthSummary(BaseModel):
    error_rate_per_min: float  # average over the rolling window
    error_rate_series: list[int]  # one bucket per minute, oldest → newest
    window_minutes: int = 60
    active_incidents: int  # P0 + P1 in last hour
    severity_counts: dict[str, int] = Field(
        default_factory=lambda: {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    )
    top_error: Optional[TopErrorSummary] = None  # kept for API compatibility
    mttr_minutes: Optional[float] = None  # mean time to recover (resolved incidents)
    status: str  # "healthy" | "degraded" | "down"


class ChatRequest(BaseModel):
    question: str
    history: list[dict] = Field(default_factory=list)  # [{role, content}, ...]


class SeverityBucket(BaseModel):
    minute_offset: int  # -14 .. 0 (0 = current minute)
    P0: int = 0
    P1: int = 0
    P2: int = 0
    P3: int = 0
    total: int = 0


class SeveritySeriesResponse(BaseModel):
    buckets: list[SeverityBucket]
    window_minutes: int = 60


class PatternAnalysis(BaseModel):
    pattern_id: str
    title: str
    severity: str
    count: int
    message_template: str
    first_seen: str
    last_seen: str
    root_cause: str
    user_impact: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    actionable_fixes: list[ActionableFix] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    github_issue_title: str
    github_issue_body: str
    github_issue_labels: list[str] = Field(default_factory=list)
    is_mock: bool = False


class PatternAnalysesResponse(BaseModel):
    analyses: list[PatternAnalysis]
    total_patterns: int
    is_mock: bool = False
    mock_reason: Optional[str] = None  # short human-readable reason when is_mock is True
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
