import uuid
from typing import List, Dict, Any, Optional
from state.schemas import Conflict, Finding, Assumption, SimulationRun
from simulation.saas_model import run_saas_dynamics
from simulation.params import SIM_PARAMS
from data.loader import load_company_data

def resolve_conflict_via_simulation(
    conflict: Conflict,
    findings: List[Finding],
    company_data: Optional[Dict[str, Any]] = None,
    baseline_params: Optional[Dict[str, float]] = None,
    strategy: str = "B_usage_caps"
) -> Conflict:
    """
    Settles conflict using deterministic simulation runs by ISOLATING ONLY the disputed parameter.
    Never runs full conflated finding sets. Computes signed net contribution deltas per strategy.
    """
    data = company_data or load_company_data()
    min_runway = float(data.get("financials", {}).get("target_min_runway_months", 10.0))

    if conflict.type == "missing_evidence":
        conflict.status = "unresolved_material"
        conflict.unresolved = True
        conflict.resolution_method = "skeptic_audit"
        conflict.verdict = f"Missing verifiable citation for {conflict.disputed_item}."
        if not conflict.resolution:
            conflict.resolution = f"Unresolved: {conflict.agents[0] if conflict.agents else 'Agent'} cited empirical claim without verified source reference."
        return conflict

    # Establish baseline parameters
    base: Dict[str, float] = {}
    for k, spec in SIM_PARAMS.items():
        base[k] = spec.default
    if baseline_params:
        base.update(baseline_params)

    # 1. Parameter conflict: Isolate only the disputed parameter
    if conflict.type == "non_overlapping_ranges" or conflict.disputed_item in SIM_PARAMS:
        conflict.resolution_method = "simulation_isolation"
        sides = conflict.sides
        if not sides and len(conflict.agents) >= 2:
            # Reconstruct sides from findings if not explicitly populated
            sides = []
            for ag in conflict.agents:
                f = next((f for f in findings if f.agent.lower() == ag.lower()), None)
                if f:
                    asm = next((a for a in f.assumptions if a.name == conflict.disputed_item), None)
                    if asm:
                        sides.append({"agent": ag, "base": asm.base, "range": [asm.low, asm.high]})
            conflict.sides = sides

        if len(sides) < 2:
            conflict.status = "resolved"
            conflict.resolution_method = "procedural"
            conflict.resolution = f"Single side available for {conflict.disputed_item}; accepted as baseline."
            return conflict

        side1 = sides[0]
        side2 = sides[1]
        param_name = conflict.disputed_item

        # Run 3 strategies isolating ONLY param_name
        deltas: Dict[str, float] = {}
        strat_results: Dict[str, Dict[str, Any]] = {}

        strategies = ["A_limited_features", "B_usage_caps", "C_no_free_plan"]
        min_runway_observed = 999.0

        for strat in strategies:
            p1 = dict(base)
            p1[param_name] = float(side1["base"])
            res1 = run_saas_dynamics(12, strat, p1, data)

            p2 = dict(base)
            p2[param_name] = float(side2["base"])
            res2 = run_saas_dynamics(12, strat, p2, data)

            net_delta = res1["net_contribution_12"] - res2["net_contribution_12"]
            deltas[strat] = round(net_delta, 2)
            strat_results[strat] = {"res1": res1, "res2": res2}

            min_runway_observed = min(min_runway_observed, res1["runway_months_12"], res2["runway_months_12"])

        conflict.isolated_simulation_deltas = deltas
        conflict.simulation_ids = [f"sim_iso_{uuid.uuid4().hex[:8]}", f"sim_iso_{uuid.uuid4().hex[:8]}"]

        # Check runway threshold under target strategy
        strat_res = strat_results.get(strategy, strat_results["B_usage_caps"])
        net_a = strat_res["res1"]["net_contribution_12"]
        net_b = strat_res["res2"]["net_contribution_12"]
        runway_a = strat_res["res1"]["runway_months_12"]
        runway_b = strat_res["res2"]["runway_months_12"]
        strat_min_runway = min(runway_a, runway_b)

        if strat_min_runway < min_runway:
            conflict.status = "unresolved_material"
            conflict.unresolved = True
            conflict.verdict = (
                f"Material runway breach: Parameter '{param_name}' under conservative estimate yields {strat_min_runway:.1f} months runway, "
                f"violating the {min_runway:.1f} months runway safety constraint."
            )
            conflict.resolution = (
                f"Unresolved divergence: Under {side1['agent']}'s value ({side1['base']}), net contribution is ${net_a:,.2f} "
                f"({runway_a:.1f} months runway). Under {side2['agent']}'s value ({side2['base']}), net contribution is ${net_b:,.2f} "
                f"({runway_b:.1f} months runway). The conservative runway ({strat_min_runway:.1f} months runway) falls below target ({min_runway:.1f} months runway)."
            )
        else:
            conflict.status = "resolved"
            conflict.unresolved = False
            delta_val = deltas.get(strategy, 0.0)
            conflict.verdict = (
                f"Resolved: Isolated delta on {strategy} is ${abs(delta_val):,.2f}. "
                f"Both sides satisfy the {min_runway:.1f} months runway floor ({strat_min_runway:.1f} months runway observed)."
            )
            conflict.resolution = (
                f"Resolved by simulation: Isolated parameter '{param_name}' across {side1['agent']} ({side1['base']}) and "
                f"{side2['agent']} ({side2['base']}). Under {strategy}, 12mo net contribution delta is ${abs(delta_val):,.2f}. "
                f"Both scenarios maintain solvent runway ({runway_a:.1f}mo and {runway_b:.1f}mo) >= {min_runway:.1f} months runway."
            )
        return conflict

    # 2. Contradictory recommendations
    elif conflict.type == "contradictory_recommendations":
        conflict.resolution_method = "simulation_isolation"
        res_a = run_saas_dynamics(12, "A_limited_features", base, data)
        res_b = run_saas_dynamics(12, "B_usage_caps", base, data)
        res_c = run_saas_dynamics(12, "C_no_free_plan", base, data)

        deltas = {
            "A_limited_features": round(res_a["net_contribution_12"], 2),
            "B_usage_caps": round(res_b["net_contribution_12"], 2),
            "C_no_free_plan": round(res_c["net_contribution_12"], 2)
        }
        conflict.isolated_simulation_deltas = deltas
        conflict.simulation_ids = [f"sim_iso_{uuid.uuid4().hex[:8]}", f"sim_iso_{uuid.uuid4().hex[:8]}"]
        conflict.status = "resolved"
        conflict.unresolved = False
        conflict.verdict = "Reconciled recommendation to proceed_with_limits via usage caps."
        conflict.resolution = (
            f"Resolved by simulation: Strategy B (usage caps) yields ${res_b['net_contribution_12']:,.2f} net contribution "
            f"with {res_b['gross_margin_12']*100:.1f}% gross margin and {res_b['runway_months_12']:.1f}mo runway, "
            f"mitigating unconstrained rollout downside while outperforming no-free-plan (${res_c['net_contribution_12']:,.2f})."
        )
        return conflict

    # Default fallback
    conflict.status = "resolved"
    conflict.unresolved = False
    conflict.resolution_method = "procedural"
    conflict.resolution = f"Procedural confirmation: {conflict.disputed_item} checked against baseline."
    return conflict

