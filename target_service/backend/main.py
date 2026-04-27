"""Target service: a small FastAPI app that *actually* fails on demand.

The triggered errors are caught and written to the shared LogLens log
file in the same structured format LogLens already tails, so any error
triggered here flows automatically into the LogLens dashboard.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from errors import list_scenarios, run_scenario, SCENARIOS

app = FastAPI(title="Target Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory recent-trigger feed for the target frontend
_RECENT: deque[dict[str, Any]] = deque(maxlen=20)


class Scenario(BaseModel):
    id: str
    label: str
    description: str


class ScenariosResponse(BaseModel):
    scenarios: list[Scenario]


class TriggerResponse(BaseModel):
    scenario_id: str
    label: str
    summary: str
    triggered_at: str


class RecentEntry(BaseModel):
    scenario_id: str
    label: str
    summary: str
    triggered_at: str


class RecentResponse(BaseModel):
    entries: list[RecentEntry]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "target"}


@app.get("/scenarios", response_model=ScenariosResponse)
def get_scenarios() -> ScenariosResponse:
    return ScenariosResponse(scenarios=[Scenario(**s) for s in list_scenarios()])


@app.post("/trigger/{scenario_id}", response_model=TriggerResponse)
def trigger(scenario_id: str) -> TriggerResponse:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}")
    summary = run_scenario(scenario_id)
    entry = {
        "scenario_id": scenario_id,
        "label": SCENARIOS[scenario_id]["label"],
        "summary": summary,
        "triggered_at": datetime.utcnow().isoformat() + "Z",
    }
    _RECENT.appendleft(entry)
    return TriggerResponse(**entry)


@app.get("/recent", response_model=RecentResponse)
def recent() -> RecentResponse:
    return RecentResponse(entries=[RecentEntry(**e) for e in _RECENT])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
