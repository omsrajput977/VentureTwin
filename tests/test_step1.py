import pytest
from pydantic import ValidationError
from state.schemas import (
    Assumption,
    Evidence,
    Finding,
    Decision,
    Task,
    Conflict,
    SimulationRun,
    VerificationResult,
    Report,
    DecisionRecord,
    Event
)
from data.loader import load_company_data, get_company_snapshot, load_seeded_decisions

def test_assumption_schema_validation():
    assumption = Assumption(
        name="free_to_paid_conversion",
        low=0.012,
        base=0.018,
        high=0.035,
        unit="percentage",
        provenance="simulated_estimate",
        confidence=0.75,
        proposed_by="CFO"
    )
    assert assumption.name == "free_to_paid_conversion"
    assert assumption.low < assumption.base < assumption.high
    assert assumption.confidence == 0.75
    assert not assumption.challenged_by_skeptic

    # Invalid confidence (> 1.0)
    with pytest.raises(ValidationError):
        Assumption(
            name="invalid",
            low=1, base=2, high=3,
            unit="pct",
            provenance="ai_assumption",
            confidence=1.5
        )

    # Invalid provenance literal
    with pytest.raises(ValidationError):
        Assumption(
            name="invalid_prov",
            low=1, base=2, high=3,
            unit="pct",
            provenance="unverified_rumor"  # type: ignore
        )

def test_finding_and_evidence_schema():
    evidence = Evidence(
        source_type="company_data",
        source_ref="financials.runway_months",
        snippet="Current runway is 13.2 months with $1.65M cash"
    )
    finding = Finding(
        agent="CFO",
        task_id="task_001",
        claim="Launching unlimited free plan threatens runway constraint of 10 months",
        recommendation="proceed_with_limits",
        assumptions=[],
        evidence=[evidence],
        confidence=0.85,
        limitations=["Assumes AWS tier remains unchanged"]
    )
    assert finding.recommendation == "proceed_with_limits"
    assert finding.evidence[0].source_type == "company_data"

def test_decision_and_task_schema():
    decision = Decision(
        id="dec_001",
        type="free_plan",
        question="Should we launch a free plan?",
        objective="Accelerate self-serve customer acquisition",
        constraints={"min_runway_months": 10.0}
    )
    assert decision.type == "free_plan"

    task = Task(
        id="task_cfo_01",
        owner_agent="CFO",
        depends_on=[],
        status="pending"
    )
    assert task.status == "pending"
    assert task.attempts == 0

def test_company_loader_and_snapshot():
    raw = load_company_data()
    assert raw["company_name"] == "NimbusDesk"
    assert raw["synthetic_data_badge"] is True
    assert raw["financials"]["cash_balance"] == 1650000
    assert raw["customers"]["total_paying"] == 655

    snapshot = get_company_snapshot()
    assert snapshot["mrr"] == 110370
    assert snapshot["runway_months"] == 13.2
    assert snapshot["paying_customers"] == 655

def test_seeded_decisions_loader():
    decisions = load_seeded_decisions()
    assert len(decisions) >= 3
    assert all("calibration_error" in d for d in decisions)
    assert decisions[0]["id"] == "dec_2023_q3_annual_discount"
