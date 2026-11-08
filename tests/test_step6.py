import pytest
from state.schemas import Assumption
from simulation.engine import (
    simulate,
    run_monte_carlo,
    run_sensitivity_analysis,
    find_flip_point
)
from data.loader import load_company_data

@pytest.fixture
def sample_assumptions():
    return [
        Assumption(
            name="free_to_paid_conversion",
            low=0.012,
            base=0.018,
            high=0.035,
            unit="rate",
            provenance="simulated_estimate",
            confidence=0.75
        ),
        Assumption(
            name="monthly_free_signups",
            low=2500.0,
            base=3800.0,
            high=5000.0,
            unit="users/month",
            provenance="simulated_estimate",
            confidence=0.70
        ),
        Assumption(
            name="infra_cost_per_free_user",
            low=0.85,
            base=1.15,
            high=1.65,
            unit="USD/user/mo",
            provenance="verified_data",
            confidence=0.85
        ),
        Assumption(
            name="paid_to_free_cannibalization",
            low=0.04,
            base=0.08,
            high=0.15,
            unit="rate",
            provenance="ai_assumption",
            confidence=0.60
        )
    ]

def test_simulation_reproducibility_and_metrics(sample_assumptions):
    data = load_company_data()
    run1 = simulate("B_usage_caps", "expected", sample_assumptions, data, seed=42)
    run2 = simulate("B_usage_caps", "expected", sample_assumptions, data, seed=42)

    assert run1.outputs == run2.outputs
    # Metrics at 6, 12, 24 months present
    assert "mrr_6" in run1.outputs
    assert "mrr_12" in run1.outputs
    assert "mrr_24" in run1.outputs
    assert "net_contribution_12" in run1.outputs
    assert "runway_months_12" in run1.outputs

def test_scenario_ordering_strict_inequality(sample_assumptions):
    data = load_company_data()
    for strat in ["A_limited_features", "B_usage_caps"]:
        c = simulate(strat, "conservative", sample_assumptions, data).outputs["net_contribution_12"]
        e = simulate(strat, "expected", sample_assumptions, data).outputs["net_contribution_12"]
        o = simulate(strat, "optimistic", sample_assumptions, data).outputs["net_contribution_12"]

        # conservative <= expected <= optimistic, and not equal
        assert c < e < o, f"Failed for {strat}: {c} < {e} < {o}"

def test_conversion_monotonicity(sample_assumptions):
    data = load_company_data()
    # Higher conversion must never lower MRR
    asms_low = [Assumption(name="free_to_paid_conversion", low=0.01, base=0.01, high=0.01, unit="rate", provenance="simulated_estimate")]
    asms_high = [Assumption(name="free_to_paid_conversion", low=0.04, base=0.04, high=0.04, unit="rate", provenance="simulated_estimate")]

    run_low = simulate("B_usage_caps", "expected", asms_low, data)
    run_high = simulate("B_usage_caps", "expected", asms_high, data)

    assert run_high.outputs["mrr_12"] >= run_low.outputs["mrr_12"]
    assert run_high.outputs["net_contribution_12"] > run_low.outputs["net_contribution_12"]

def test_monte_carlo_distribution(sample_assumptions):
    mc = run_monte_carlo("B_usage_caps", sample_assumptions, n_samples=100, seed=123)
    net = mc["net_contribution_12"]
    assert net["p10"] <= net["p50"] <= net["p90"]
    assert "mean" in net
    assert "prob_positive" in net

def test_sensitivity_analysis_tornado(sample_assumptions):
    tornado = run_sensitivity_analysis("B_usage_caps", sample_assumptions)
    assert len(tornado) == len(sample_assumptions)
    # Ranks are 1, 2, 3, 4
    assert [item["impact_rank"] for item in tornado] == [1, 2, 3, 4]
    # Swings are sorted descending
    for i in range(len(tornado) - 1):
        assert tornado[i]["swing"] >= tornado[i+1]["swing"]

def test_flip_point_search(sample_assumptions):
    res = find_flip_point(
        strategy_a="B_usage_caps",
        strategy_b="C_no_free_plan",
        variable_name="free_to_paid_conversion",
        assumptions=sample_assumptions
    )
    assert res["has_flip_point"] is True
    assert 0.001 < res["threshold"] < 0.05
    assert "outperforms" in res["statement"]

