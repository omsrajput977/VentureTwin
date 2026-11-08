import uuid
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from state.schemas import Assumption, SimulationRun
from simulation.saas_model import run_saas_dynamics
from data.loader import load_company_data

def extract_scenario_params(
    assumptions: List[Assumption],
    scenario: str
) -> Dict[str, float]:
    """
    Extracts deterministic parameter values for conservative, expected, optimistic,
    or stress test scenarios.
    """
    params: Dict[str, float] = {}

    cost_levers = {
        "infra_cost_per_free_user",
        "paid_to_free_cannibalization",
        "free_user_ticket_rate"
    }

    for asm in assumptions:
        if scenario == "expected":
            params[asm.name] = asm.base
        elif scenario == "conservative":
            # For conservative: low on benefits, high on costs
            params[asm.name] = asm.high if asm.name in cost_levers else asm.low
        elif scenario == "optimistic":
            # For optimistic: high on benefits, low on costs
            params[asm.name] = asm.low if asm.name in cost_levers else asm.high
        elif scenario == "stress_infra":
            val = asm.base
            if asm.name == "infra_cost_per_free_user":
                val = asm.high * 2.0
            params[asm.name] = val
        elif scenario == "stress_churn":
            params[asm.name] = asm.base
        else:
            params[asm.name] = asm.base

    # Strategy C paid funnel lift scenario scaling
    if scenario == "conservative":
        params["paid_funnel_lift"] = 1.08
    elif scenario == "optimistic":
        params["paid_funnel_lift"] = 1.28
    else:
        params["paid_funnel_lift"] = 1.18

    # Ensure defaults if assumptions list didn't include certain parameters
    defaults = {
        "monthly_free_signups": 3800.0,
        "free_to_paid_conversion": 0.018,
        "infra_cost_per_free_user": 1.15,
        "paid_to_free_cannibalization": 0.08,
        "free_user_ticket_rate": 0.12
    }
    for k, v in defaults.items():
        if k not in params:
            params[k] = v

    return params


def simulate(
    strategy: str,
    scenario: str,
    assumptions: List[Assumption],
    company_data: Optional[Dict[str, Any]] = None,
    seed: int = 42
) -> SimulationRun:
    """
    Simulates a strategy under a specific scenario deterministically.
    """
    data = company_data or load_company_data()
    params = extract_scenario_params(assumptions, scenario)
    outputs = run_saas_dynamics(months=24, strategy=strategy, params=params, company_data=data)

    run_id = f"sim_{strategy[:1].lower()}_{scenario[:4]}_{uuid.uuid4().hex[:6]}"
    return SimulationRun(
        id=run_id,
        strategy=strategy,
        scenario=scenario,
        parameters=params,
        outputs=outputs,
        seed=seed
    )


def run_monte_carlo(
    strategy: str,
    assumptions: List[Assumption],
    company_data: Optional[Dict[str, Any]] = None,
    n_samples: int = 300,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Runs Monte Carlo sampling across assumption ranges to compute confidence distributions.
    """
    np.random.seed(seed)
    data = company_data or load_company_data()

    samples_net_12 = []
    samples_mrr_12 = []
    samples_runway_12 = []

    # Map assumptions to distributions
    asm_map = {a.name: a for a in assumptions}
    names = ["free_to_paid_conversion", "monthly_free_signups", "infra_cost_per_free_user", "paid_to_free_cannibalization"]

    for _ in range(n_samples):
        sampled_params = {}
        for name in names:
            if name in asm_map:
                a = asm_map[name]
                # Triangular distribution (low, mode=base, high)
                sampled_params[name] = float(np.random.triangular(a.low, a.base, a.high))
            else:
                sampled_params[name] = extract_scenario_params(assumptions, "expected").get(name, 1.0)

        out = run_saas_dynamics(months=12, strategy=strategy, params=sampled_params, company_data=data)
        samples_net_12.append(out["net_contribution_12"])
        samples_mrr_12.append(out["mrr_12"])
        samples_runway_12.append(out["runway_months_12"])

    arr_net = np.array(samples_net_12)
    return {
        "strategy": strategy,
        "n_samples": n_samples,
        "seed": seed,
        "net_contribution_12": {
            "mean": round(float(np.mean(arr_net)), 2),
            "std": round(float(np.std(arr_net)), 2),
            "p10": round(float(np.percentile(arr_net, 10)), 2),
            "p50": round(float(np.percentile(arr_net, 50)), 2),
            "p90": round(float(np.percentile(arr_net, 90)), 2),
            "prob_positive": round(float(np.mean(arr_net > 0)), 4)
        },
        "mrr_12_p50": round(float(np.percentile(samples_mrr_12, 50)), 2),
        "runway_months_12_p50": round(float(np.percentile(samples_runway_12, 50)), 1)
    }


def run_sensitivity_analysis(
    strategy: str,
    assumptions: List[Assumption],
    company_data: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Computes One-At-A-Time (OAT) parameter variation for Tornado chart ranking.
    """
    data = company_data or load_company_data()
    base_params = extract_scenario_params(assumptions, "expected")
    base_out = run_saas_dynamics(months=12, strategy=strategy, params=base_params, company_data=data)
    baseline_net = base_out["net_contribution_12"]

    tornado_items = []
    for asm in assumptions:
        # Vary low
        low_params = dict(base_params)
        low_params[asm.name] = asm.low
        low_res = run_saas_dynamics(months=12, strategy=strategy, params=low_params, company_data=data)

        # Vary high
        high_params = dict(base_params)
        high_params[asm.name] = asm.high
        high_res = run_saas_dynamics(months=12, strategy=strategy, params=high_params, company_data=data)

        low_net = low_res["net_contribution_12"]
        high_net = high_res["net_contribution_12"]
        swing = abs(high_net - low_net)

        tornado_items.append({
            "assumption_name": asm.name,
            "low_value": asm.low,
            "high_value": asm.high,
            "base_value": asm.base,
            "unit": asm.unit,
            "net_contribution_at_low": round(low_net, 2),
            "net_contribution_at_high": round(high_net, 2),
            "swing": round(swing, 2),
            "impact_rank": 0
        })

    # Sort descending by swing
    tornado_items.sort(key=lambda x: x["swing"], reverse=True)
    for idx, item in enumerate(tornado_items):
        item["impact_rank"] = idx + 1

    return tornado_items


def find_flip_point(
    strategy_a: str,
    strategy_b: str,
    variable_name: str,
    assumptions: List[Assumption],
    company_data: Optional[Dict[str, Any]] = None,
    search_range: Optional[Tuple[float, float]] = None
) -> Dict[str, Any]:
    """
    Finds the exact threshold value of variable_name where strategy_a and strategy_b cross.
    Uses binary search bisection.
    """
    data = company_data or load_company_data()
    asm = next((a for a in assumptions if a.name == variable_name), None)
    low_bound, high_bound = search_range or ((asm.low * 0.5, asm.high * 2.0) if asm else (0.005, 0.06))

    base_params = extract_scenario_params(assumptions, "expected")

    def eval_diff(val: float) -> float:
        p = dict(base_params)
        p[variable_name] = val
        out_a = run_saas_dynamics(months=12, strategy=strategy_a, params=p, company_data=data)
        out_b = run_saas_dynamics(months=12, strategy=strategy_b, params=p, company_data=data)
        return out_a["net_contribution_12"] - out_b["net_contribution_12"]

    f_low = eval_diff(low_bound)
    f_high = eval_diff(high_bound)

    # Check if a root exists in range
    if f_low * f_high > 0:
        return {
            "has_flip_point": False,
            "variable_name": variable_name,
            "statement": f"{strategy_a} dominates {strategy_b} across entire tested range ({low_bound:.3f} to {high_bound:.3f}).",
            "threshold": None
        }

    # Bisection search
    left = low_bound
    right = high_bound
    for _ in range(40):
        mid = (left + right) / 2.0
        f_mid = eval_diff(mid)
        if abs(f_mid) < 1.0 or abs(right - left) < 0.0001:
            break
        if f_low * f_mid <= 0:
            right = mid
        else:
            left = mid
            f_low = f_mid

    threshold = round((left + right) / 2.0, 4)
    pct_str = f"{threshold * 100:.2f}%" if "conversion" in variable_name or "rate" in variable_name else f"{threshold:,.2f}"

    statement = (
        f"{strategy_a.replace('_', ' ')} outperforms {strategy_b.replace('_', ' ')} "
        f"only if {variable_name.replace('_', ' ')} stays above {pct_str}."
    )

    return {
        "has_flip_point": True,
        "variable_name": variable_name,
        "threshold": threshold,
        "statement": statement,
        "strategy_a": strategy_a,
        "strategy_b": strategy_b
    }
