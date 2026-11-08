from datetime import datetime, timezone
from typing import Literal, Optional, Any, Dict, List
from pydantic import BaseModel, Field

# Provenance types
ProvenanceType = Literal[
    "verified_data",
    "external_research",
    "simulated_estimate",
    "ai_assumption"
]

class Assumption(BaseModel):
    name: str
    low: float
    base: float
    high: float
    unit: str
    provenance: ProvenanceType
    source_ref: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    proposed_by: Optional[str] = None
    challenged_by_skeptic: bool = False

class Evidence(BaseModel):
    source_type: Literal["company_data", "external", "calculation"]
    source_ref: str
    snippet: str

class Finding(BaseModel):
    agent: str
    task_id: str
    claim: str
    recommendation: Literal["proceed", "proceed_with_limits", "reject", "needs_more_info"]
    assumptions: List[Assumption] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    limitations: List[str] = Field(default_factory=list)
    status: Literal["ok", "failed", "needs_more_info"] = "ok"

class Decision(BaseModel):
    id: str
    type: Literal["free_plan", "price_change", "unsupported"]
    question: str
    objective: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Task(BaseModel):
    id: str
    owner_agent: str
    depends_on: List[str] = Field(default_factory=list)
    status: Literal["pending", "running", "done", "failed", "retrying", "blocked"] = "pending"
    input_ref: Optional[str] = None
    output_ref: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[str] = None

class Conflict(BaseModel):
    id: str
    type: str
    agents: List[str]
    disputed_item: str
    evidence: List[Evidence] = Field(default_factory=list)
    resolution: Optional[str] = None
    simulation_ids: List[str] = Field(default_factory=list)
    unresolved: bool = False

class SimulationRun(BaseModel):
    id: str
    strategy: str
    scenario: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    seed: int = 42

class VerificationResult(BaseModel):
    check_name: str
    status: Literal["passed", "failed", "waived"]
    detail: str

class Report(BaseModel):
    decision_id: str
    sections: Dict[str, Any] = Field(default_factory=dict)
    recommendation: str
    confidence: Literal["Low", "Medium", "High"]
    disclaimers: List[str] = Field(default_factory=list)

class DecisionRecord(BaseModel):
    decision_id: str
    snapshot: Dict[str, Any]
    chosen_strategy: str
    predicted_metrics: Dict[str, Any]
    approved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actual_metrics: Optional[Dict[str, Any]] = None

class Event(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: Literal[
        "task_created",
        "agent_started",
        "finding_posted",
        "conflict_detected",
        "simulation_run",
        "agent_failed",
        "recovery_started",
        "recovery_done",
        "verification_passed",
        "verification_failed",
        "report_ready"
    ]
    agent: str
    payload: Dict[str, Any] = Field(default_factory=dict)
