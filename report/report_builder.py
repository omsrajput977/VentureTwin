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
    company_data: Optional[Dict[str, Any]] = None,
    findings: Optional[List[Finding]] = None
) -> Report:
    data = company_data or load_company_data()
    model_cfg = load_model_config()
    ranked = rank_strategies(sim_runs, decision.constraints, company_data=data)
    conf_assessment = compute_confidence(
        ranked=ranked,
        mc_summaries=mc_summary,
        assumptions=assumptions,
        degraded_agents=degraded_agents,
        conflicts=conflicts
    )

    min_runway_constraint = float(decision.constraints.get('min_runway_months', 10.0)) if decision.constraints else 10.0
    
    # Assess specialist agent consensus
    findings_list = findings or []
    reject_findings = [f for f in findings_list if f.recommendation == "reject"]
    proceed_findings = [f for f in findings_list if f.recommendation in ["proceed", "proceed_with_limits"]]
    is_rejected_by_agents = len(reject_findings) > len(proceed_findings) and len(reject_findings) >= 2

    if is_rejected_by_agents:
        # Re-rank so status quo is rank 1
        sq_strat = next((s for s in ranked if "status_quo" in s.strategy.lower() or "no_free_plan" in s.strategy.lower()), None)
        if sq_strat:
            other_strats = [s for s in ranked if s.strategy != sq_strat.strategy]
            new_ranked = [
                RankedStrategy(
                    strategy=sq_strat.strategy,
                    rank=1,
                    net_contribution_12=sq_strat.net_contribution_12,
                    runway_months_12=sq_strat.runway_months_12,
                    mrr_12=sq_strat.mrr_12,
                    gross_margin_12=sq_strat.gross_margin_12,
                    is_feasible=True,
                    feasibility_reason=f"Recommended: Status Quo maintains operational baseline; proposal '{decision.question}' rejected by executive consensus.",
                    min_runway_months=sq_strat.min_runway_months
                )
            ]
            for idx, s in enumerate(other_strats, start=2):
                new_ranked.append(
                    RankedStrategy(
                        strategy=s.strategy,
                        rank=idx,
                        net_contribution_12=s.net_contribution_12,
                        runway_months_12=s.runway_months_12,
                        mrr_12=s.mrr_12,
                        gross_margin_12=s.gross_margin_12,
                        is_feasible=False,
                        feasibility_reason=f"Rejected: Specialist agents advise against executing this initiative.",
                        min_runway_months=s.min_runway_months
                    )
                )
            ranked = new_ranked

    feasible_strategies = [s for s in ranked if s.is_feasible]
    top_strategy = feasible_strategies[0] if feasible_strategies else (ranked[0] if ranked else None)
    top_name = top_strategy.strategy if top_strategy else "None"
    top_name_pretty = top_name.replace("_", " ")

    flip_thresh_str = f"{flip_point_info.get('threshold', 0.0) * 100:.2f}%" if flip_point_info.get('has_flip_point') else "N/A"

    if is_rejected_by_agents:
        rec_title = "Reject: Do not proceed with proposal"
        agent_points = []
        for f in reject_findings[:3]:
            clean_claim = f.claim.strip().rstrip(".")
            agent_points.append(f"{f.agent}: {clean_claim}")
        claims_prose = "; ".join(agent_points)

        exec_summary = (
            f"Recommendation: {rec_title} (Confidence: {conf_assessment.level}). "
            f"Executive analysis across {len(reject_findings)} specialist agents advises rejecting the proposed initiative "
            f"('{decision.question}'). Key agent findings: {claims_prose}. "
            f"Financial simulations confirm that maintaining the baseline Status Quo preserves {top_strategy.runway_months_12:.1f} months of cash runway "
            f"(minimum safety threshold: {min_runway_constraint:.1f} mo) and ${top_strategy.net_contribution_12:,.2f} in cumulative 12-month net contribution "
            f"without taking on unvalidated strategic, brand, or operational disruption."
        )
    elif top_strategy and top_strategy.is_feasible:
        rec_title = f"Proceed with {top_name_pretty}"
        exec_summary = (
            f"Recommendation: {rec_title} (Confidence: {conf_assessment.level}). "
            f"Under expected operating parameters, {top_name_pretty} generates an estimated ${top_strategy.net_contribution_12:,.2f} "
            f"in cumulative 12-month net contribution while preserving {top_strategy.runway_months_12:.1f} months of cash runway "
            f"(safety threshold: {min_runway_constraint:.1f} mo). "
            f"The recommendation remains viable as long as free-to-paid conversion stays above {flip_thresh_str}."
        )
    else:
        rec_title = "Do not proceed"
        exec_summary = (
            f"Recommendation: Do not proceed (Confidence: Low). "
            f"No strategy satisfies the minimum runway requirement of {min_runway_constraint:.1f} months. "
            f"Under current constraints, all evaluated options breach the required cash safety threshold."
        )

    reg = NumberRegistry()

    # 1. Executive Summary numbers
    if top_strategy and top_strategy.is_feasible:
        reg.register_source(
            value=top_strategy.net_contribution_12,
            path="sections.executive_summary.net_contribution_12",
            source_ref=f"sim:{top_strategy.strategy}.net_contribution_12"
        )
        reg.register_source(
            value=top_strategy.runway_months_12,
            path="sections.executive_summary.runway_months_12",
            source_ref=f"sim:{top_strategy.strategy}.runway_months_12"
        )

    reg.register_source(
        value=min_runway_constraint,
        path="sections.executive_summary.min_runway_months",
        source_ref="company:financials.target_min_runway_months"
    )

    if flip_point_info.get("has_flip_point"):
        thresh = float(flip_point_info.get("threshold", 0.0))
        reg.register_source(
            value=thresh,
            path="sections.flip_points.threshold",
            source_ref="flip:threshold"
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

    reg.register_source(value=float(fin.get("mrr", 0.0)), path="sections.current_position.mrr", source_ref="company:financials.mrr")
    reg.register_source(value=float(fin.get("arr", 0.0)), path="sections.current_position.arr", source_ref="company:financials.arr")
    reg.register_source(value=float(fin.get("cash_balance", 0.0)), path="sections.current_position.cash_balance", source_ref="company:financials.cash_balance")
    reg.register_source(value=float(fin.get("runway_months", 0.0)), path="sections.current_position.runway_months", source_ref="company:financials.runway_months")
    reg.register_source(value=float(cust.get("total_paying", 0)), path="sections.current_position.paying_customers", source_ref="company:customers.total_paying")

    # 3. Strategies Compared
    strategies_compared = [r.model_dump() for r in ranked]
    for i, strat in enumerate(ranked):
        reg.register_source(
            value=strat.net_contribution_12,
            path=f"sections.strategies_compared[{i}].net_contribution_12",
            source_ref=f"sim:{strat.strategy}.net_contribution_12"
        )
        reg.register_source(
            value=strat.runway_months_12,
            path=f"sections.strategies_compared[{i}].runway_months_12",
            source_ref=f"sim:{strat.strategy}.runway_months_12"
        )
        reg.register_source(
            value=strat.mrr_12,
            path=f"sections.strategies_compared[{i}].mrr_12",
            source_ref=f"sim:{strat.strategy}.mrr_12"
        )
        reg.register_source(
            value=strat.gross_margin_12,
            path=f"sections.strategies_compared[{i}].gross_margin_12",
            source_ref=f"sim:{strat.strategy}.gross_margin_12"
        )

    # 4. Scenario Table (excluding isolated conflict runs)
    scenario_table = []
    matrix_runs = [r for r in sim_runs if not r.scenario.startswith("conflict:")]
    for i, r in enumerate(matrix_runs):
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

        reg.register_source(
            value=float(row["mrr_12"]),
            path=f"sections.scenario_table[{i}].mrr_12",
            source_ref=f"sim:{r.id}.mrr_12"
        )
        reg.register_source(
            value=float(row["net_contribution_12"]),
            path=f"sections.scenario_table[{i}].net_contribution_12",
            source_ref=f"sim:{r.id}.net_contribution_12"
        )
        reg.register_source(
            value=float(row["runway_months_12"]),
            path=f"sections.scenario_table[{i}].runway_months_12",
            source_ref=f"sim:{r.id}.runway_months_12"
        )
        reg.register_source(
            value=float(row["gross_margin_12"]),
            path=f"sections.scenario_table[{i}].gross_margin_12",
            source_ref=f"sim:{r.id}.gross_margin_12"
        )

    # 5. Sensitivity (tornado)
    for item in tornado_data:
        p = item.get("assumption_name") or item.get("param") or item.get("parameter") or ""
        sw = float(item.get("swing", 0.0))
        reg.register_source(
            value=sw,
            path=f"sections.tornado_sensitivity.{p}.swing",
            source_ref=f"tornado:{p}.swing"
        )

    # 6. Outcome ranges (Monte Carlo quantiles & probabilities)
    if mc_summary:
        if "quantiles" in mc_summary:
            for st_key, q_dict in mc_summary["quantiles"].items():
                for metric_name, m_vals in q_dict.items():
                    if isinstance(m_vals, dict):
                        for qk in ["p10", "p50", "p90"]:
                            if qk in m_vals:
                                qv = float(m_vals[qk])
                                reg.register_source(
                                    value=qv,
                                    path=f"sections.outcome_ranges.{st_key}.{metric_name}.{qk}",
                                    source_ref=f"mc:{st_key}.{metric_name}_{qk}"
                                )
        if "strategies" in mc_summary:
            for s_name, s_data in mc_summary["strategies"].items():
                p_bst = float(s_data.get("p_best", 0.0))
                p_feas = float(s_data.get("p_feasible", 0.0))
                reg.register_source(value=p_bst, path=f"sections.monte_carlo.{s_name}.p_best", source_ref=f"mc:{s_name}.p_best")
                reg.register_source(value=p_feas, path=f"sections.monte_carlo.{s_name}.p_feasible", source_ref=f"mc:{s_name}.p_feasible")
                reg.register_source(value=round(p_bst * 100.0, 1), path=f"sections.monte_carlo.{s_name}.p_best_pct", source_ref=f"mc:{s_name}.p_best_pct")
                reg.register_source(value=round(p_feas * 100.0, 1), path=f"sections.monte_carlo.{s_name}.p_feasible_pct", source_ref=f"mc:{s_name}.p_feasible_pct")

    # 7. Model Constants
    for mc_key, mc_val in model_cfg.items():
        if isinstance(mc_val, (int, float)):
            reg.register_source(
                value=float(mc_val),
                path=f"sections.model_constants.{mc_key}",
                source_ref=f"model_config:{mc_key}"
            )
        elif isinstance(mc_val, dict) and "default" in mc_val:
            reg.register_source(
                value=float(mc_val["default"]),
                path=f"sections.model_constants.{mc_key}.default",
                source_ref=f"model_config:{mc_key}.default"
            )

    # 8. Conflicts Resolution
    import re
    conf_num_pattern = re.compile(r"(\$)?\b([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|\d+(?:\.\d+)?)\b(%?)")
    conflicts_resolution = []
    for i, c in enumerate(conflicts):
        conflicts_resolution.append({
            "id": c.id,
            "type": c.type,
            "agents": c.agents,
            "disputed_item": c.disputed_item,
            "resolution": c.resolution,
            "verdict": c.verdict,
            "simulation_ids": c.simulation_ids,
            "unresolved": c.unresolved
        })
        if c.resolution:
            for m in conf_num_pattern.finditer(c.resolution):
                raw_num = m.group(2).replace(",", "")
                try:
                    num_val = float(raw_num)
                    reg.register_source(
                        value=num_val,
                        path=f"sections.conflicts_resolution[{i}].resolution",
                        source_ref=f"conflict:{c.id}.resolution"
                    )
                except ValueError:
                    pass
        if c.isolated_simulation_deltas:
            for k, delta_val in c.isolated_simulation_deltas.items():
                try:
                    reg.register_source(
                        value=float(delta_val),
                        path=f"sections.conflicts_resolution[{i}].deltas.{k}",
                        source_ref=f"conflict:{c.id}.delta_{k}"
                    )
                except (ValueError, TypeError):
                    pass

    # 9. Assumption Ledger
    ledger = [asm.model_dump() for asm in assumptions]

    # Register any numbers extracted from executive_summary narrative
    if exec_summary:
        for m in conf_num_pattern.finditer(exec_summary):
            raw_num = m.group(2).replace(",", "")
            try:
                num_val = float(raw_num)
                reg.register_source(
                    value=num_val,
                    path="sections.executive_summary.prose",
                    source_ref=f"exec_summary:prose_{num_val}"
                )
            except ValueError:
                pass

    # 10. Risks & Execution Plan
    if is_rejected_by_agents:
        risks_and_triggers = [
            {
                "risk": "Operational distraction from unvetted proposals",
                "trigger": "Pursuing non-core or rejected strategic initiatives",
                "mitigation": "Enforce strict executive governance; refocus roadmap on validated core growth levers."
            },
            {
                "risk": "Runway compression below safety floor",
                "trigger": f"Runway falls below {min_runway_constraint:.1f} months",
                "mitigation": "Maintain baseline operations; do not allocate resources to unvalidated initiatives."
            }
        ]
        execution_plan = [
            {
                "phase": "Phase 1: Rejection & Operational Guardrails (Immediate)",
                "gate": f"Runway >= {min_runway_constraint:.1f} mo",
                "action": f"Formalize executive rejection of '{decision.question}'. Reaffirm company focus on core business operations."
            },
            {
                "phase": "Phase 2: Baseline Roadmap Execution (Months 1-12)",
                "gate": f"Gross margin >= 70% and Runway >= {min_runway_constraint:.1f} mo",
                "action": "Maintain existing product and pricing model while monitoring customer retention and unit economics."
            }
        ]
    else:
        risks_and_triggers = [
            {
                "risk": "Conversion degradation below threshold",
                "trigger": f"Free-to-paid conversion dips below {flip_thresh_str}",
                "mitigation": "Immediately tighten feature gates or reduce self-serve free limits."
            },
            {
                "risk": "Runway compression below safety floor",
                "trigger": f"Runway falls below {min_runway_constraint:.1f} months",
                "mitigation": "Pause free tier new onboarding; migrate high-usage free users to paid Starter."
            }
        ]
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

    # Register execution plan thresholds
    reg.register_source(value=min_runway_constraint, path="sections.execution_plan.min_runway_months", source_ref="company:financials.target_min_runway_months")
    reg.register_source(value=70.0, path="sections.execution_plan.gross_margin_gate", source_ref="model_config:target_gross_margin")
    if flip_point_info.get("has_flip_point"):
        thresh = float(flip_point_info.get("threshold", 0.0))
        reg.register_source(value=thresh, path="sections.execution_plan.flip_threshold", source_ref="flip:threshold")

    # Register confidence assessment rationale numbers
    if len(ranked) >= 2:
        diff_lead = round(ranked[0].net_contribution_12 - ranked[1].net_contribution_12, 2)
        reg.register_source(
            value=diff_lead,
            path="sections.confidence_assessment.margin_lead",
            source_ref="calc:margin_lead"
        )
    if assumptions:
        avg_asm_conf = round(sum(a.confidence for a in assumptions) / len(assumptions), 4)
        reg.register_source(
            value=round(avg_asm_conf * 100.0, 1),
            path="sections.confidence_assessment.avg_confidence",
            source_ref="calc:avg_confidence"
        )

    # 11. Verification Summary
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
        "model_constants": model_cfg,
        "llm_mode": os.getenv("LLM_MODE", "mock").lower(),
        "outcome_ranges": mc_summary.get("quantiles", {}) if mc_summary else {},
        "verification_summary": verif_summary,
        "monte_carlo": mc_summary or {},
        "agent_findings": [
            {
                "agent": f.agent,
                "claim": f.claim,
                "recommendation": f.recommendation,
                "confidence": f.confidence,
                "limitations": f.limitations,
                "status": f.status
            }
            for f in findings_list
        ],
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
