import pytest
from state.schemas import Conflict, Finding, Assumption, Evidence, Decision
from conflict.detector import detect_all_conflicts, generate_deterministic_conflict_id
from conflict.resolver import resolve_conflict_via_simulation, get_min_runway

def test_deterministic_conflict_ids():
    id1 = generate_deterministic_conflict_id("non_overlapping_ranges", "free_to_paid_conversion", ["CFO", "GROWTH"])
    id2 = generate_deterministic_conflict_id("non_overlapping_ranges", "free_to_paid_conversion", ["GROWTH", "CFO"])
    assert id1 == id2
    assert id1.startswith("conf_")

def test_recommendation_conflict_settled_by_simulation_not_canned_text():
    f_growth = Finding(
        agent="GROWTH",
        task_id="t1",
        claim="Growth wants to proceed",
        recommendation="proceed",
        assumptions=[],
        evidence=[]
    )
    f_cfo = Finding(
        agent="CFO",
        task_id="t2",
        claim="CFO wants to reject",
        recommendation="reject",
        assumptions=[],
        evidence=[]
    )
    conflict = Conflict(
        id=generate_deterministic_conflict_id("contradictory_recommendations", "decision_recommendation", ["CFO", "GROWTH"]),
        type="contradictory_recommendations",
        agents=["CFO", "GROWTH"],
        disputed_item="decision_recommendation"
    )
    resolved = resolve_conflict_via_simulation(conflict, [f_growth, f_cfo])
    assert resolved.status in ["resolved", "unresolved_material"]
    # Resolution text must be generated dynamically from computed simulation figures, no static canned phrases
    assert "Reconciled recommendation to proceed_with_limits via usage caps." != resolved.verdict
    assert len(resolved.simulation_ids) >= 1
    for sid in resolved.simulation_ids:
        assert sid.startswith("sim_iso_")

def test_decision_constraints_control_min_runway():
    dec = Decision(
        id="d_custom_runway",
        question="Should we launch a free plan?",
        type="free_plan",
        objective="Test",
        constraints={"min_runway_months": 15.0}
    )
    company_data = {"financials": {"target_min_runway_months": 10.0}}
    min_runway = get_min_runway(dec, company_data)
    assert min_runway == 15.0

@pytest.mark.asyncio
async def test_rebuttal_revision_yields_resolved_converged():
    from orchestrator.supervisor import Supervisor
    from state.shared_state import WorkflowState
    from state.schemas import Task, Rebuttal

    dec = Decision(id="d1", question="Should we launch a free plan?", type="free_plan", objective="Test")
    state = WorkflowState(decision=dec)

    f_cfo = Finding(
        agent="CFO",
        task_id="t1",
        claim="CFO conservative",
        recommendation="reject",
        assumptions=[
            Assumption(id="asm_cfo_free_to_paid_conversion", name="free_to_paid_conversion", low=0.01, base=0.015, high=0.02, unit="rate", provenance="verified_data", proposed_by="CFO")
        ],
        evidence=[]
    )
    f_growth = Finding(
        agent="GROWTH",
        task_id="t2",
        claim="Growth aggressive",
        recommendation="proceed",
        assumptions=[
            Assumption(id="asm_growth_free_to_paid_conversion", name="free_to_paid_conversion", low=0.028, base=0.035, high=0.045, unit="rate", provenance="external_research", proposed_by="GROWTH")
        ],
        evidence=[]
    )
    state.add_finding(f_cfo)
    state.add_finding(f_growth)

    # Skeptic challenge against CFO
    state.skeptic_challenges = [{
        "agent": "CFO",
        "assumption": "free_to_paid_conversion",
        "challenge": "Benchmark data indicates conversion can reach 3.0% with good onboarding."
    }]

    supervisor = Supervisor()

    # Mock llm_call for discussion rebuttal to return a compromise that overlaps with Growth
    async def mock_discussion_call(*args, **kwargs):
        return Rebuttal(
            agent="CFO",
            parameter="free_to_paid_conversion",
            stance="compromise",
            updated_base=0.030,
            updated_low=0.025,
            updated_high=0.032,
            rationale="Agreed to adjust upward toward 3.0% based on onboarding benchmarks."
        )

    import agents.llm_client as llm_mod
    orig_call = llm_mod.llm_call
    llm_mod.llm_call = mock_discussion_call
    try:
        disc_task = Task(id="task_agent_discussion", kind="discussion", description="Agent discussion", owner_agent="supervisor")
        await supervisor._run_discussion_task(disc_task, state)

        # Verify revision stored
        revised_asm = next(a for a in state.findings[0].assumptions if a.name == "free_to_paid_conversion")
        assert revised_asm.revision_of == "asm_cfo_free_to_paid_conversion"
        assert revised_asm.revision_rationale is not None
        assert revised_asm.base == 0.030
        assert revised_asm.high == 0.032

        # Verify resolved_converged conflict created
        assert any(c.status == "resolved_converged" for c in state.conflicts)
        converged = next(c for c in state.conflicts if c.status == "resolved_converged")
        assert converged.disputed_item == "free_to_paid_conversion"
        assert "CFO" in converged.agents and "GROWTH" in converged.agents

        # Now run conflict resolution task - it should preserve the converged conflict
        conf_task = Task(id="task_conflict_resolution", kind="conflict_resolution", description="Conflict resolution", owner_agent="supervisor")
        await supervisor._run_conflict_resolution_task(conf_task, state)
        assert any(c.status == "resolved_converged" for c in state.conflicts)
    finally:
        llm_mod.llm_call = orig_call

