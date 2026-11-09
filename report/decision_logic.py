from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel
from state.schemas import SimulationRun, Assumption, Conflict

class RankedStrategy(BaseModel):
    strategy: str
    rank: int
    is_feasible: bool
    net_contribution_12: float
    mrr_12: float
    runway_months_12: float
    gross_margin_12: float
    feasibility_reason: str
    min_runway_months: Optional[float] = None

class ConfidenceAssessment(BaseModel):
    level: Literal["Low", "Medium", "High"]
    score: float
    reasons: List[str]

def get_min_runway(decision: Optional[Any] = None, company_data: Optional[Dict[str, Any]] = None) -> float:
    """
    Returns the effective minimum runway threshold.
    Precedence: Decision.constraints -> Company financial target -> 10.0 default.
    """
    if decision and getattr(decision, "constraints", None):
        if "min_runway_months" in decision.constraints:
            return float(decision.constraints["min_runway_months"])
    if company_data and "financials" in company_data:
        fin = company_data["financials"]
        if "target_min_runway_months" in fin:
            return float(fin["target_min_runway_months"])
    return 10.0

def rank_strategies(
    sim_runs: List[SimulationRun],
    constraints: Optional[Dict[str, Any]] = None,
    min_runway_default: float = 10.0,
    company_data: Optional[Dict[str, Any]] = None
) -> List[RankedStrategy]:
    min_runway = min_runway_default
    if constraints and "min_runway_months" in constraints:
        min_runway = float(constraints["min_runway_months"])
    elif company_data:
        min_runway = get_min_runway(None, company_data)

    # Extract expected runs
    expected_runs = [r for r in sim_runs if r.scenario == "expected"]
    if not expected_runs:
        expected_runs = sim_runs

    ranked_items: List[RankedStrategy] = []
    for r in expected_runs:
        out = r.outputs
        runway = out.get("runway_months_12", 0.0)
        net_contrib = out.get("net_contribution_12", 0.0)
        mrr = out.get("mrr_12", 0.0)
        gm = out.get("gross_margin_12", 0.0)

        history = out.get("history", [])
        if history:
            min_trajectory_runway = min(m.get("runway_months", 0.0) for m in history[:12])
        else:
            min_trajectory_runway = runway

        is_feasible = (min_trajectory_runway >= min_runway) and (runway >= min_runway)
        effective_runway = min_trajectory_runway if min_trajectory_runway < runway else runway
        reason = (
            f"Runway ({effective_runway:.1f} mo) satisfies the {min_runway:.1f}-month safety floor."
            if is_feasible else
            f"Runway ({effective_runway:.1f} mo) breaches the {min_runway:.1f}-month minimum constraint."
        )

        ranked_items.append(RankedStrategy(
            strategy=r.strategy,
            rank=0,
            is_feasible=is_feasible,
            net_contribution_12=net_contrib,
            mrr_12=mrr,
            runway_months_12=runway,
            gross_margin_12=gm,
            feasibility_reason=reason,
            min_runway_months=min_trajectory_runway
        ))

    # Sort feasible first by net_contribution_12 desc, then infeasible by net_contribution_12 desc
    feasible = [item for item in ranked_items if item.is_feasible]
    infeasible = [item for item in ranked_items if item.is_feasible is False]

    feasible.sort(key=lambda x: (x.net_contribution_12, x.runway_months_12), reverse=True)
    infeasible.sort(key=lambda x: (x.net_contribution_12, x.runway_months_12), reverse=True)

    final_ranked = feasible + infeasible
    for idx, item in enumerate(final_ranked):
        item.rank = idx + 1

    return final_ranked


def compute_dynamic_strategy_comparison(
    ranked: List[RankedStrategy],
    reconciled: Any,
    company_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    from simulation.saas_model import run_saas_dynamics
    from simulation.engine import find_flip_point, extract_scenario_params_from_reconciled
    from data.loader import load_company_data

    data = company_data or load_company_data()

    if not ranked or not ranked[0].is_feasible:
        return {
            "top_strategy": ranked[0].strategy if ranked else "None",
            "runner_up": None,
            "margin_tornado": [],
            "flip_point": {
                "has_flip_point": False,
                "threshold": None,
                "statement": "No strategy is viable under current constraints; flip point analysis omitted."
            }
        }

    s1 = ranked[0].strategy
    s2 = ranked[1].strategy if len(ranked) >= 2 else "C_no_free_plan"
    s3 = ranked[2].strategy if len(ranked) >= 3 else None

    # Compute margin tornado between s1 and s2
    base_params = extract_scenario_params_from_reconciled(reconciled, "expected")
    margin_tornado = []
    for p_name, spec in reconciled.params.items():
        if abs(spec.high - spec.low) < 1e-6:
            continue
        p_low = dict(base_params)
        p_low[p_name] = spec.low
        out_s1_low = run_saas_dynamics(12, s1, p_low, data)
        out_s2_low = run_saas_dynamics(12, s2, p_low, data)
        margin_low = out_s1_low["net_contribution_12"] - out_s2_low["net_contribution_12"]

        p_high = dict(base_params)
        p_high[p_name] = spec.high
        out_s1_high = run_saas_dynamics(12, s1, p_high, data)
        out_s2_high = run_saas_dynamics(12, s2, p_high, data)
        margin_high = out_s1_high["net_contribution_12"] - out_s2_high["net_contribution_12"]

        swing = round(abs(margin_high - margin_low), 2)
        margin_tornado.append({
            "assumption_name": p_name,
            "param": p_name,
            "low_value": spec.low,
            "high_value": spec.high,
            "base_value": spec.base,
            "margin_at_low": round(margin_low, 2),
            "margin_at_high": round(margin_high, 2),
            "net_contribution_at_low": round(margin_low, 2),
            "net_contribution_at_high": round(margin_high, 2),
            "swing": swing
        })
    margin_tornado.sort(key=lambda x: x["swing"], reverse=True)

    # Compute flip point against s2 (or s3 if s2 has no flip point)
    fp = find_flip_point(s1, s2, "free_to_paid_conversion", reconciled, data)
    if not fp.get("has_flip_point") and s3:
        fp = find_flip_point(s1, s3, "free_to_paid_conversion", reconciled, data)

    return {
        "top_strategy": s1,
        "runner_up": s2,
        "margin_tornado": margin_tornado,
        "flip_point": fp
    }


def compute_confidence(
    ranked: List[RankedStrategy],
    mc_summaries: Optional[Dict[str, Any]] = None,
    assumptions: Optional[List[Assumption]] = None,
    degraded_agents: Optional[List[str]] = None,
    conflicts: Optional[List[Conflict]] = None
) -> ConfidenceAssessment:
    """
    Computes data-driven confidence score based on:
    - Margin between 1st and 2nd strategy
    - Monte Carlo probability of positive contribution, p_best, and p_feasible
    - Average assumption confidence
    - Penalties for degraded agents and unresolved conflicts
    """
    reasons = []
    score = 0.50

    if not ranked:
        return ConfidenceAssessment(level="Low", score=0.0, reasons=["No evaluated strategies."])

    top = ranked[0]
    if not top.is_feasible:
        reasons.append("Top strategy is infeasible under minimum runway constraints.")
        score = min(score, 0.25)

    # 1. Margin over runner up
    if len(ranked) >= 2 and top.is_feasible:
        runner_up = ranked[1]
        diff = top.net_contribution_12 - runner_up.net_contribution_12
        if diff > 100000:
            score += 0.15
            reasons.append(f"Strong net contribution lead of ${diff:,.2f} over runner-up.")
        elif diff > 25000:
            score += 0.08
            reasons.append(f"Moderate net contribution lead of ${diff:,.2f} over runner-up.")
        else:
            reasons.append(f"Narrow margin (${diff:,.2f}) over runner-up.")

    # 2. Monte Carlo p_best and p_feasible
    if mc_summaries and top.is_feasible:
        top_mc = None
        if "strategies" in mc_summaries and top.strategy in mc_summaries["strategies"]:
            top_mc = mc_summaries["strategies"][top.strategy]
        elif mc_summaries.get("strategy") == top.strategy:
            top_mc = mc_summaries
        elif "probabilities" in mc_summaries and top.strategy in mc_summaries["probabilities"]:
            top_mc = mc_summaries["probabilities"][top.strategy]

        if top_mc:
            p_best = float(top_mc.get("p_best", 0.0))
            p_feasible = float(top_mc.get("p_feasible", 0.0))
            if p_best >= 0.70 and p_feasible >= 0.90:
                score += 0.15
                reasons.append(f"High Monte Carlo stability: {p_best*100:.1f}% probability of top outcome with {p_feasible*100:.1f}% runway solvency.")
            elif p_best < 0.40 or p_feasible < 0.75:
                score -= 0.15
                reasons.append(f"Monte Carlo risk: strategy is top in only {p_best*100:.1f}% of simulations (runway solvency {p_feasible*100:.1f}%).")
            else:
                reasons.append(f"Moderate Monte Carlo outcome: {p_best*100:.1f}% win rate with {p_feasible*100:.1f}% feasibility.")

    # 3. Assumption confidence
    if assumptions:
        avg_asm_conf = sum(a.confidence for a in assumptions) / len(assumptions)
        score += (avg_asm_conf - 0.5) * 0.25
        reasons.append(f"Average assumption provenance confidence is {avg_asm_conf * 100:.1f}%.")

    # 4. Penalties for degraded agents
    if degraded_agents:
        penalty = len(degraded_agents) * 0.20
        score -= penalty
        score = min(score, 0.65)  # Degraded agents cap confidence at Medium/Low
        reasons.append(f"Degraded agent penalty: {', '.join(degraded_agents)} ran with degraded fallback.")

    # 5. Penalty for unresolved conflicts
    if conflicts:
        unresolved = [c for c in conflicts if c.unresolved]
        if unresolved:
            score -= 0.15
            reasons.append(f"{len(unresolved)} conflict(s) remain unresolved.")

    final_score = max(0.10, min(0.95, score))

    if final_score >= 0.70:
        level = "High"
    elif final_score >= 0.45:
        level = "Medium"
    else:
        level = "Low"

    return ConfidenceAssessment(level=level, score=round(final_score, 2), reasons=reasons)

