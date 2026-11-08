from datetime import datetime, timezone
from typing import Literal, Optional, Any, Dict, List
from pydantic import BaseModel, Field, model_validator

# Provenance types
ProvenanceType = Literal[
    "verified_data",
    "external_research",
    "simulated_estimate",
    "ai_assumption",
    "fallback_degraded"
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

    @model_validator(mode="after")
    def validate_bounds(self) -> "Assumption":
        if self.low > self.base:
            raise ValueError(f"Assumption '{self.name}' low ({self.low}) cannot exceed base ({self.base})")
        if self.base > self.high:
            raise ValueError(f"Assumption '{self.name}' base ({self.base}) cannot exceed high ({self.high})")
        return self

class DraftAssumption(BaseModel):
    name: str
    low: float
    base: float
    high: float
    unit: str
    basis: str
    rationale: str

    @model_validator(mode="after")
    def validate_draft_bounds(self) -> "DraftAssumption":
        if self.low > self.base:
            self.low = self.base
        if self.base > self.high:
            self.high = self.base
        return self

class Evidence(BaseModel):
    source_type: Literal["company_data", "external", "calculation"]
    source_ref: str
    snippet: str

class AgentFindingDraft(BaseModel):
    claim: str
    recommendation: str = "proceed"
    assumptions: List[DraftAssumption] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

class Finding(BaseModel):
    agent: str
    task_id: str
    claim: str
    recommendation: str = "proceed"
    assumptions: List[Assumption] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    limitations: List[str] = Field(default_factory=list)
    status: Literal["ok", "failed", "needs_more_info"] = "ok"
    degraded: bool = False
    degraded_reason: Optional[str] = None

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
    kind: Literal[
        "core_analysis",
        "specialist_analysis",
        "agent_critique",
        "agent_discussion",
        "supervisor_coordination"
    ] = "specialist_analysis"

class Conflict(BaseModel):
    id: str
    type: str
    agents: List[str]
    disputed_item: str
    evidence: List[Evidence] = Field(default_factory=list)
    resolution: Optional[str] = None
    simulation_ids: List[str] = Field(default_factory=list)
    unresolved: bool = False
    status: Literal["resolved", "unresolved_material", "unresolved_immaterial"] = "resolved"
    verdict: Optional[str] = None
    resolution_method: Optional[Literal["simulation_isolation", "rebuttal_concession", "skeptic_audit", "procedural"]] = None
    sides: List[Dict[str, Any]] = Field(default_factory=list)
    isolated_simulation_deltas: Optional[Dict[str, float]] = None

class Critique(BaseModel):
    skeptic_agent: str
    target_agent: str
    target_parameter: str
    concern: str
    severity: Literal["low", "medium", "high"] = "medium"

class Rebuttal(BaseModel):
    agent: str
    parameter: str
    stance: Literal["concede", "defend", "compromise"]
    updated_base: Optional[float] = None
    updated_low: Optional[float] = None
    updated_high: Optional[float] = None
    rationale: str

class Message(BaseModel):
    from_agent: str
    to_agent: str
    round: int
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

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

