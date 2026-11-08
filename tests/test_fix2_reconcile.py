import pytest
import random
from state.schemas import Assumption, Decision
from simulation.reconcile import reconcile_assumptions, ReconciledParams
from simulation.engine import simulate, extract_scenario_params_from_reconciled
from report.decision_logic import get_min_runway
from data.loader import load_company_data

def test_reconcile_order_independence():
    asms = [
        Assumption(name="free_to_paid_conversion", low=0.010, base=0.015, high=0.022, unit="rate", provenance="simulated_estimate", confidence=0.8, proposed_by="CFO"),
        Assumption(name="free_to_paid_conversion", low=0.025, base=0.035, high=0.050, unit="rate", provenance="external_research", confidence=0.6, proposed_by="Growth"),
        Assumption(name="infra_cost_per_free_user", low=0.75, base=1.15, high=1.85, unit="USD/user/month", provenance="verified_data", confidence=0.9, proposed_by="CTO"),
        Assumption(name="unmodeled_noise", low=1, base=2, high=3, unit="count", provenance="ai_assumption", proposed_by="Product")
    ]

    # Reconcile in normal order
    r1 = reconcile_assumptions(asms)
    
    # Shuffle and reconcile
    asms_shuffled = list(asms)
    random.seed(42)
    random.shuffle(asms_shuffled)
    r2 = reconcile_assumptions(asms_shuffled)

    assert r1.params == r2.params
    assert "free_to_paid_conversion" in r1.params
    # Unmodeled noise parameter excluded from simulated params
    assert "unmodeled_noise" not in r1.params

    # Contested check (CFO [0.010, 0.022] vs Growth [0.025, 0.050] do not overlap)
    conv_spec = r1.params["free_to_paid_conversion"]
    assert conv_spec.contested is True
    # Range is union: min(0.010, 0.025)=0.010, max(0.022, 0.050)=0.050
    assert conv_spec.low == 0.010
    assert conv_spec.high == 0.050
    # Base is confidence-weighted: (0.015*0.8 + 0.035*0.6) / (0.8 + 0.6) = (0.012 + 0.021) / 1.4 = 0.033 / 1.4 = 0.02357
    expected_base = (0.015 * 0.8 + 0.035 * 0.6) / (0.8 + 0.6)
    assert abs(conv_spec.base - expected_base) < 1e-4

def test_deterministic_simulation_id():
    data = load_company_data()
    asms = [
        Assumption(name="free_to_paid_conversion", low=0.01, base=0.02, high=0.03, unit="rate", provenance="simulated_estimate", proposed_by="CFO")
    ]
    r = reconcile_assumptions(asms)
    run1 = simulate("B_usage_caps", "expected", r, company_data=data, seed=42)
    run2 = simulate("B_usage_caps", "expected", r, company_data=data, seed=42)
    assert run1.id == run2.id
    assert not run1.id.endswith("None")

def test_get_min_runway_precedence():
    comp = {"financials": {"target_min_runway_months": 12.0}}
    # Decision constraint overrides company target
    dec_with_constraint = Decision(id="d1", type="free_plan", question="?", objective="?", constraints={"min_runway_months": 14.0})
    assert get_min_runway(dec_with_constraint, comp) == 14.0

    # Falls back to company target if no decision constraint
    dec_no_constraint = Decision(id="d2", type="free_plan", question="?", objective="?")
    assert get_min_runway(dec_no_constraint, comp) == 12.0

    # Falls back to 10.0 default
    assert get_min_runway(dec_no_constraint, {}) == 10.0
