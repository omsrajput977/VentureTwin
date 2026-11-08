import pytest
import copy
from simulation.saas_model import run_saas_dynamics
from data.loader import load_company_data, load_model_config

def test_tradeoff_a_and_b_each_win_somewhere():
    data = load_company_data()
    # At moderate/low conversion, Strategy B beats A because of lower cost/cannibalization
    params_mod = {
        "monthly_free_signups": 3800.0,
        "free_to_paid_conversion": 0.015,
        "paid_to_free_cannibalization": 0.08,
        "infra_cost_per_free_user": 1.15,
        "usage_cap_infra_reduction": 0.35,
        "usage_cap_cannibalization_reduction": 0.50,
        "activation_drop_from_gating": 0.15,
        "cap_conversion_uplift": 0.10
    }
    out_a_mod = run_saas_dynamics(12, "A_limited_features", params_mod, data)
    out_b_mod = run_saas_dynamics(12, "B_usage_caps", params_mod, data)
    assert out_b_mod["net_contribution_12"] > out_a_mod["net_contribution_12"]

    # At very high conversion (e.g. 8%) and low gating drop, Strategy A beats B
    # because A retains 100% full signup activation volume
    params_high = dict(params_mod)
    params_high["free_to_paid_conversion"] = 0.08
    params_high["activation_drop_from_gating"] = 0.35  # heavy activation penalty on B
    params_high["cap_conversion_uplift"] = 0.02

    out_a_high = run_saas_dynamics(12, "A_limited_features", params_high, data)
    out_b_high = run_saas_dynamics(12, "B_usage_caps", params_high, data)
    assert out_a_high["net_contribution_12"] > out_b_high["net_contribution_12"]

def test_model_constants_affect_output():
    data = load_company_data()
    params = {
        "monthly_free_signups": 3800.0,
        "free_to_paid_conversion": 0.02,
        "infra_cost_per_free_user": 1.15
    }
    config1 = load_model_config()
    config2 = copy.deepcopy(config1)
    config2["monthly_support_cost_per_fte"] = 15000.0  # Much higher support cost

    out1 = run_saas_dynamics(12, "B_usage_caps", params, data, model_config=config1)
    out2 = run_saas_dynamics(12, "B_usage_caps", params, data, model_config=config2)

    assert out1["net_contribution_12"] != out2["net_contribution_12"]
    assert out1["net_contribution_12"] > out2["net_contribution_12"]

def test_monotonicity_invariants():
    data = load_company_data()
    params_base = {"free_to_paid_conversion": 0.02, "infra_cost_per_free_user": 1.0}
    params_high_conv = {"free_to_paid_conversion": 0.04, "infra_cost_per_free_user": 1.0}
    params_high_infra = {"free_to_paid_conversion": 0.02, "infra_cost_per_free_user": 3.0}

    out_base = run_saas_dynamics(12, "A_limited_features", params_base, data)
    out_conv = run_saas_dynamics(12, "A_limited_features", params_high_conv, data)
    out_infra = run_saas_dynamics(12, "A_limited_features", params_high_infra, data)

    # Higher conversion never lowers MRR or net contribution
    assert out_conv["mrr_12"] >= out_base["mrr_12"]
    assert out_conv["net_contribution_12"] > out_base["net_contribution_12"]

    # Higher infra cost never raises net contribution
    assert out_infra["net_contribution_12"] < out_base["net_contribution_12"]
