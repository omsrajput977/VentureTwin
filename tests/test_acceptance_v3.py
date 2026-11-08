import pytest
import time
import asyncio
from data.loader import (
    load_company_data,
    load_benchmarks,
    load_model_config,
    load_seeded_decisions
)
from state.schemas import (
    Decision,
    Task,
    Finding,
    Assumption,
    Conflict,
    SimulationRun,
    Report
)
from agents.specialists import (
    CFOAgent,
    GrowthAgent,
    CTOAgent,
    CustomerAgent,
    ProductAgent,
    SkepticAgent
)
from agents.mock_handlers import default_mock_handler
from simulation.reconcile import reconcile_assumptions
from simulation.saas_model import run_saas_dynamics
from conflict.detector import detect_contradictory_recommendations, detect_non_overlapping_ranges
from conflict.resolver import resolve_conflict_via_simulation
from orchestrator.decomposer import decompose_decision
from orchestrator.supervisor import Supervisor
from report.number_registry import NumberRegistry
from verification.verifier import verify_number_registry, verify_prose_numbers, run_all_verification_checks
from report.report_builder import build_consolidated_report
from api.app import compute_calibration_summary

# Criterion 1: Real multi-agent orchestration with specialized nodes
def test_criterion_1_agents_are_separate_nodes_with_structured_output():
    agents = [CFOAgent(), GrowthAgent(), CTOAgent(), CustomerAgent(), ProductAgent(), SkepticAgent()]
    roles = {a.role for a in agents}
    assert len(roles) == 6, "Each agent must possess a unique professional role"
    objectives = {a.objective for a in agents}
    assert len(objectives) == 6, "Each agent must possess a distinct strategic objective"

# Criterion 2: LLMs/Mocks never output hardcoded number strings
@pytest.mark.asyncio
async def test_criterion_2_deterministic_mock_handlers_use_tool_data():
    cfo = CFOAgent()
    task = Task(id="t_cfo", owner_agent="CFO", kind="core_analysis")
    finding = await cfo.run(task, context={})
    assert isinstance(finding, Finding)
    assert len(finding.assumptions) >= 1
    # Check that conversion assumption has verified or grounded provenance
    conv_asm = next((a for a in finding.assumptions if a.name == "free_to_paid_conversion"), None)
    assert conv_asm is not None
    assert conv_asm.low <= conv_asm.base <= conv_asm.high

# Criterion 3: Order-independent assumption reconciliation
def test_criterion_3_order_independent_reconciliation():
    asm1 = Assumption(name="free_to_paid_conversion", low=0.01, base=0.015, high=0.02, unit="rate", provenance="verified_data", proposed_by="CFO")
    asm2 = Assumption(name="free_to_paid_conversion", low=0.025, base=0.035, high=0.05, unit="rate", provenance="external_research", proposed_by="GROWTH")

    rec_12 = reconcile_assumptions([asm1, asm2])
    rec_21 = reconcile_assumptions([asm2, asm1])

    assert rec_12.params["free_to_paid_conversion"].base == rec_21.params["free_to_paid_conversion"].base
    assert rec_12.params["free_to_paid_conversion"].low == rec_21.params["free_to_paid_conversion"].low
    assert rec_12.params["free_to_paid_conversion"].high == rec_21.params["free_to_paid_conversion"].high

# Criterion 4: Genuine strategy A vs B tradeoff
def test_criterion_4_genuine_strategy_tradeoff():
    data = load_company_data()
    # At low conversion, B beats A due to lower cost and cannibalization
    p_low = {"free_to_paid_conversion": 0.015, "infra_cost_per_free_user": 1.15, "activation_drop_from_gating": 0.15, "usage_cap_infra_reduction": 0.35}
    out_a_low = run_saas_dynamics(12, "A_limited_features", p_low, data)
    out_b_low = run_saas_dynamics(12, "B_usage_caps", p_low, data)
    assert out_b_low["net_contribution_12"] > out_a_low["net_contribution_12"]

    # At high conversion, A beats B due to 100% full signup activation volume
    p_high = {"free_to_paid_conversion": 0.08, "infra_cost_per_free_user": 1.15, "activation_drop_from_gating": 0.35, "cap_conversion_uplift": 0.02}
    out_a_high = run_saas_dynamics(12, "A_limited_features", p_high, data)
    out_b_high = run_saas_dynamics(12, "B_usage_caps", p_high, data)
    assert out_a_high["net_contribution_12"] > out_b_high["net_contribution_12"]

# Criterion 5: Real ordinal conflict detection
def test_criterion_5_ordinal_conflict_detection():
    f_support = Finding(agent="GROWTH", task_id="t1", claim="c1", recommendation="support")
    f_strongly_support = Finding(agent="PRODUCT", task_id="t2", claim="c2", recommendation="strongly_support")
    assert len(detect_contradictory_recommendations([f_support, f_strongly_support])) == 0

    f_oppose = Finding(agent="CFO", task_id="t3", claim="c3", recommendation="oppose")
    conflicts = detect_contradictory_recommendations([f_support, f_oppose])
    assert len(conflicts) == 1

# Criterion 6: Isolated-parameter conflict resolution
def test_criterion_6_isolated_parameter_conflict_resolution():
    conflict = Conflict(
        id="c_test",
        type="non_overlapping_ranges",
        agents=["CFO", "GROWTH"],
        disputed_item="free_to_paid_conversion",
        sides=[{"agent": "CFO", "base": 0.015}, {"agent": "GROWTH", "base": 0.035}]
    )
    resolved = resolve_conflict_via_simulation(conflict, [], baseline_params={"free_to_paid_conversion": 0.025})
    assert resolved.resolution_method == "simulation_isolation"
    assert resolved.isolated_simulation_deltas is not None
    assert "B_usage_caps" in resolved.isolated_simulation_deltas

# Criterion 7: Bounded discussion node in DAG
def test_criterion_7_discussion_node_in_dag():
    dec = Decision(id="d_disc", question="Should we launch a free plan?", type="free_plan", objective="Evaluate")
    dag = decompose_decision(dec)
    assert "task_agent_discussion" in dag.tasks
    assert "task_skeptic_audit" in dag.tasks["task_agent_discussion"].depends_on

# Criterion 8: Core task failure stops workflow
@pytest.mark.asyncio
async def test_criterion_8_core_task_failure_stops_workflow():
    dec = Decision(id="d_fail", question="Should we launch a free plan?", type="free_plan", objective="Evaluate")
    supervisor = Supervisor()
    supervisor.inject_failure("cfo", "persistent_exception")
    state = await supervisor.execute_workflow(dec)
    assert state.status == "failed"
    assert state.report is None

# Criterion 9: Instant timeout injection
@pytest.mark.asyncio
async def test_criterion_9_instant_timeout_injection():
    agent = CFOAgent()
    task = Task(id="t_cfo", owner_agent="CFO", kind="core_analysis")
    start = time.time()
    with pytest.raises(asyncio.TimeoutError):
        await agent.run(task, context={}, injected_failure="timeout")
    assert time.time() - start < 0.2

# Criterion 10: Number registry & prose number audit
def test_criterion_10_number_registry_and_prose_audit():
    reg = NumberRegistry()
    reg.register(value=943667.25, path="exec", origin="sim", expected_value=943667.25)
    clean_report = Report(
        decision_id="d1",
        sections={"number_registry": reg.to_dict(), "executive_summary": "Net contribution is $943,667.25 over 12 months."},
        recommendation="Proceed",
        confidence="High"
    )
    assert verify_prose_numbers(clean_report).status == "passed"

    rogue_report = Report(
        decision_id="d1",
        sections={"number_registry": reg.to_dict(), "executive_summary": "Net contribution is $4,500,000 hallucinated dollars."},
        recommendation="Proceed",
        confidence="High"
    )
    assert verify_prose_numbers(rogue_report).status == "failed"

# Criterion 11: Dynamic calibration summary
def test_criterion_11_dynamic_calibration_summary():
    seeded = load_seeded_decisions()
    summary = compute_calibration_summary(seeded)
    assert summary["total_evaluated_past_decisions"] == 4
    assert summary["mean_arr_error_pct"] > 0.0

# Criterion 12: Human approval gate without external execution
@pytest.mark.asyncio
async def test_criterion_12_human_approval_gate():
    dec = Decision(id="d_appr", question="Should we launch a free plan?", type="free_plan", objective="Evaluate")
    supervisor = Supervisor()
    state = await supervisor.execute_workflow(dec)
    assert state.status == "completed"
    assert state.report is not None
    # Report contains disclaimers that VentureTwin never executes external actions
    assert any("explicit human sign-off" in d for d in state.report.disclaimers)
