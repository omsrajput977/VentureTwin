import hashlib
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
from state.schemas import Assumption, SimulationRun
from simulation.saas_model import run_saas_dynamics
from simulation.params import SIM_PARAMS
from simulation.reconcile import ReconciledParams, reconcile_assumptions
from data.loader import load_company_data
from report.decision_logic import get_min_runway

def extract_scenario_params_from_reconciled(
    reconciled: ReconciledParams,
    scenario: str
) -> Dict[str, float]:
    """
    Extracts scenario parameters based on SIM_PARAMS favorable directions and stress tests.
    """
    params: Dict[str, float] = {}

    for name, p in reconciled.params.items():
        if scenario == "expected":
            params[name] = p.base
        elif scenario == "conservative":
            # Unfavorable bound
            params[name] = p.low if p.favorable_direction == "higher" else p.high
        elif scenario == "optimistic":
            # Favorable bound
            params[name] = p.high if p.favorable_direction == "higher" else p.low
        elif scenario == "stress_infra_doubles":
            val = p.base
            if name == "infra_cost_per_free_user":
                val = (p.high if p.favorable_direction == "lower" else p.low) * 2.0
            params[name] = val
        elif scenario == "stress_conversion_collapse":
            val = p.base
            if name == "free_to_paid_conversion":
                val = (p.low if p.favorable_direction == "higher" else p.high) * 0.5
            params[name] = val
        elif scenario == "stress_large_customer_churn":
            params[name] = p.base
        else:
            params[name] = p.base

    return params


def generate_deterministic_sim_id(strategy: str, scenario: str, params: Dict[str, float]) -> str:
    """
    Computes a deterministic hash-based simulation ID for 100% reproducible reports.
    """
    sorted_items = sorted(params.items())
    key_str = f"{strategy}||{scenario}||" + json.dumps(sorted_items)
    h = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:8]
    strat_code = strategy.split("_")[0].lower()
    scen_code = scenario.split("_")[0][:4].lower()
    return f"sim_{strat_code}_{scen_code}_{h}"


def simulate(
    strategy: str,
    scenario: str,
    assumptions_or_reconciled: Optional[Union[List[Assumption], ReconciledParams]] = None,
    company_data: Optional[Dict[str, Any]] = None,
    seed: int = 42,
    assumptions: Optional[List[Assumption]] = None
) -> SimulationRun:
    """
    Simulates a strategy under a specific scenario deterministically.
    """
    target = assumptions_or_reconciled if assumptions_or_reconciled is not None else assumptions
    if target is None:
        target = []

    data = company_data or load_company_data()

    if isinstance(target, ReconciledParams):
        reconciled = target
    else:
        reconciled = reconcile_assumptions(target)

    params = extract_scenario_params_from_reconciled(reconciled, scenario)
    outputs = run_saas_dynamics(months=24, strategy=strategy, params=params, company_data=data)

    run_id = generate_deterministic_sim_id(strategy, scenario, params)
    return SimulationRun(
        id=run_id,
        strategy=strategy,
        scenario=scenario,
        parameters=params,
        outputs=outputs,
        seed=seed
    )


def run_monte_carlo(
    strategy: str = "B_usage_caps",
    assumptions_or_reconciled: Optional[Union[List[Assumption], ReconciledParams]] = None,
    company_data: Optional[Dict[str, Any]] = None,
    n_samples: int = 500,
    seed: int = 42,
    assumptions: Optional[List[Assumption]] = None,
    all_strategies: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Runs Monte Carlo simulation with local Generator across all strategies.
    Apples-to-apples comparison on shared sample draws.
    Computes p10/p50/p90, p_feasible, and dynamic p_best.
    """
    target = assumptions_or_reconciled if assumptions_or_reconciled is not None else assumptions
    if target is None:
        target = []

    rng = np.random.default_rng(seed)
    data = company_data or load_company_data()
    min_runway = get_min_runway(None, data)

    if isinstance(target, ReconciledParams):
        reconciled = target
    else:
        reconciled = reconcile_assumptions(target)

    active_strategies = all_strategies or ["A_limited_features", "B_usage_caps", "C_no_free_plan"]
    param_names = list(reconciled.params.keys())

    # Generate shared parameter draws
    shared_draws = []
    for _ in range(n_samples):
        sampled_params = {}
        for name in param_names:
            p = reconciled.params[name]
            if abs(p.high - p.low) < 1e-6:
                sampled_params[name] = p.base
            else:
                sampled_params[name] = float(rng.triangular(p.low, p.base, p.high))
        shared_draws.append(sampled_params)

    # Evaluate all strategies
    strat_results = {s: {"net": [], "mrr": [], "runway": []} for s in active_strategies}
    best_counts = {s: 0 for s in active_strategies}

    for draw in shared_draws:
        draw_outputs = {}
        for s in active_strategies:
            out = run_saas_dynamics(months=12, strategy=s, params=draw, company_data=data)
            strat_results[s]["net"].append(out["net_contribution_12"])
            strat_results[s]["mrr"].append(out["mrr_12"])
            strat_results[s]["runway"].append(out["runway_months_12"])
            draw_outputs[s] = out

        # Find best strategy in this draw among feasible ones
        feasible_strats = []
        for s in active_strategies:
            r12 = draw_outputs[s]["runway_months_12"]
            hist = draw_outputs[s].get("history", [])
            min_r = min((m["runway_months"] for m in hist[:12]), default=r12)
            if r12 >= min_runway and min_r >= min_runway:
                feasible_strats.append(s)

        if feasible_strats:
            best_strat = max(feasible_strats, key=lambda s: draw_outputs[s]["net_contribution_12"])
            best_counts[best_strat] += 1

    # Build per-strategy summaries
    strategies_summary = {}
    quantiles_summary = {}
    probabilities_summary = {}

    for s in active_strategies:
        arr_net = np.array(strat_results[s]["net"])
        arr_mrr = np.array(strat_results[s]["mrr"])
        arr_runway = np.array(strat_results[s]["runway"])

        p_feas = float(np.mean(arr_runway >= min_runway))
        p_bst = float(best_counts[s] / n_samples)

        s_summary = {
            "strategy": s,
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
            "mrr_12": {
                "p10": round(float(np.percentile(arr_mrr, 10)), 2),
                "p50": round(float(np.percentile(arr_mrr, 50)), 2),
                "p90": round(float(np.percentile(arr_mrr, 90)), 2)
            },
            "runway_months_12": {
                "p10": round(float(np.percentile(arr_runway, 10)), 1),
                "p50": round(float(np.percentile(arr_runway, 50)), 1),
                "p90": round(float(np.percentile(arr_runway, 90)), 1)
            },
            "p_feasible": round(p_feas, 4),
            "p_best": round(p_bst, 4)
        }
        strategies_summary[s] = s_summary
        quantiles_summary[s] = {
            "net_contribution_12": s_summary["net_contribution_12"],
            "mrr_12": s_summary["mrr_12"],
            "runway_months_12": s_summary["runway_months_12"]
        }
        probabilities_summary[s] = {
            "p_feasible": round(p_feas, 4),
            "p_best": round(p_bst, 4)
        }

    target_strat = strategy if strategy in strategies_summary else (active_strategies[0] if active_strategies else "B_usage_caps")
    target_summary = strategies_summary[target_strat]

    result = dict(target_summary)
    result["strategies"] = strategies_summary
    result["quantiles"] = quantiles_summary
    result["probabilities"] = probabilities_summary
    return result


def run_sensitivity_analysis(
    strategy: str,
    assumptions_or_reconciled: Optional[Union[List[Assumption], ReconciledParams]] = None,
    company_data: Optional[Dict[str, Any]] = None,
    assumptions: Optional[List[Assumption]] = None
) -> List[Dict[str, Any]]:
    """
    Computes One-At-A-Time (OAT) parameter variation for simulated parameters only.
    No duplicate rows and no zero-swing rows for non-simulated assumptions.
    """
    target = assumptions_or_reconciled if assumptions_or_reconciled is not None else assumptions
    if target is None:
        target = []

    data = company_data or load_company_data()
    explicit_names = {a.name for a in target} if isinstance(target, list) and target else None

    if isinstance(target, ReconciledParams):
        reconciled = target
    else:
        reconciled = reconcile_assumptions(target)

    base_params = extract_scenario_params_from_reconciled(reconciled, "expected")
    base_out = run_saas_dynamics(months=12, strategy=strategy, params=base_params, company_data=data)

    tornado_items = []
    for name, p in reconciled.params.items():
        if explicit_names and name not in explicit_names:
            continue
        if abs(p.high - p.low) < 1e-6:
            continue

        low_params = dict(base_params)
        low_params[name] = p.low
        low_res = run_saas_dynamics(months=12, strategy=strategy, params=low_params, company_data=data)

        high_params = dict(base_params)
        high_params[name] = p.high
        high_res = run_saas_dynamics(months=12, strategy=strategy, params=high_params, company_data=data)

        low_net = low_res["net_contribution_12"]
        high_net = high_res["net_contribution_12"]
        swing = abs(high_net - low_net)

        tornado_items.append({
            "assumption_name": name,
            "low_value": p.low,
            "high_value": p.high,
            "base_value": p.base,
            "unit": p.unit,
            "net_contribution_at_low": round(low_net, 2),
            "net_contribution_at_high": round(high_net, 2),
            "swing": round(swing, 2),
            "impact_rank": 0
        })

    tornado_items.sort(key=lambda x: x["swing"], reverse=True)
    for idx, item in enumerate(tornado_items):
        item["impact_rank"] = idx + 1

    return tornado_items


def find_flip_point(
    strategy_a: str,
    strategy_b: str,
    variable_name: str,
    assumptions_or_reconciled: Optional[Union[List[Assumption], ReconciledParams]] = None,
    company_data: Optional[Dict[str, Any]] = None,
    search_range: Optional[Tuple[float, float]] = None,
    assumptions: Optional[List[Assumption]] = None
) -> Dict[str, Any]:
    """
    Finds exact threshold value of variable_name where strategy_a and strategy_b cross.
    """
    target = assumptions_or_reconciled if assumptions_or_reconciled is not None else assumptions
    if target is None:
        target = []

    data = company_data or load_company_data()

    if isinstance(target, ReconciledParams):
        reconciled = target
    else:
        reconciled = reconcile_assumptions(target)

    p_spec = reconciled.params.get(variable_name)
    low_bound, high_bound = search_range or (
        (min(0.001, p_spec.low * 0.25), max(0.08, p_spec.high * 2.0)) if p_spec else (0.001, 0.08)
    )

    base_params = extract_scenario_params_from_reconciled(reconciled, "expected")

    def eval_diff(val: float) -> float:
        p = dict(base_params)
        p[variable_name] = val
        out_a = run_saas_dynamics(months=12, strategy=strategy_a, params=p, company_data=data)
        out_b = run_saas_dynamics(months=12, strategy=strategy_b, params=p, company_data=data)
        return out_a["net_contribution_12"] - out_b["net_contribution_12"]

    f_low = eval_diff(low_bound)
    f_high = eval_diff(high_bound)

    if f_low * f_high > 0:
        return {
            "has_flip_point": False,
            "variable_name": variable_name,
            "statement": f"{strategy_a} dominates {strategy_b} across tested range ({low_bound:.4f} to {high_bound:.4f}).",
            "threshold": None
        }

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

    if f_low < f_high:
        direction_clause = f"drops below {pct_str}"
    else:
        direction_clause = f"rises above {pct_str}"

    statement = (
        f"If {variable_name.replace('_', ' ')} {direction_clause}, "
        f"{strategy_a.replace('_', ' ')} is overtaken by {strategy_b.replace('_', ' ')}"
    )

    return {
        "has_flip_point": True,
        "variable_name": variable_name,
        "threshold": threshold,
        "statement": statement,
        "strategy_a": strategy_a,
        "strategy_b": strategy_b
    }
