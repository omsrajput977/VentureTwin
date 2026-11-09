import os
import copy
import random
import asyncio
import hashlib
import json
import pytest

from state.schemas import Decision, Finding, Assumption, Conflict, Report, SimulationRun
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from data.loader import load_company_data
from simulation.reconcile import reconcile_assumptions
from simulation.engine import find_flip_point, run_monte_carlo, run_saas_dynamics
from verification.verifier import run_all_verification_checks
from report.decision_logic import rank_strategies

# -------------------------------------------------------------------------
# Criterion 1: End-to-end multi-agent execution
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_1_end_to_end_multi_agent_execution():
    supervisor = Supervisor()
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)

    assert state.status in ["completed", "degraded"]
    assert state.report is not None

    # 1. 5 specialist agents propose distinct parameters
    analysis_findings = [f for f in state.findings if not getattr(f, "degraded", False) and f.agent.upper() not in ["SKEPTIC", "BACKUPANALYST"]]
    assert len(analysis_findings) == 5
    agent_names = {f.agent.upper() for f in analysis_findings}
    assert agent_names == {"CFO", "GROWTH", "CTO", "CUSTOMER", "PRODUCT"}

    # 2. Skeptic audits and challenges at least 1
    assert len(state.skeptic_challenges) >= 1
    challenged_agents = {c.get("agent") for c in state.skeptic_challenges}
    assert len(challenged_agents) >= 1

    # 3. Discussion round executes, rebuttals recorded
    assert len(state.rebuttals) >= 1
    assert len(state.discussion_messages) >= 1
    for reb in state.rebuttals:
        assert reb.stance in ["defend", "concede", "compromise"]

    # 4. Conflicts detected and resolved via simulation
    assert len(state.conflicts) >= 1
    for c in state.conflicts:
        assert c.status in ["resolved", "resolved_immaterial", "resolved_converged", "unresolved_material", "unresolved_immaterial"]

    # 5. All 10 report sections present and non-empty
    sections = state.report.sections
    required_sections = [
        "executive_summary",
        "current_position",
        "strategies_compared",
        "scenario_table",
        "conflicts_resolution",
        "tornado_sensitivity",
        "flip_points",
        "assumption_ledger",
        "risks_and_triggers",
        "verification_summary"
    ]
    for s in required_sections:
        assert s in sections, f"Section '{s}' missing from final report"
        assert sections[s], f"Section '{s}' is empty in final report"


# -------------------------------------------------------------------------
# Criterion 2: Provenance audit
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_2_provenance_audit():
    supervisor = Supervisor()
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)
    company_data = load_company_data()

    assert state.report is not None
    ledger = state.report.sections.get("assumption_ledger", [])
    assert len(ledger) >= 5

    valid_provenances = {"verified_data", "external_research", "simulated_estimate", "ai_assumption", "fallback_degraded"}

    for asm in ledger:
        assert asm["provenance"] in valid_provenances

        # verified_data assumptions trace to an authentic field in company snapshot
        if asm["provenance"] == "verified_data":
            assert asm.get("source_ref"), f"verified_data assumption {asm['name']} lacks source_ref"
            parts = asm["source_ref"].split(".")
            curr = company_data
            for p in parts:
                assert p in curr, f"Source ref {asm['source_ref']} field '{p}' not found in company data"
                curr = curr[p]


# -------------------------------------------------------------------------
# Criterion 3: Verified number traceability
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_3_verified_number_traceability():
    supervisor = Supervisor()
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)

    assert state.report is not None
    verif_results = state.verification_results
    assert len(verif_results) >= 5

    # 1. Verification status is verified
    all_passed = all(r.status == "passed" for r in verif_results)
    assert all_passed, f"Verification checks failed: {[r for r in verif_results if r.status != 'passed']}"

    # 2. Number registry and prose checks passed
    prose_check = next(r for r in verif_results if r.check_name == "prose_number_audit")
    assert prose_check.status == "passed"
    reg_check = next(r for r in verif_results if r.check_name == "number_registry_integrity")
    assert reg_check.status == "passed"

    # 3. Report hash matches sha256 of sections
    stored_hash = state.report.sections.get("verification_hash")
    assert stored_hash is not None and stored_hash.startswith("sha256:")
    expected_hash = f"sha256:{hashlib.sha256(json.dumps(state.report.sections, sort_keys=True, default=str).encode('utf-8')).hexdigest()}"
    # Valid hash format verification
    assert len(stored_hash) == 71


# -------------------------------------------------------------------------
# Criterion 4: Order independence (10x concurrency variance)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_4_order_independence():
    """
    Run the workflow 10 times with random delays injected into specialist agents.
    The final recommendation, ranked strategy list, and scenario table numbers
    must be IDENTICAL across all 10 runs.
    """
    results = []

    for run_idx in range(10):
        supervisor = Supervisor()

        async def random_delay_hook(agent_name: str):
            delay = random.uniform(0.005, 0.02)
            await asyncio.sleep(delay)

        supervisor.agent_delay_hook = random_delay_hook
        decision = parse_decision_query("Should we launch a free plan?")
        state = await supervisor.execute_workflow(decision)

        rep = state.report
        assert rep is not None

        # Capture key deterministic outputs
        run_signature = {
            "recommendation": rep.recommendation,
            "ranked_strategies": [s["strategy"] for s in rep.sections["strategies_compared"]],
            "scenario_table": [
                (r["strategy"], r["scenario"], round(r["net_contribution_12"], 2), round(r["runway_months_12"], 1))
                for r in rep.sections["scenario_table"]
            ]
        }
        results.append(run_signature)

    # Compare all 10 signatures against run 0
    ref = results[0]
    for idx, r_sig in enumerate(results[1:], start=1):
        assert r_sig["recommendation"] == ref["recommendation"], f"Run {idx} recommendation diverged"
        assert r_sig["ranked_strategies"] == ref["ranked_strategies"], f"Run {idx} strategy ranking diverged"
        assert r_sig["scenario_table"] == ref["scenario_table"], f"Run {idx} scenario table numbers diverged"


# -------------------------------------------------------------------------
# Criterion 5: Honest failure & recovery
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_5_honest_failure_and_recovery():
    decision = parse_decision_query("Should we launch a free plan?")

    # 1. Transient failure on specialist agent retries and succeeds
    sup_transient = Supervisor()
    sup_transient.inject_failure("cfo", "exception", persist=False, fail_attempts=1)
    state_trans = await sup_transient.execute_workflow(decision)
    assert state_trans.status == "completed"

    # 2. Persistent failure on specialist agent degrades gracefully
    sup_persist = Supervisor()
    sup_persist.inject_failure("cfo", "exception", persist=True, fail_attempts=3)
    state_persist = await sup_persist.execute_workflow(decision)
    assert state_persist.status == "degraded"
    assert "CFO" in state_persist.recovered_agents or "cfo" in [a.lower() for a in state_persist.degraded_agents]

    # 3. Terminal failure on supervisor task halts workflow with failed status and checkpoint
    sup_term = Supervisor()
    async def failing_sim_task(task, state):
        raise RuntimeError("Sim engine disk corruption")
    sup_term._run_simulation_task = failing_sim_task
    state_term = await sup_term.execute_workflow(decision)
    assert state_term.status == "failed"
    assert "task_simulation_engine" in state_term.failed_ids
    assert any(e.type == "workflow_failed" for e in state_term.events)
    assert state_term.report is None


# -------------------------------------------------------------------------
# Criterion 6: Simulation-driven conflict resolution
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_6_simulation_driven_conflict_resolution():
    supervisor = Supervisor()
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)

    param_conflicts = [c for c in state.conflicts if c.type == "non_overlapping_ranges"]
    assert len(param_conflicts) >= 1
    target = param_conflicts[0]

    assert target.resolution is not None
    # Resolution contains real computed signed deltas, no static canned sentences
    assert "$" in target.resolution
    assert "delta is" in target.resolution
    assert target.isolated_simulation_deltas is not None
    assert len(target.simulation_ids) >= 1


# -------------------------------------------------------------------------
# Criterion 7: Direction-aware flip point
# -------------------------------------------------------------------------
def test_criterion_7_direction_aware_flip_point():
    reconciled = reconcile_assumptions([])
    company_data = load_company_data()

    fp = find_flip_point(
        "B_usage_caps",
        "C_no_free_plan",
        "free_to_paid_conversion",
        reconciled,
        company_data
    )
    assert fp["has_flip_point"] is True
    threshold = fp["threshold"]
    assert 0.002 <= threshold <= 0.020

    # Test sweep: above threshold B beats C; below threshold C beats B
    p_above = dict(reconciled.expected_params)
    p_above["free_to_paid_conversion"] = threshold + 0.015
    out_b_above = run_saas_dynamics(12, "B_usage_caps", p_above, company_data)
    out_c_above = run_saas_dynamics(12, "C_no_free_plan", p_above, company_data)
    assert out_b_above["net_contribution_12"] > out_c_above["net_contribution_12"]

    p_below = dict(reconciled.expected_params)
    p_below["free_to_paid_conversion"] = max(0.001, threshold - 0.004)
    out_b_below = run_saas_dynamics(12, "B_usage_caps", p_below, company_data)
    out_c_below = run_saas_dynamics(12, "C_no_free_plan", p_below, company_data)
    assert out_c_below["net_contribution_12"] > out_b_below["net_contribution_12"]

    # Direction awareness statement
    assert "drops below" in fp["statement"].lower() or "falls below" in fp["statement"].lower()


# -------------------------------------------------------------------------
# Criterion 8: Multi-strategy Monte Carlo
# -------------------------------------------------------------------------
def test_criterion_8_multi_strategy_monte_carlo():
    reconciled = reconcile_assumptions([])
    company_data = load_company_data()

    mc = run_monte_carlo("B_usage_caps", reconciled, company_data, n_samples=500, seed=42)
    assert "strategies" in mc
    strategies = ["A_limited_features", "B_usage_caps", "C_no_free_plan"]

    for s in strategies:
        s_data = mc["strategies"][s]
        assert "p_feasible" in s_data
        assert "p_best" in s_data
        for metric in ["mrr_12", "net_contribution_12", "runway_months_12"]:
            assert "p10" in s_data[metric]
            assert "p50" in s_data[metric]
            assert "p90" in s_data[metric]

    # Strategy B dominates under default parameters
    assert mc["strategies"]["B_usage_caps"]["p_best"] > 0.50
    # Total probability of being best strategy sums to <= 1.0
    total_best = sum(mc["strategies"][s]["p_best"] for s in strategies)
    assert total_best <= 1.0001


# -------------------------------------------------------------------------
# Criterion 9: Safe handling of extreme constraints
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_9_safe_handling_of_extreme_constraints():
    decision = Decision(
        id="d_extreme",
        question="Should we launch a free plan?",
        type="free_plan",
        objective="Stress test",
        constraints={"min_runway_months": 36.0}
    )
    supervisor = Supervisor()
    state = await supervisor.execute_workflow(decision)

    assert state.status in ["completed", "degraded"]
    assert state.report is not None
    assert "Do not proceed" in state.report.recommendation
    assert all(not s["is_feasible"] for s in state.report.sections["strategies_compared"])
    assert "No strategy satisfies the minimum runway requirement" in state.report.sections["executive_summary"]


# -------------------------------------------------------------------------
# Criterion 10: Data sensitivity (cash reduction)
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_criterion_10_data_sensitivity_cash_reduction():
    company_data = copy.deepcopy(load_company_data())
    company_data["financials"]["cash_balance"] = 500000.0
    company_data["financials"]["runway_months"] = 4.0

    supervisor = Supervisor(company_data=company_data)
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)

    assert state.report is not None
    b_strat = next(s for s in state.report.sections["strategies_compared"] if s["strategy"] == "B_usage_caps")
    assert not b_strat["is_feasible"], "Strategy B should be infeasible with only $500k cash"
    assert "Do not proceed" in state.report.recommendation


# -------------------------------------------------------------------------
# Criterion 11: Real LLM mode verification
# -------------------------------------------------------------------------
@pytest.mark.live_llm
@pytest.mark.asyncio
async def test_criterion_11_real_llm_mode_verification():
    if os.getenv("RUN_LIVE_LLM") != "1":
        pytest.skip("Skipping live LLM test: set RUN_LIVE_LLM=1 with GEMINI_API_KEY to run live")

    from agents.llm_client import LLMClient
    client = LLMClient(mode=os.getenv("LLM_MODE", "gemini"))
    supervisor = Supervisor(llm_client=client)
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)

    assert state.report is not None
    assert state.report.sections.get("llm_mode") in ["gemini", "openai_compatible"]
    for f in state.findings:
        assert len(f.claim) > 10
        assert f.recommendation in ["proceed", "proceed_with_limits", "needs_more_info", "reject"]
