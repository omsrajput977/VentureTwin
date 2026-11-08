import os
from typing import Dict, Any, List, Optional
from state.schemas import (
    Report,
    Decision,
    SimulationRun,
    Assumption,
    Conflict,
    VerificationResult,
    Finding
)
from report.decision_logic import rank_strategies, compute_confidence, RankedStrategy
from report.number_registry import NumberRegistry
from data.loader import load_company_data, load_model_config

def build_consolidated_report(
    decision: Decision,
    sim_runs: List[SimulationRun],
    assumptions: List[Assumption],
    conflicts: List[Conflict],
    verification_results: List[VerificationResult],
    tornado_data: List[Dict[str, Any]],
    flip_point_info: Dict[str, Any],
    mc_summary: Optional[Dict[str, Any]] = None,
    degraded_agents: Optional[List[str]] = None,
    company_data: Optional[Dict[str, Any]] = None
) -> Report:
    data = company_data or load_company_data()
    ranked = rank_strategies(sim_runs, decision.constraints)
    conf_assessment = compute_confidence(
        ranked=ranked,
        mc_summaries=mc_summary,
        assumptions=assumptions,
        degraded_agents=degraded_agents,
        conflicts=conflicts
    )

    top_strategy = ranked[0] if ranked else None
    top_name = top_strategy.strategy if top_strategy else "None"
    top_name_pretty = top_name.replace("_", " ")

    if top_strategy and top_strategy.is_feasible:
        rec_title = f"Proceed with {top_name_pretty}"
    else:
        rec_title = "Do not proceed with any free-plan strategy under current constraints"

    reg = NumberRegistry()

    # 1. Executive Summary
    flip_thresh_str = f"{flip_point_info.get('threshold', 0.0) * 100:.2f}%" if flip_point_info.get('has_flip_point') else "N/A"
    exec_summary = (
        f"Recommendation: {rec_title} (Confidence: {conf_assessment.level}). "
        f"Under expected operating parameters, {top_name_pretty} generates an estimated ${top_strategy.net_contribution_12:,.2f} "
        f"in cumulative 12-month net contribution while preserving {top_strategy.runway_months_12:.1f} months of cash runway "
        f"(safety threshold: {decision.constraints.get('min_runway_months', 10.0):.1f} mo). "
        f"The recommendation remains viable as long as free-to-paid conversion stays above {flip_thresh_str}."
    )

    if top_strategy:
        reg.register(
            value=top_strategy.net_contribution_12,
            path="sections.executive_summary.net_contribution_12",
            origin=f"simulation_run:{top_strategy.strategy}_expected",
            expected_value=top_strategy.net_contribution_12
        )
        reg.register(
            value=top_strategy.runway_months_12,
            path="sections.executive_summary.runway_months_12",
            origin=f"simulation_run:{top_strategy.strategy}_expected",
            expected_value=top_strategy.runway_months_12
        )

    min_runway_constraint = float(decision.constraints.get('min_runway_months', 10.0))
    reg.register(
        value=min_runway_constraint,
        path="sections.executive_summary.min_runway_months",
        origin="decision.constraints.min_runway_months",
        expected_value=min_runway_constraint
    )

    if flip_point_info.get("has_flip_point"):
        thresh = float(flip_point_info.get("threshold", 0.0))
        reg.register(
            value=thresh,
            path="sections.flip_points.threshold",
            origin="calculation:flip_point",
            expected_value=thresh
        )

    # 2. Current Position
    fin = data.get("financials", {})
    cust = data.get("customers", {})
    current_position = {
        "company": data.get("company_name", "NimbusDesk"),
        "stage": data.get("stage", "Series A"),
        "mrr": fin.get("mrr", 0.0),
        "arr": fin.get("arr", 0.0),
        "cash_balance": fin.get("cash_balance", 0.0),
        "runway_months": fin.get("runway_months", 0.0),
        "paying_customers": cust.get("total_paying", 0),
        "synthetic_data_badge": True
    }

    for k, v in [
        ("mrr", fin.get("mrr", 0.0)),
        ("arr", fin.get("arr", 0.0)),
        ("cash_balance", fin.get("cash_balance", 0.0)),
        ("runway_months", fin.get("runway_months", 0.0)),
        ("paying_customers", cust.get("total_paying", 0))
    ]:
        reg.register(
            value=float(v),
            path=f"sections.current_position.{k}",
            origin=f"company_data.{k}",
            expected_value=float(v)
        )

    # 3. Strategies Compared
    strategies_compared = [r.model_dump() for r in ranked]
    for i, strat in enumerate(ranked):
        reg.register(
            value=strat.net_contribution_12,
            path=f"sections.strategies_compared[{i}].net_contribution_12",
            origin=f"simulation_run:{strat.strategy}",
            expected_value=strat.net_contribution_12
        )
        reg.register(
            value=strat.runway_months_12,
            path=f"sections.strategies_compared[{i}].runway_months_12",
            origin=f"simulation_run:{strat.strategy}",
            expected_value=strat.runway_months_12
        )

    # 4. Scenario Table
    scenario_table = []
    for i, r in enumerate(sim_runs):
        out = r.outputs
        row = {
            "strategy": r.strategy,
            "scenario": r.scenario,
            "mrr_12": out.get("mrr_12", 0.0),
            "net_contribution_12": out.get("net_contribution_12", 0.0),
            "runway_months_12": out.get("runway_months_12", 0.0),
            "gross_margin_12": out.get("gross_margin_12", 0.0),
            "support_headcount_12": out.get("support_headcount_12", 0)
        }
        scenario_table.append(row)

        reg.register(
            value=float(row["mrr_12"]),
            path=f"sections.scenario_table[{i}].mrr_12",
            origin=f"simulation_run:{r.id}",
            expected_value=float(row["mrr_12"])
        )
        reg.register(
            value=float(row["net_contribution_12"]),
            path=f"sections.scenario_table[{i}].net_contribution_12",
            origin=f"simulation_run:{r.id}",
            expected_value=float(row["net_contribution_12"])
        )
        reg.register(
            value=float(row["runway_months_12"]),
            path=f"sections.scenario_table[{i}].runway_months_12",
            origin=f"simulation_run:{r.id}",
            expected_value=float(row["runway_months_12"])
        )

    # 5. Conflicts Resolution
    conflicts_resolution = [
        {
            "id": c.id,
            "type": c.type,
            "agents": c.agents,
            "disputed_item": c.disputed_item,
            "resolution": c.resolution,
            "simulation_ids": c.simulation_ids,
            "unresolved": c.unresolved
        }
        for c in conflicts
    ]

    # 6. Assumption Ledger
    ledger = [asm.model_dump() for asm in assumptions]

    # 7. Risks & Execution Plan
    risks_and_triggers = [
        {
            "risk": "Conversion degradation below threshold",
            "trigger": f"Free-to-paid conversion dips below {flip_thresh_str}",
            "mitigation": "Immediately tighten feature gates or reduce self-serve free limits."
        },
        {
            "risk": "Runway compression below safety floor",
            "trigger": f"Runway falls below {decision.constraints.get('min_runway_months', 10.0):.1f} months",
            "mitigation": "Pause free tier new onboarding; migrate high-usage free users to paid Starter."
        }
    ]

    # Grounded execution plan phases and gates
    execution_plan = [
        {
            "phase": "Phase 1: Gated Beta Rollout (Months 1-3)",
            "gate": f"Conversion >= {flip_thresh_str} and Runway >= {min_runway_constraint:.1f} mo",
            "action": "Enable self-serve signups with strict product limits and monitor support load."
        },
        {
            "phase": "Phase 2: Full Distribution Scale (Months 4-12)",
            "gate": f"Gross margin >= 70% and Runway >= {min_runway_constraint:.1f} mo",
            "action": "Accelerate in-app upgrade triggers and expand self-serve marketing funnels."
        }
    ]

    # 8. Verification Summary
    verif_summary = [v.model_dump() for v in verification_results]

    sections = {
        "executive_summary": exec_summary,
        "confidence_assessment": conf_assessment.model_dump(),
        "current_position": current_position,
        "strategies_compared": strategies_compared,
        "scenario_table": scenario_table,
        "conflicts_resolution": conflicts_resolution,
        "tornado_sensitivity": tornado_data,
        "flip_points": flip_point_info,
        "assumption_ledger": ledger,
        "risks_and_triggers": risks_and_triggers,
        "execution_plan": execution_plan,
        "model_constants": load_model_config(),
        "llm_mode": os.getenv("LLM_MODE", "mock").lower(),
        "outcome_ranges": mc_summary.get("quantiles", {}) if mc_summary else {},
        "verification_summary": verif_summary,
        "monte_carlo": mc_summary or {},
        "number_registry": reg.to_dict()
    }

    disclaimers = [
        "Synthetic Data Notice: All financial metrics and telemetry originate from the NimbusDesk benchmark dataset.",
        "Deterministic Simulation Disclaimer: Outputs reflect mathematical modeling of specified assumptions, not guaranteed outcomes.",
        "Decision Support Only: Strategic recommendations require explicit human sign-off; VentureTwin does not execute external actions."
    ]

    return Report(
        decision_id=decision.id,
        sections=sections,
        recommendation=rec_title,
        confidence=conf_assessment.level,
        disclaimers=disclaimers
    )


def render_markdown_report(report: Report, workflow_status: str = "completed") -> str:
    """
    Renders human-readable GitHub-flavored markdown report with dynamic header status.
    """
    # Header status calculation based on verification and workflow
    verif_failed = any(v.get("status") == "failed" for v in report.sections.get("verification_summary", []))
    if verif_failed:
        header_status = "Status: Verification Failed"
    elif workflow_status == "degraded":
        header_status = "Status: Degraded (Agent Process Fallback)"
    else:
        header_status = "Status: Verified"

    sec = report.sections
    pos = sec.get("current_position", {})
    flip = sec.get("flip_points", {})

    lines = [
        f"# VentureTwin Decision Stress-Test Report",
        f"**Decision:** {report.decision_id} | **{header_status}** | **Confidence:** {report.confidence}\n",
        f"---",
        f"## 1. Executive Summary & Recommendation",
        f"{sec.get('executive_summary')}\n",
        f"## 2. Current Company Baseline ({pos.get('company', 'NimbusDesk')})",
        f"- **ARR:** ${pos.get('arr', 0):,.2f} (MRR: ${pos.get('mrr', 0):,.2f})",
        f"- **Cash Reserves:** ${pos.get('cash_balance', 0):,.2f} | **Runway:** {pos.get('runway_months', 0):.1f} months",
        f"- **Paying Customers:** {pos.get('paying_customers', 0):,}\n",
        f"## 3. Strategies Evaluated",
    ]

    for strat in sec.get("strategies_compared", []):
        feas_badge = "[FEASIBLE]" if strat.get("is_feasible") else "[INFEASIBLE]"
        lines.append(
            f"- **Rank {strat.get('rank')}: {strat.get('strategy').replace('_', ' ')}** {feas_badge}: "
            f"12mo Net Contribution: ${strat.get('net_contribution_12', 0):,.2f} | "
            f"Runway: {strat.get('runway_months_12', 0):.1f} mo. *({strat.get('feasibility_reason')})*"
        )

    lines.extend([
        f"\n## 4. Sensitivity & Flip Points",
        f"- **Flip Point:** {flip.get('statement', 'None')}",
        f"\n## 5. Verification Summary",
    ])

    for v in sec.get("verification_summary", []):
        badge = "PASSED" if v.get("status") == "passed" else "FAILED"
        lines.append(f"- `[{badge}]` **{v.get('check_name')}**: {v.get('detail')}")

    lines.extend([
        f"\n---",
        f"### Disclaimers",
    ])
    for d in report.disclaimers:
        lines.append(f"> {d}")

    return "\n".join(lines)

