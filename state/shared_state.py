from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from state.schemas import (
    Decision,
    Task,
    Finding,
    Assumption,
    Conflict,
    SimulationRun,
    VerificationResult,
    Report,
    Event
)

class WorkflowState(BaseModel):
    decision: Decision
    tasks: Dict[str, Task] = Field(default_factory=dict)
    findings: List[Finding] = Field(default_factory=list)
    assumptions: List[Assumption] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    simulation_runs: List[SimulationRun] = Field(default_factory=list)
    verification_results: List[VerificationResult] = Field(default_factory=list)
    report: Optional[Report] = None
    events: List[Event] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed", "degraded"] = "pending"
    degraded_agents: List[str] = Field(default_factory=list)
    round: int = 1
    max_rounds: int = 3

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)
        for asm in finding.assumptions:
            # Avoid duplicate assumption names
            existing = next((a for a in self.assumptions if a.name == asm.name and a.proposed_by == asm.proposed_by), None)
            if not existing:
                self.assumptions.append(asm)

    def mark_task_done(self, task_id: str, output_ref: Optional[str] = None) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].status = "done"
            self.tasks[task_id].output_ref = output_ref

    def mark_task_failed(self, task_id: str, error: str) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].status = "failed"
            self.tasks[task_id].error = error
