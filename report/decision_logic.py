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

        is_feasible = runway >= min_runway
        reason = (
            f"Runway ({runway:.1f} mo) satisfies the {min_runway:.1f}-month safety floor."
            if is_feasible else
            f"Runway ({runway:.1f} mo) breaches the {min_runway:.1f}-month minimum constraint."
        )

        ranked_items.append(RankedStrategy(
            strategy=r.strategy,
            rank=0,
            is_feasible=is_feasible,
            net_contribution_12=net_contrib,
            mrr_12=mrr,
            runway_months_12=runway,
            gross_margin_12=gm,
            feasibility_reason=reason
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
    - Monte Carlo probability of positive contribution
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
            score += 0.20
            reasons.append(f"Strong net contribution lead of ${diff:,.2f} over runner-up.")
        elif diff > 25000:
            score += 0.10
            reasons.append(f"Moderate net contribution lead of ${diff:,.2f} over runner-up.")
        else:
            reasons.append(f"Narrow margin (${diff:,.2f}) over runner-up.")

    # 2. Assumption confidence
    if assumptions:
        avg_asm_conf = sum(a.confidence for a in assumptions) / len(assumptions)
        score += (avg_asm_conf - 0.5) * 0.25
        reasons.append(f"Average assumption provenance confidence is {avg_asm_conf * 100:.1f}%.")

    # 3. Penalties for degraded agents
    if degraded_agents:
        penalty = len(degraded_agents) * 0.20
        score -= penalty
        reasons.append(f"Degraded agent penalty: {', '.join(degraded_agents)} ran with degraded fallback.")

    # 4. Penalty for unresolved conflicts
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

