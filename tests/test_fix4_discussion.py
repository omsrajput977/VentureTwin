import pytest
import asyncio
from state.schemas import (
    Finding,
    Assumption,
    Conflict,
    Critique,
    Rebuttal,
    Decision,
    Evidence
)
from conflict.detector import (
    detect_contradictory_recommendations,
    detect_non_overlapping_ranges,
    detect_missing_evidence,
    detect_all_conflicts
)
from conflict.resolver import resolve_conflict_via_simulation
from orchestrator.decomposer import decompose_decision
from orchestrator.supervisor import Supervisor
from data.loader import load_company_data

def test_ordinal_recommendation_conflict_detection():
    # Stances with distance < 2 should NOT produce a conflict (proceed=3 vs proceed_with_limits=2 -> diff 1)
    f1 = Finding(
        agent="GROWTH",
        task_id="t1",
        claim="Growth supports free plan",
        recommendation="proceed",
        assumptions=[],
        evidence=[]
    )
    f2 = Finding(
        agent="PRODUCT",
        task_id="t2",
        claim="Product recommends limits",
        recommendation="proceed_with_limits",
        assumptions=[],
        evidence=[]
    )
    assert len(detect_contradictory_recommendations([f1, f2])) == 0

    # Stances with distance >= 2 (reject=0 vs proceed=3 -> diff 3) MUST produce a conflict
    f3 = Finding(
        agent="CFO",
        task_id="t3",
        claim="CFO rejects free tier",
        recommendation="reject",
        assumptions=[],
        evidence=[]
    )
    conflicts = detect_contradictory_recommendations([f1, f3])
    assert len(conflicts) == 1
    assert "CFO" in conflicts[0].agents
    assert "GROWTH" in conflicts[0].agents

def test_parameter_conflicts_grouped_per_param_and_degraded_ignored():
    f_cfo = Finding(
        agent="CFO",
        task_id="t1",
        claim="CFO low conversion",
        recommendation="reject",
        assumptions=[
            Assumption(name="free_to_paid_conversion", low=0.01, base=0.015, high=0.018, unit="rate", provenance="verified_data", proposed_by="CFO")
        ],
        evidence=[Evidence(source_type="calculation", source_ref="cfo.calc", snippet="cfo")]
    )
    f_growth = Finding(
        agent="GROWTH",
        task_id="t2",
        claim="Growth high conversion",
        recommendation="proceed",
        assumptions=[
            Assumption(name="free_to_paid_conversion", low=0.035, base=0.04, high=0.05, unit="rate", provenance="external_research", proposed_by="GROWTH")
        ],
        evidence=[Evidence(source_type="calculation", source_ref="growth.calc", snippet="growth")]
    )
    f_product = Finding(
        agent="PRODUCT",
        task_id="t3",
        claim="Product very high conversion",
        recommendation="proceed_with_limits",
        assumptions=[
            Assumption(name="free_to_paid_conversion", low=0.06, base=0.07, high=0.08, unit="rate", provenance="simulated_estimate", proposed_by="PRODUCT")
        ],
        evidence=[Evidence(source_type="calculation", source_ref="product.calc", snippet="product")]
    )
    # 3 agents disagreeing on the SAME parameter should produce ONE conflict with 3 sides
    range_conflicts = detect_non_overlapping_ranges([f_cfo, f_growth, f_product])
    assert len(range_conflicts) == 1
    assert len(range_conflicts[0].sides) == 3
    assert range_conflicts[0].disputed_item == "free_to_paid_conversion"

    # Degraded finding should be ignored in conflict detection
    f_cfo_degraded = Finding(
        agent="CFO",
        task_id="t1",
        claim="Degraded fallback",
        recommendation="reject",
        assumptions=[
            Assumption(name="free_to_paid_conversion", low=0.01, base=0.015, high=0.018, unit="rate", provenance="fallback_degraded", proposed_by="CFO")
        ],
        evidence=[],
        degraded=True
    )
    assert len(detect_non_overlapping_ranges([f_cfo_degraded, f_growth])) == 0

def test_missing_evidence_unresolved_material():
    f = Finding(
        agent="GROWTH",
        task_id="t1",
        claim="No source given",
        recommendation="proceed",
        assumptions=[
            Assumption(
                name="free_to_paid_conversion",
                low=0.02, base=0.03, high=0.04,
                unit="rate",
                provenance="verified_data",
                source_ref=None,
                proposed_by="GROWTH"
            )
        ],
        evidence=[]
    )
    conflicts = detect_missing_evidence([f])
    assert len(conflicts) == 1
    assert conflicts[0].status == "unresolved_material"

def test_isolated_parameter_simulation_resolution():
    conflict = Conflict(
        id="c1",
        type="non_overlapping_ranges",
        agents=["CFO", "GROWTH"],
        disputed_item="free_to_paid_conversion",
        sides=[
            {"agent": "CFO", "base": 0.015, "range": [0.01, 0.02]},
            {"agent": "GROWTH", "base": 0.040, "range": [0.03, 0.05]}
        ]
    )
    resolved = resolve_conflict_via_simulation(conflict, [], baseline_params={
        "monthly_free_signups": 3800.0,
        "free_to_paid_conversion": 0.025,
        "paid_to_free_cannibalization": 0.08,
        "infra_cost_per_free_user": 1.15
    })
    assert resolved.resolution_method == "simulation_isolation"
    assert resolved.isolated_simulation_deltas is not None
    assert "B_usage_caps" in resolved.isolated_simulation_deltas
    assert resolved.verdict is not None
    assert resolved.status in ["resolved", "resolved_immaterial", "resolved_converged", "unresolved_material", "unresolved_immaterial"]

@pytest.mark.asyncio
async def test_dag_includes_discussion_node():
    dec = Decision(id="d1", question="Should we launch a free plan?", type="free_plan", objective="Evaluate feasibility")
    dag = decompose_decision(dec)
    assert "task_agent_discussion" in dag.tasks
    # Check dependencies: discussion depends on skeptic audit, conflict resolution depends on discussion
    disc_task = dag.tasks["task_agent_discussion"]
    conf_task = dag.tasks["task_conflict_resolution"]
    assert "task_skeptic_audit" in disc_task.depends_on
    assert "task_agent_discussion" in conf_task.depends_on
