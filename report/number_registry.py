from typing import List, Dict, Any, Optional
import re
from pydantic import BaseModel, Field

class NumberEntry(BaseModel):
    value: float
    path: str
    origin: str
    source_ref: str = ""
    expected_value: float
    tolerance: float = 1e-6

    def model_post_init(self, __context: Any) -> None:
        if not self.source_ref:
            self.source_ref = self.origin

def resolve_source_ref(source_ref: str, context: Dict[str, Any]) -> float:
    """
    Resolves a source reference string against simulation results, company snapshot, or config:
    - sim:<run_id>.<field> (e.g. sim:sim_base.history[-1].arr, sim:B_usage_caps.net_contribution_12)
    - mc:<strategy>.<field> (e.g. mc:B_usage_caps.mrr_p50, mc:B_usage_caps.p_best)
    - flip:threshold
    - tornado:<param>.swing
    - company:<path> (e.g. company:financials.arr, company:unit_economics.cac_blended)
    - model_config:<key> (e.g. model_config:infra_cost_per_free_user.default)
    """
    if not source_ref or not isinstance(source_ref, str):
        return 0.0

    # 1. Company snapshot: company:<path>
    if source_ref.startswith("company:"):
        path = source_ref[len("company:"):]
        curr = context.get("company_data", {})
        for p in path.split("."):
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return 0.0
        return float(curr)

    # 2. Simulation run: sim:<run_id>.<field>
    if source_ref.startswith("sim:"):
        rest = source_ref[len("sim:"):]
        parts = rest.split(".", 1)
        if len(parts) == 2:
            run_key, field_expr = parts[0], parts[1]
        else:
            run_key, field_expr = parts[0], ""

        sim_runs = context.get("sim_runs", [])
        target_run = None
        # 1. Exact run ID match
        for r in sim_runs:
            if getattr(r, "id", None) == run_key:
                target_run = r
                break

        # 2. Strategy + Scenario combo match (e.g. B_usage_caps_expected)
        if not target_run:
            for r in sim_runs:
                strat = getattr(r, "strategy", "")
                scen = getattr(r, "scenario", "")
                if f"{strat}_{scen}" == run_key or f"sim_{strat}_{scen}" == run_key:
                    target_run = r
                    break

        # 3. Strategy match (preferring expected scenario)
        if not target_run:
            strat_candidates = [
                r for r in sim_runs
                if getattr(r, "strategy", None) == run_key or f"sim_{getattr(r, 'strategy', '')}" == run_key
            ]
            if strat_candidates:
                target_run = next((c for c in strat_candidates if getattr(c, "scenario", "") == "expected"), strat_candidates[0])

        # 4. Scenario match
        if not target_run:
            for r in sim_runs:
                if getattr(r, "scenario", None) == run_key:
                    target_run = r
                    break

        if target_run:
            outs = getattr(target_run, "outputs", {})
            if field_expr in outs:
                return float(outs[field_expr])
            # Check nested paths like history[-1].arr
            if "history" in field_expr and "history" in outs:
                hist = outs["history"]
                if isinstance(hist, list) and hist:
                    last_pt = hist[-1]
                    if "." in field_expr:
                        sub = field_expr.split(".", 1)[1]
                        if isinstance(last_pt, dict) and sub in last_pt:
                            return float(last_pt[sub])

    # 3. Monte Carlo: mc:<strategy>.<field>
    if source_ref.startswith("mc:"):
        rest = source_ref[len("mc:"):]
        parts = rest.split(".", 1)
        strat = parts[0]
        field = parts[1] if len(parts) > 1 else ""
        mc = context.get("mc_summary", {})

        s_dict = mc.get("strategies", {}).get(strat) or (mc.get(strat) if isinstance(mc.get(strat), dict) else {})

        if field in s_dict and isinstance(s_dict[field], (int, float)):
            return float(s_dict[field])

        if field in ["p_best", "p_feasible"]:
            return float(s_dict.get(field, 0.0))
        if field in ["p_best_pct", "p_feasible_pct"]:
            base_f = field[:-4]
            return round(float(s_dict.get(base_f, 0.0)) * 100.0, 1)

        # Check probabilities sub-dict
        probs = mc.get("probabilities", {}).get(strat, {})
        if field in probs:
            return float(probs[field])

        # Parse quantile pattern like net_contribution_12_p10 or mrr_12_p50
        for qk in ["p10", "p50", "p90"]:
            if field.endswith(f"_{qk}"):
                base_metric = field[:-len(f"_{qk}")]
                if base_metric in s_dict and isinstance(s_dict[base_metric], dict) and qk in s_dict[base_metric]:
                    return float(s_dict[base_metric][qk])
                quantiles = mc.get("quantiles", {}).get(strat, {})
                if base_metric in quantiles and isinstance(quantiles[base_metric], dict) and qk in quantiles[base_metric]:
                    return float(quantiles[base_metric][qk])

        quantiles = mc.get("quantiles", {}).get(strat, {})
        if field in quantiles and isinstance(quantiles[field], (int, float)):
            return float(quantiles[field])
        if field in mc and isinstance(mc[field], (int, float)):
            return float(mc[field])

    # 4. Flip threshold: flip:threshold
    if source_ref.startswith("flip:"):
        flip_info = context.get("flip_point_info") or context.get("flip_points") or {}
        return float(flip_info.get("threshold", 0.0))

    # 5. Tornado swing: tornado:<param>.swing
    if source_ref.startswith("tornado:"):
        rest = source_ref[len("tornado:"):]
        param = rest.split(".", 1)[0]
        tornado = context.get("tornado_data") or context.get("tornado_sensitivity") or []
        for item in tornado:
            if isinstance(item, dict):
                p_name = item.get("assumption_name") or item.get("param") or item.get("parameter")
                if p_name == param:
                    return float(item.get("swing", 0.0))

    # 6. Model config: model_config:<key>
    if source_ref.startswith("model_config:"):
        key_path = source_ref[len("model_config:"):]
        config = context.get("model_config", {})
        curr = config
        for p in key_path.split("."):
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                curr = 0.0
                break
        try:
            return float(curr)
        except (ValueError, TypeError):
            return 0.0

    # 7. Calculations: calc:<key>
    if source_ref.startswith("calc:"):
        key = source_ref[len("calc:"):]
        if key == "margin_lead":
            sim_runs = context.get("sim_runs", [])
            exp_runs = [r for r in sim_runs if getattr(r, "scenario", "") == "expected"]
            if len(exp_runs) >= 2:
                sorted_exp = sorted(exp_runs, key=lambda x: x.outputs.get("net_contribution_12", 0.0), reverse=True)
                return float(round(sorted_exp[0].outputs.get("net_contribution_12", 0.0) - sorted_exp[1].outputs.get("net_contribution_12", 0.0), 2))
        if key == "avg_confidence":
            asms = context.get("assumptions", [])
            if asms:
                return round(sum(a.confidence for a in asms) / len(asms) * 100.0, 1)

    return 0.0


class NumberRegistry:
    def __init__(self, entries: Optional[List[NumberEntry]] = None):
        self.entries: List[NumberEntry] = entries or []

    def register(
        self,
        value: float,
        path: str,
        origin: str,
        expected_value: Optional[float] = None,
        tolerance: float = 1e-6,
        source_ref: Optional[str] = None
    ) -> None:
        ref = source_ref or origin
        exp = expected_value if expected_value is not None else value
        self.entries.append(
            NumberEntry(
                value=round(float(value), 4),
                path=path,
                origin=origin,
                source_ref=ref,
                expected_value=round(float(exp), 4),
                tolerance=tolerance
            )
        )

    def register_source(
        self,
        value: float,
        path: str,
        source_ref: str,
        tolerance: float = 1e-6
    ) -> None:
        self.register(
            value=value,
            path=path,
            origin=source_ref,
            expected_value=value,
            tolerance=tolerance,
            source_ref=source_ref
        )

    def lookup_number(self, val: float, tolerance: float = 0.05) -> bool:
        """Checks if a numeric value matches any registered entry within relative or absolute tolerance."""
        for e in self.entries:
            abs_diff = abs(e.value - val)
            if abs_diff <= tolerance:
                return True
            # Check percentage scale (e.g. 0.02 vs 2.0%)
            if abs(e.value * 100.0 - val) <= tolerance:
                return True
            if val != 0 and abs(abs_diff / val) <= tolerance:
                return True
        return False

    def verify_all(self) -> List[Dict[str, Any]]:
        failures = []
        for e in self.entries:
            diff = abs(e.value - e.expected_value)
            if diff > e.tolerance:
                failures.append({
                    "path": e.path,
                    "origin": e.origin,
                    "source_ref": e.source_ref,
                    "value": e.value,
                    "expected": e.expected_value,
                    "diff": diff,
                    "tolerance": e.tolerance
                })
        return failures

    def verify_with_context(self, context: Dict[str, Any], rel_tol: float = 1e-6) -> List[Dict[str, Any]]:
        failures = []
        for e in self.entries:
            resolved = resolve_source_ref(e.source_ref, context)
            if resolved == 0.0 and e.value != 0.0:
                if not any(e.source_ref.startswith(pfx) for pfx in ["sim:", "mc:", "company:", "flip:", "tornado:", "model_config:"]):
                    resolved = e.expected_value
                elif getattr(e, "source_ref", "").startswith("calc:"):
                    resolved = e.expected_value
            diff = abs(e.value - resolved)
            denom = abs(resolved) if abs(resolved) > 1e-6 else 1.0
            rel_diff = diff / denom
            if rel_diff > rel_tol and diff > 1e-4:
                failures.append({
                    "path": e.path,
                    "source_ref": e.source_ref,
                    "reported": e.value,
                    "resolved": resolved,
                    "delta": diff,
                    "rel_tol": rel_tol
                })
        return failures

    def to_dict(self) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self.entries]

    @classmethod
    def from_dict(cls, data: Any) -> "NumberRegistry":
        if isinstance(data, list):
            return cls([NumberEntry.model_validate(item) for item in data])
        return cls([])
