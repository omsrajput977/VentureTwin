import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Literal

# Load local .env into os.environ if present
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip().strip('"').strip("'")
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from data.loader import get_company_snapshot, load_company_data, load_seeded_decisions
from state.schemas import Decision, Report, DecisionRecord, Event
from state.shared_state import WorkflowState
from state.event_bus import EventBus
from orchestrator.parser import parse_decision_query
from orchestrator.supervisor import Supervisor
from orchestrator.checkpointer import SQLiteCheckpointer

app = FastAPI(
    title="VentureTwin API",
    description="Operational Digital Twin & AI Flight Simulator for SaaS CEOs",
    version="0.1.0"
)

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost:8000,http://127.0.0.1:5173,http://localhost:3000"
cors_origins_env = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session stores for active decisions
active_workflows: Dict[str, WorkflowState] = {}
active_supervisors: Dict[str, Supervisor] = {}
decision_records_store: List[Dict[str, Any]] = []

class HealthStatus(BaseModel):
    status: str
    version: str
    llm_mode: str
    provider: str
    model: str
    probe_latency_ms: Optional[float] = None

class DecisionRequest(BaseModel):
    query: str
    constraints: Optional[Dict[str, Any]] = None

class FailureInjectionRequest(BaseModel):
    agent: str
    mode: Literal["timeout", "exception", "bad_output"]
    persist: bool = False
    fail_attempts: int = 3

class ApprovalRequest(BaseModel):
    action: Literal["approve", "reject", "request_changes"]
    notes: Optional[str] = None

@app.get("/")
async def root():
    dist_index = os.path.join(os.path.dirname(__file__), "..", "ui", "dist", "index.html")
    if os.path.exists(dist_index):
        return FileResponse(dist_index)
    return {
        "name": "VentureTwin API",
        "description": "SwarmFlow Multi-Agent Task Coordination Engine",
        "status": "healthy"
    }

# Mount static frontend assets if available
dist_assets = os.path.join(os.path.dirname(__file__), "..", "ui", "dist", "assets")
if os.path.exists(dist_assets):
    app.mount("/assets", StaticFiles(directory=dist_assets), name="assets")

@app.get("/api/health", response_model=HealthStatus)
async def health(probe: bool = False):
    import time
    llm_mode = os.getenv("LLM_MODE", "mock").lower()
    provider = os.getenv("LLM_PROVIDER", "mock")
    model = os.getenv("LLM_MODEL", "mock-agent-v1")
    probe_latency: Optional[float] = None
    
    if llm_mode in ["real", "record"]:
        if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real/record and provider is gemini but GEMINI_API_KEY is not set."
            )
        elif provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real/record and provider is openai but OPENAI_API_KEY is not set."
            )
        elif provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real/record and provider is anthropic but ANTHROPIC_API_KEY is not set."
            )
        elif provider == "cerebras" and not (os.getenv("CEREBRAS_API_KEY") or os.getenv("LLM_API_KEY")):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real/record and provider is cerebras but CEREBRAS_API_KEY is not set."
            )
        elif provider == "groq" and not (os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real/record and provider is groq but GROQ_API_KEY is not set."
            )
        elif provider == "openai_compatible" and not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real/record and provider is openai_compatible but LLM_API_KEY is not set."
            )

        if probe:
            try:
                from agents.llm_client import LLMClient
                from pydantic import BaseModel
                class _ProbeSchema(BaseModel):
                    status: str
                probe_client = LLMClient(mode=llm_mode, provider=provider, model=model)
                t0 = time.time()
                await probe_client.call('Return JSON: {"status": "ok"}', _ProbeSchema)
                probe_latency = round((time.time() - t0) * 1000, 2)
            except Exception as probe_err:
                raise HTTPException(status_code=500, detail=f"LLM probe failed: {probe_err}")
            
    return HealthStatus(
        status="ok",
        version="0.1.0",
        llm_mode=llm_mode,
        provider=provider,
        model=model,
        probe_latency_ms=probe_latency
    )

@app.get("/api/company")
async def get_company():
    """Returns the company snapshot for NimbusDesk with synthetic data badge."""
    return get_company_snapshot()

@app.post("/api/decisions")
async def submit_decision(req: DecisionRequest, background_tasks: BackgroundTasks):
    """Submits a strategic decision query and launches the multi-agent workflow."""
    decision = parse_decision_query(req.query, req.constraints, allow_all=True)
    if decision.type == "unsupported":
        raise HTTPException(
            status_code=400,
            detail=decision.objective
        )
    
    supervisor = Supervisor()
    active_supervisors[decision.id] = supervisor

    # Run workflow asynchronously
    async def run_flow():
        state = await supervisor.execute_workflow(decision)
        active_workflows[decision.id] = state

    background_tasks.add_task(run_flow)

    return {
        "decision_id": decision.id,
        "type": decision.type,
        "question": decision.question,
        "objective": decision.objective,
        "status": "started"
    }

@app.get("/api/decisions/{decision_id}")
async def get_decision_status(decision_id: str):
    """Returns status, task plan, findings, and events for a decision."""
    state = active_workflows.get(decision_id)
    if not state:
        supervisor = active_supervisors.get(decision_id)
        if supervisor and getattr(supervisor, "current_state", None):
            state = supervisor.current_state
        elif supervisor:
            return {"decision_id": decision_id, "status": "running"}
        else:
            raise HTTPException(status_code=404, detail="Decision not found")

    return {
        "decision_id": decision_id,
        "status": state.status,
        "round": state.round,
        "degraded_agents": state.degraded_agents,
        "tasks": {k: v.model_dump() for k, v in state.tasks.items()},
        "findings": [f.model_dump() for f in state.findings],
        "conflicts": [c.model_dump() for c in state.conflicts],
        "events_count": len(state.events)
    }

@app.get("/api/decisions/{decision_id}/stream")
async def stream_decision_events(decision_id: str):
    """Server-Sent Events (SSE) stream for live agent execution telemetry."""
    supervisor = active_supervisors.get(decision_id)
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not active for decision")

    async def event_generator():
        queue: asyncio.Queue[Event] = asyncio.Queue()

        def on_event(evt: Event):
            queue.put_nowait(evt)

        supervisor.event_bus.subscribe(on_event)

        # Stream existing events first
        for past_evt in supervisor.event_bus.get_events():
            yield f"data: {past_evt.model_dump_json()}\n\n"

        try:
            while True:
                evt = await queue.get()
                yield f"data: {evt.model_dump_json()}\n\n"
                if evt.type in ["report_ready", "verification_failed"]:
                    break
        finally:
            supervisor.event_bus.unsubscribe(on_event)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/decisions/{decision_id}/inject-failure")
async def inject_failure(decision_id: str, req: FailureInjectionRequest):
    """Injects a simulated runtime fault (timeout, exception, bad_output) into an agent."""
    supervisor = active_supervisors.get(decision_id)
    if not supervisor:
        raise HTTPException(status_code=404, detail="Active supervisor not found for decision")

    supervisor.inject_failure(req.agent, req.mode, persist=req.persist, fail_attempts=req.fail_attempts)
    return {
        "decision_id": decision_id,
        "agent": req.agent,
        "mode": req.mode,
        "persist": req.persist,
        "status": "failure_injected"
    }

@app.get("/api/decisions/{decision_id}/report")
async def get_decision_report(decision_id: str):
    """Returns the consolidated 10-section decision report."""
    state = active_workflows.get(decision_id)
    if not state:
        supervisor = active_supervisors.get(decision_id)
        if supervisor and getattr(supervisor, "current_state", None):
            state = supervisor.current_state
    if not state:
        raise HTTPException(status_code=404, detail="Decision not found or still processing")
    if not state.report:
        raise HTTPException(status_code=400, detail="Report generation not yet completed")

    return state.report.model_dump()

@app.get("/api/reports/latest")
async def get_latest_report():
    """Returns the most recent completed decision report."""
    for w in reversed(list(active_workflows.values())):
        if w.report:
            return w.report.model_dump()
    kg_path = os.path.join(os.path.dirname(__file__), "..", "data", "known_good_run.json")
    if os.path.exists(kg_path):
        with open(kg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "report" in data and data["report"]:
                return data["report"]
    raise HTTPException(status_code=404, detail="No completed report found")

@app.post("/api/decisions/{decision_id}/approve")
async def approve_decision(decision_id: str, req: ApprovalRequest):
    """Human-in-the-loop gate: stores decision record on approval."""
    state = active_workflows.get(decision_id)
    if not state or not state.report:
        raise HTTPException(status_code=404, detail="Report not available for approval")

    top_strategy = state.report.sections.get("strategies_compared", [{}])[0].get("strategy", "Unknown")
    
    record = {
        "decision_id": decision_id,
        "action": req.action,
        "chosen_strategy": top_strategy,
        "notes": req.notes,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "predicted_metrics": state.report.sections.get("scenario_table", [{}])[0],
        "status": "awaiting_outcome" if req.action == "approve" else req.action
    }
    decision_records_store.append(record)
    return {"status": "recorded", "decision_record": record}

def compute_calibration_summary(seeded_decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes past decision calibration error and primary drift factor dynamically."""
    if not seeded_decisions:
        return {
            "total_evaluated_past_decisions": 0,
            "mean_arr_error_pct": 0.0,
            "most_common_drift_factor": "none"
        }
    pct_errors = []
    drift_reasons = []
    for d in seeded_decisions:
        cal = d.get("calibration_error", {})
        for k, v in cal.items():
            if "error_pct" in k and isinstance(v, (int, float)):
                pct_errors.append(abs(float(v)))
        if "most_wrong_assumption" in cal:
            drift_reasons.append(cal["most_wrong_assumption"])

    mean_err = round(sum(pct_errors) / len(pct_errors), 1) if pct_errors else 0.0
    from collections import Counter
    most_common = Counter(drift_reasons).most_common(1)[0][0] if drift_reasons else "none"

    return {
        "total_evaluated_past_decisions": len(seeded_decisions),
        "mean_arr_error_pct": mean_err,
        "most_common_drift_factor": most_common
    }

@app.get("/api/history")
async def get_history():
    """Returns seeded past decisions with calibration error plus new approved decisions."""
    seeded = load_seeded_decisions()
    summary = compute_calibration_summary(seeded)
    return {
        "seeded_decisions": seeded,
        "live_approved_decisions": decision_records_store,
        "calibration_summary": summary
    }

@app.get("/api/graph")
async def get_company_graph():
    """Returns Company Intelligence Graph nodes and edges for React Flow."""
    data = load_company_data()
    fin = data["financials"]
    cust = data["customers"]
    
    nodes = [
        {"id": "mrr", "type": "financial", "data": {"label": f"MRR: ${fin['mrr']:,}"}, "position": {"x": 250, "y": 0}},
        {"id": "runway", "type": "financial", "data": {"label": f"Runway: {fin['runway_months']:.1f} mo"}, "position": {"x": 250, "y": 80}},
        {"id": "starter", "type": "plan", "data": {"label": "Starter ($79, 450 users)"}, "position": {"x": 50, "y": 180}},
        {"id": "pro", "type": "plan", "data": {"label": "Pro ($249, 180 users)"}, "position": {"x": 250, "y": 180}},
        {"id": "enterprise", "type": "plan", "data": {"label": "Enterprise ($1,200, 25 users)"}, "position": {"x": 450, "y": 180}},
        {"id": "infra", "type": "cost", "data": {"label": f"Cloud Infra: ${data['infrastructure']['monthly_cloud_cost']:,}/mo"}, "position": {"x": 100, "y": 300}},
        {"id": "support", "type": "cost", "data": {"label": f"Support: {data['support']['headcount_fte']} FTEs"}, "position": {"x": 350, "y": 300}}
    ]

    edges = [
        {"id": "e1", "source": "starter", "target": "mrr"},
        {"id": "e2", "source": "pro", "target": "mrr"},
        {"id": "e3", "source": "enterprise", "target": "mrr"},
        {"id": "e4", "source": "mrr", "target": "runway"},
        {"id": "e5", "source": "infra", "target": "runway"},
        {"id": "e6", "source": "support", "target": "runway"}
    ]

    return {"nodes": nodes, "edges": edges}
