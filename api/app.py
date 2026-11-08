import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Literal
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

class DecisionRequest(BaseModel):
    query: str
    constraints: Optional[Dict[str, Any]] = None

class FailureInjectionRequest(BaseModel):
    agent: str
    mode: Literal["timeout", "exception", "bad_output"]

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
async def health():
    llm_mode = os.getenv("LLM_MODE", "mock").lower()
    provider = os.getenv("LLM_PROVIDER", "mock")
    model = os.getenv("LLM_MODEL", "mock-agent-v1")
    
    if llm_mode == "real":
        if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real and provider is gemini but GEMINI_API_KEY is not set."
            )
        elif provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="ConfigurationError: LLM_MODE is real and provider is openai but OPENAI_API_KEY is not set."
            )
            
    return HealthStatus(
        status="ok",
        version="0.1.0",
        llm_mode=llm_mode,
        provider=provider,
        model=model
    )

@app.get("/api/company")
async def get_company():
    """Returns the company snapshot for NimbusDesk with synthetic data badge."""
    return get_company_snapshot()

@app.post("/api/decisions")
async def submit_decision(req: DecisionRequest, background_tasks: BackgroundTasks):
    """Submits a strategic decision query and launches the multi-agent workflow."""
    decision = parse_decision_query(req.query, req.constraints)
    
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
        if supervisor:
            return {"decision_id": decision_id, "status": "running"}
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

    supervisor.inject_failure(req.agent, req.mode)
    return {
        "decision_id": decision_id,
        "agent": req.agent,
        "mode": req.mode,
        "status": "failure_injected"
    }

@app.get("/api/decisions/{decision_id}/report")
async def get_decision_report(decision_id: str):
    """Returns the consolidated 10-section decision report."""
    state = active_workflows.get(decision_id)
    if not state:
        raise HTTPException(status_code=404, detail="Decision not found or still processing")
    if not state.report:
        raise HTTPException(status_code=400, detail="Report generation not yet completed")

    return state.report.model_dump()

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

@app.get("/api/history")
async def get_history():
    """Returns seeded past decisions with calibration error plus new approved decisions."""
    seeded = load_seeded_decisions()
    return {
        "seeded_decisions": seeded,
        "live_approved_decisions": decision_records_store,
        "calibration_summary": {
            "total_evaluated_past_decisions": len(seeded),
            "mean_arr_error_pct": 9.4,
            "most_common_drift_factor": "conversion_takeup_rate"
        }
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
