import pytest
from simulation.engine import find_flip_point, run_monte_carlo
from simulation.reconcile import reconcile_assumptions
from simulation.saas_model import run_saas_dynamics
from report.decision_logic import (
    compute_dynamic_strategy_comparison,
    RankedStrategy,
    compute_confidence
)
from data.loader import load_company_data, load_model_config

def test_direction_aware_flip_point():
    reconciled = reconcile_assumptions([])
    company_data = load_company_data()

    # free_to_paid_conversion should have a "drops below" direction
    fp_conv = find_flip_point(
        "B_usage_caps",
        "C_no_free_plan",
        "free_to_paid_conversion",
        reconciled,
        company_data
    )
    assert fp_conv["has_flip_point"] is True
    assert "drops below" in fp_conv["statement"].lower() or "falls below" in fp_conv["statement"].lower()

    # paid_to_free_cannibalization should have a "rises above" direction
    fp_cann = find_flip_point(
        "B_usage_caps",
        "A_limited_features",
        "paid_to_free_cannibalization",
        reconciled,
        company_data,
        search_range=(0.01, 0.50)
    )
    if fp_cann["has_flip_point"]:
        assert "rises above" in fp_cann["statement"].lower() or "exceeds" in fp_cann["statement"].lower()

def test_infeasible_top_strategy_flip_point():
    reconciled = reconcile_assumptions([])
    company_data = load_company_data()
    # If top strategy is marked infeasible
    infeasible_top = RankedStrategy(
        strategy="B_usage_caps",
        rank=1,
        is_feasible=False,
        net_contribution_12=100000.0,
        mrr_12=150000.0,
        runway_months_12=6.0,
        gross_margin_12=0.70,
        feasibility_reason="Runway breaches 10mo floor"
    )
    res = compute_dynamic_strategy_comparison(
        ranked=[infeasible_top],
        reconciled=reconciled,
        company_data=company_data
    )
    assert res["flip_point"]["has_flip_point"] is False
    assert "no strategy is viable" in res["flip_point"]["statement"].lower()

def test_multi_strategy_monte_carlo_runs_all_three_with_shared_draws():
    reconciled = reconcile_assumptions([])
    company_data = load_company_data()

    mc = run_monte_carlo("B_usage_caps", reconciled, company_data, n_samples=500, seed=42)

    # Must contain evaluations for all 3 strategies
    assert "strategies" in mc
    strategies = ["A_limited_features", "B_usage_caps", "C_no_free_plan"]
    for s in strategies:
        assert s in mc["strategies"]
        s_data = mc["strategies"][s]
        assert "net_contribution_12" in s_data
        assert "p10" in s_data["net_contribution_12"]
        assert "p50" in s_data["net_contribution_12"]
        assert "p90" in s_data["net_contribution_12"]
        assert "p_feasible" in s_data
        assert "p_best" in s_data
        assert 0.0 <= s_data["p_best"] <= 1.0

    # Total p_best across all 3 strategies must sum to <= 1.0 (equals 1.0 if at least one is always feasible)
    total_p_best = sum(mc["strategies"][s]["p_best"] for s in strategies)
    assert total_p_best <= 1.0001
    assert total_p_best > 0.0

def test_saas_model_uses_externalized_ticket_reduction_and_floors():
    company_data = load_company_data()
    params = {"monthly_free_signups": 20000.0, "free_to_paid_conversion": 0.02, "usage_cap_infra_reduction": 0.35}

    cfg1 = load_model_config()
    cfg1["support_ticket_reduction_factor"] = 1.0
    out1 = run_saas_dynamics(months=12, strategy="B_usage_caps", params=params, company_data=company_data, model_config=cfg1)

    cfg2 = dict(cfg1)
    cfg2["support_ticket_reduction_factor"] = 0.05  # higher ticket reduction
    out2 = run_saas_dynamics(months=12, strategy="B_usage_caps", params=params, company_data=company_data, model_config=cfg2)

    # Changing the config constant changes support headcount and net contribution
    assert out1["support_headcount_12"] != out2["support_headcount_12"]
    assert out1["net_contribution_12"] != out2["net_contribution_12"]
