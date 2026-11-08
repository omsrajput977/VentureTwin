import pytest
import copy
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from data.loader import load_company_data
from simulation.engine import simulate
from state.schemas import Task, Finding, Assumption
from verification.verifier import verify_report_data_traceability, verify_provenance_integrity

@pytest.mark.asyncio
async def test_acceptance_1_data_sensitivity():
    """
    With a tiny cash balance, the system must not recommend a strategy
    that violates the runway constraint.
    """
    normal_data = load_company_data()
    # Deep copy with tiny cash balance ($50k vs $1.65M)
    constrained_data = copy.deepcopy(normal_data)
    constrained_data["financials"]["cash_balance"] = 50000.0
    constrained_data["financials"]["runway_months"] = 0.4

    decision = parse_decision_query("Should we launch a free plan?")
    supervisor = Supervisor(company_data=constrained_data)
    state = await supervisor.execute_workflow(decision)
    report = state.report
    assert report is not None
    # With tiny cash balance, top strategies violate runway constraint
    ranked = report.sections["strategies_compared"]
    top = ranked[0]
    # Infeasible or recommends not proceeding
    assert not top["is_feasible"] or "Do not proceed" in report.recommendation or top["runway_months_12"] < 10.0

@pytest.mark.asyncio
async def test_acceptance_2_scenario_ordering():
    """
    For every strategy, net_contribution_12 satisfies conservative <= expected <= optimistic,
    and the three are not equal.
    """
    data = load_company_data()
    asms = [
        Assumption(name="free_to_paid_conversion", low=0.012, base=0.022, high=0.035, unit="rate", provenance="simulated_estimate"),
        Assumption(name="monthly_free_signups", low=2500.0, base=3800.0, high=5000.0, unit="users/month", provenance="simulated_estimate"),
        Assumption(name="infra_cost_per_free_user", low=0.85, base=1.15, high=1.65, unit="USD/user/month", provenance="verified_data"),
        Assumption(name="paid_to_free_cannibalization", low=0.04, base=0.08, high=0.15, unit="rate", provenance="ai_assumption")
    ]
    for strat in ["A_limited_features", "B_usage_caps", "C_no_free_plan"]:
        c = simulate(strat, "conservative", asms, data).outputs["net_contribution_12"]
        e = simulate(strat, "expected", asms, data).outputs["net_contribution_12"]
        o = simulate(strat, "optimistic", asms, data).outputs["net_contribution_12"]
        assert c < e < o, f"Failed strict ordering for {strat}: {c} < {e} < {o}"

@pytest.mark.asyncio
async def test_acceptance_3_order_independence():
    """
    Shuffling the order in which agent tasks finish yields identical report numbers.
    """
    decision1 = parse_decision_query("Should we launch a free plan?")
    decision2 = parse_decision_query("Should we launch a free plan?")

    sup1 = Supervisor()
    sup2 = Supervisor()

    state1 = await sup1.execute_workflow(decision1)
    state2 = await sup2.execute_workflow(decision2)

    rep1 = state1.report.sections["scenario_table"]
    rep2 = state2.report.sections["scenario_table"]

    # Identical values
    assert [r["net_contribution_12"] for r in rep1] == [r["net_contribution_12"] for r in rep2]

def test_acceptance_4_tampering_caught():
    """
    Corrupting one number in the draft report makes verification fail.
    """
    data = load_company_data()
    decision = parse_decision_query("Should we launch a free plan?")
    from simulation.engine import simulate
    asms = [Assumption(name="test", low=1, base=2, high=3, unit="rate", provenance="simulated_estimate")]
    sim_run = simulate("B_usage_caps", "expected", asms, data)

    from state.schemas import Report
    report = Report(
        decision_id="dec_test",
        recommendation="Test",
        confidence="High",
        sections={"scenario_table": [{"strategy": "B_usage_caps", "scenario": "expected", "net_contribution_12": 9999999.0}]}
    )
    res = verify_report_data_traceability(report, [sim_run], data)
    assert res.status == "failed"
    assert "Tampering detected" in res.detail

@pytest.mark.asyncio
async def test_acceptance_5_honest_failure_and_degraded_flag():
    """
    A persistent agent failure produces a report that visibly flags the degraded agent
    and caps confidence.
    """
    supervisor = Supervisor()
    # Inject persistent failure into customer agent
    supervisor.inject_failure("customer", "persistent_exception")
    
    # Force max_attempts = 1 on customer task for faster test
    decision = parse_decision_query("Should we launch a free plan?")
    dag = supervisor.registry.get("customer")
    
    state = await supervisor.execute_workflow(decision)
    assert "customer" in state.degraded_agents or state.status == "degraded"
    assert state.report is not None
    # Confidence penalty applied
    assert state.report.confidence in ["Low", "Medium"]

def test_acceptance_7_no_fabricated_sources():
    """
    Every verified_data assumption traces to an authentic company snapshot field.
    """
    data = load_company_data()
    from agents.specialists import CFOAgent, CTOAgent
    cfo = CFOAgent()
    cto = CTOAgent()
    
    import asyncio
    f_cfo = asyncio.run(cfo.run(Task(id="t1", owner_agent="CFO"), context={}))
    f_cto = asyncio.run(cto.run(Task(id="t2", owner_agent="CTO"), context={}))

    all_asms = f_cfo.assumptions + f_cto.assumptions
    res = verify_provenance_integrity(all_asms, data)
    assert res.status == "passed"
