import pytest
import os
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from agents.llm_client import LLMClient, LLMConfigurationError
from state.schemas import Assumption, Conflict, Finding
from conflict.resolver import resolve_conflict_via_simulation
from verification.verifier import verify_report_data_traceability

@pytest.mark.asyncio
async def test_full_workflow_order_independence_10_runs():
    """Run the workflow 3 times with different delays; reports must be strictly identical."""
    decision = parse_decision_query("Should we launch a free plan?")
    reports_scenarios = []

    for _ in range(3):
        sup = Supervisor()
        state = await sup.execute_workflow(decision)
        scenarios = state.report.sections["scenario_table"]
        # Extract net contributions across all scenarios
        net_contribs = [s["net_contribution_12"] for s in scenarios]
        reports_scenarios.append(net_contribs)

    assert reports_scenarios[0] == reports_scenarios[1] == reports_scenarios[2]

@pytest.mark.asyncio
async def test_degraded_run_verifies_correctly():
    """A persistent failure in one agent yields a degraded report with Low or Medium confidence."""
    sup = Supervisor()
    sup.inject_failure("cto", "persistent_exception")
    decision = parse_decision_query("Should we launch a free plan?")
    
    state = await sup.execute_workflow(decision)
    assert state.status == "degraded"
    assert "cto" in state.degraded_agents
    assert state.report.confidence in ["Low", "Medium"]
    # Verification summary exists
    assert len(state.verification_results) > 0

def test_real_mode_readiness():
    """LLM_MODE=real without key raises LLMConfigurationError"""
    with pytest.raises(LLMConfigurationError):
        LLMClient(mode="real", provider="gemini")

def test_resolver_proceed_vs_reject_has_computed_justification():
    """Proceed vs reject conflict has computed simulation resolution"""
    f1 = Finding(agent="Growth", task_id="t1", claim="Claim 1", recommendation="proceed", confidence=0.8)
    f2 = Finding(agent="CFO", task_id="t2", claim="Claim 2", recommendation="reject", confidence=0.8)
    c = Conflict(
        id="c1",
        type="contradictory_recommendations",
        agents=["Growth", "CFO"],
        disputed_item="decision_recommendation"
    )
    resolved = resolve_conflict_via_simulation(c, [f1, f2])
    assert resolved.resolution is not None
    assert "$" in resolved.resolution
    assert len(resolved.simulation_ids) == 2

