from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from state.schemas import Assumption
from simulation.params import SIM_PARAMS, SimParamSpec

class ReconciledParam(BaseModel):
    name: str
    low: float
    base: float
    high: float
    unit: str
    favorable_direction: str
    contested: bool = False
    contributors: List[str] = Field(default_factory=list)

class ReconciledParams(BaseModel):
    params: Dict[str, ReconciledParam] = Field(default_factory=dict)
    context_assumptions: List[Assumption] = Field(default_factory=list)

    @property
    def expected_params(self) -> Dict[str, float]:
        return {k: v.base for k, v in self.params.items()}

def reconcile_assumptions(assumptions: List[Assumption]) -> ReconciledParams:
    """
    Deterministically reconciles all agent assumptions into one canonical parameter set.
    Sorts inputs by (proposed_by, name) so the output is 100% order-independent.
    Excludes fallback_degraded assumptions.
    """
    # 1. Filter out degraded fallback assumptions
    active_asms = [a for a in assumptions if a.provenance != "fallback_degraded"]

    # 2. Sort by (proposed_by, name) for strict order independence
    sorted_asms = sorted(active_asms, key=lambda a: (a.proposed_by or "", a.name))

    grouped: Dict[str, List[Assumption]] = {}
    context_asms: List[Assumption] = []

    for a in sorted_asms:
        if a.name in SIM_PARAMS:
            grouped.setdefault(a.name, []).append(a)
        else:
            context_asms.append(a)

    reconciled_dict: Dict[str, ReconciledParam] = {}

    # 3. Reconcile simulated parameters
    for name, group in grouped.items():
        spec = SIM_PARAMS[name]
        low = min(a.low for a in group)
        high = max(a.high for a in group)
        
        # Confidence-weighted base
        total_conf = sum(a.confidence for a in group)
        if total_conf > 0:
            base = sum(a.base * a.confidence for a in group) / total_conf
        else:
            base = sum(a.base for a in group) / len(group)

        # Clamping to parameter bounds
        low = max(spec.lower_bound, min(spec.upper_bound, low))
        high = max(spec.lower_bound, min(spec.upper_bound, high))
        base = max(low, min(high, base))

        # Range overlap check
        contested = False
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a1, a2 = group[i], group[j]
                    if a1.high < a2.low or a2.high < a1.low:
                        contested = True
                        break

        contributors = sorted(list({a.proposed_by for a in group if a.proposed_by}))

        reconciled_dict[name] = ReconciledParam(
            name=name,
            low=round(low, 4),
            base=round(base, 4),
            high=round(high, 4),
            unit=spec.unit,
            favorable_direction=spec.favorable_direction,
            contested=contested,
            contributors=contributors
        )

    # 4. Fill in defaults for SIM_PARAMS not explicitly proposed by agents
    for name, spec in SIM_PARAMS.items():
        if name not in reconciled_dict:
            reconciled_dict[name] = ReconciledParam(
                name=name,
                low=spec.lower_bound,
                base=spec.default,
                high=spec.upper_bound,
                unit=spec.unit,
                favorable_direction=spec.favorable_direction,
                contested=False,
                contributors=["default"]
            )

    return ReconciledParams(params=reconciled_dict, context_assumptions=context_asms)
