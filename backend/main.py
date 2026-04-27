from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import (
    HealthResponse, LogsResponse, SimulateErrorRequest, SimulateErrorResponse,
    AnalysisResult, AnalyzeRequest, CreateIssueRequest, GitHubIssueResponse,
    PatternsResponse, TimelineResponse, RunbooksResponse,
    HealthSummary, ChatRequest,
    SeveritySeriesResponse, PatternAnalysesResponse,
)
from log_writer import seed_logs, start_background_writer, simulate_error
from log_reader import read_latest_logs
from analyzer import analyze, get_last_analysis
from github_client import create_issue
from oncall_features import (
    detect_patterns, build_timeline, suggest_runbooks,
    compute_health_summary, compute_severity_series,
)
from analyzer_patterns import analyze_patterns
from chat import chat_stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_logs()
    start_background_writer()
    yield


app = FastAPI(title="LogLens", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.post("/simulate-error", response_model=SimulateErrorResponse)
def post_simulate_error(request: SimulateErrorRequest = SimulateErrorRequest()):
    error_type = simulate_error(request.error_type)
    return SimulateErrorResponse(
        success=True,
        message=f"Simulated {error_type} error written to logs",
    )


@app.get("/logs/latest", response_model=LogsResponse)
def get_latest_logs(n: int = 50):
    logs = read_latest_logs(n)
    return LogsResponse(logs=logs, total=len(logs))


@app.post("/analyze", response_model=AnalysisResult)
def post_analyze(request: AnalyzeRequest = AnalyzeRequest()):
    return analyze(request.log_lines)


@app.get("/analysis/latest", response_model=AnalysisResult | None)
def get_latest_analysis():
    return get_last_analysis()


@app.post("/issues/create", response_model=GitHubIssueResponse)
def post_create_issue(request: CreateIssueRequest):
    return create_issue(request)


@app.get("/oncall/patterns", response_model=PatternsResponse)
def get_patterns(n: int = 5000):
    return detect_patterns(n)


@app.get("/oncall/timeline", response_model=TimelineResponse)
def get_timeline(n: int = 5000):
    return build_timeline(n)


@app.get("/oncall/runbooks", response_model=RunbooksResponse)
def get_runbooks(n: int = 5000):
    return suggest_runbooks(n)


@app.get("/oncall/health-summary", response_model=HealthSummary)
def get_health_summary(n: int = 5000, window_minutes: int = 60):
    return compute_health_summary(n, window_minutes)


@app.get("/oncall/severity-series", response_model=SeveritySeriesResponse)
def get_severity_series(n: int = 5000, window_minutes: int = 60):
    return compute_severity_series(n, window_minutes)


@app.post("/oncall/analyze-patterns", response_model=PatternAnalysesResponse)
def post_analyze_patterns(n: int = 5000, force: bool = False):
    return analyze_patterns(n, force=force)


@app.post("/chat")
def post_chat(request: ChatRequest):
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        chat_stream(request.question, request.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
