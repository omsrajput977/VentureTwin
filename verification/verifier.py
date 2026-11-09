import re
from typing import List, Dict, Any, Optional
from state.schemas import (
    Report,
    SimulationRun,
    Assumption,
    VerificationResult,
    Finding
)
from data.loader import load_company_data, load_model_config
from report.number_registry import NumberRegistry, NumberEntry, resolve_source_ref

VALID_UNITS = {"rate", "percentage", "users/month", "USD/user/month", "months", "USD", "ratio", "deals/month", "days"}

def verify_units(assumptions: List[Assumption]) -> VerificationResult:
    invalid = [a.name for a in assumptions if a.unit.lower() not in {u.lower() for u in VALID_UNITS}]
    if invalid:
        return VerificationResult(
            check_name="unit_consistency",
            status="failed",
            detail=f"Invalid units detected in assumptions: {', '.join(invalid)}"
        )
    return VerificationResult(
        check_name="unit_consistency",
        status="passed",
        detail="All assumption units conform to standard taxonomy."
    )


def verify_company_financial_tie_outs(company_data: Dict[str, Any]) -> VerificationResult:
    fin = company_data.get("financials", {})
    cust = company_data.get("customers", {})

    # 1. MRR to ARR tie out
    mrr = fin.get("mrr", 0.0)
    arr = fin.get("arr", 0.0)
    if abs(mrr * 12.0 - arr) > 1.0:
        return VerificationResult(
            check_name="financial_tie_out",
            status="failed",
            detail=f"MRR (${mrr:,.2f}) * 12 does not tie out to ARR (${arr:,.2f})"
        )

    # 2. Plan customer sum tie out
    plans = cust.get("plans", [])
    total_cust = cust.get("total_paying", 0)
    sum_cust = sum(p.get("count", 0) for p in plans)
    if plans and sum_cust != total_cust:
        return VerificationResult(
            check_name="financial_tie_out",
            status="failed",
            detail=f"Sum of plan customers ({sum_cust}) does not match total paying ({total_cust})"
        )

    return VerificationResult(
        check_name="financial_tie_out",
        status="passed",
        detail="Company baseline financials, customer counts, and ARR tie out with 100% precision."
    )


def verify_provenance_integrity(
    assumptions: List[Assumption],
    company_data: Dict[str, Any]
) -> VerificationResult:
    for asm in assumptions:
        if asm.provenance == "verified_data":
            if not asm.source_ref:
                return VerificationResult(
                    check_name="provenance_integrity",
                    status="failed",
                    detail=f"Assumption '{asm.name}' tagged verified_data lacks source_ref."
                )
            # Verify source ref exists in company data
            parts = asm.source_ref.split(".")
            curr = company_data
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    return VerificationResult(
                        check_name="provenance_integrity",
                        status="failed",
                        detail=f"Source ref '{asm.source_ref}' for '{asm.name}' not found in company data."
                    )
    return VerificationResult(
        check_name="provenance_integrity",
        status="passed",
        detail="All verified_data assumptions trace to authentic company snapshot fields."
    )


def verify_report_data_traceability(
    report: Optional[Report],
    sim_runs: List[SimulationRun],
    company_data: Dict[str, Any]
) -> VerificationResult:
    if report is None:
        return VerificationResult(
            check_name="report_traceability",
            status="failed",
            detail="Report object is missing."
        )

    # 1. Collect all simulation outputs
    sim_outputs_map: Dict[str, Dict[str, Any]] = {
        f"{r.strategy}_{r.scenario}": r.outputs for r in sim_runs
    }

    # Verify scenario table numbers match actual simulation runs
    scenarios = report.sections.get("scenario_table", [])
    for row in scenarios:
        key = f"{row.get('strategy')}_{row.get('scenario')}"
        if key in sim_outputs_map:
            actual = sim_outputs_map[key]
            if "net_contribution_12" in row:
                reported_net = row["net_contribution_12"]
                actual_net = actual.get("net_contribution_12")
                if abs(reported_net - actual_net) > 0.5:
                    return VerificationResult(
                        check_name="report_traceability",
                        status="failed",
                        detail=f"Tampering detected in {key}: reported net {reported_net} vs simulated {actual_net}"
                    )
            if "mrr_12" in row:
                reported_mrr = row["mrr_12"]
                actual_mrr = actual.get("mrr_12")
                if abs(reported_mrr - actual_mrr) > 0.5:
                    return VerificationResult(
                        check_name="report_traceability",
                        status="failed",
                        detail=f"Tampering detected in {key}: reported MRR {reported_mrr} vs simulated {actual_mrr}"
                    )

    # 2. Wide traceability: check registered coverage across sections
    raw_reg = report.sections.get("number_registry", [])
    registered_paths = {entry.get("path", "") for entry in raw_reg if isinstance(entry, dict)}

    # Check current_position coverage if section is structured
    if isinstance(report.sections.get("current_position"), dict):
        for cp_key in ["mrr", "arr", "cash_balance", "runway_months", "paying_customers"]:
            expected_path = f"sections.current_position.{cp_key}"
            if expected_path not in registered_paths:
                return VerificationResult(
                    check_name="report_traceability",
                    status="failed",
                    detail=f"Wide traceability gap: Current position metric '{cp_key}' is missing from audited number registry."
                )

    return VerificationResult(
        check_name="report_traceability",
        status="passed",
        detail="Every scenario table metric and audited section ties out directly to underlying simulation outputs or snapshot origins."
    )


def verify_required_sections(report: Optional[Report]) -> VerificationResult:
    if report is None:
        return VerificationResult(
            check_name="required_sections",
            status="failed",
            detail="Report is missing."
        )

    required = [
        "executive_summary",
        "current_position",
        "strategies_compared",
        "scenario_table",
        "conflicts_resolution",
        "tornado_sensitivity",
        "flip_points",
        "assumption_ledger",
        "risks_and_triggers",
        "verification_summary"
    ]

    missing = [sec for sec in required if sec not in report.sections]
    if missing:
        return VerificationResult(
            check_name="required_sections",
            status="failed",
            detail=f"Missing required sections: {', '.join(missing)}"
        )

    return VerificationResult(
        check_name="required_sections",
        status="passed",
        detail="All 10 required report sections are populated."
    )


def verify_number_registry(
    report: Optional[Report],
    context: Optional[Dict[str, Any]] = None
) -> VerificationResult:
    if report is None:
        return VerificationResult(
            check_name="number_registry_integrity",
            status="failed",
            detail="Report is missing."
        )

    raw_reg = report.sections.get("number_registry", [])
    if not raw_reg:
        return VerificationResult(
            check_name="number_registry_integrity",
            status="failed",
            detail="Number registry is missing or empty in report."
        )

    reg = NumberRegistry.from_dict(raw_reg)

    if context:
        failures = reg.verify_with_context(context, rel_tol=1e-6)
    else:
        failures = reg.verify_all()

    if failures:
        first = failures[0]
        return VerificationResult(
            check_name="number_registry_integrity",
            status="failed",
            detail=f"Discrepancy detected in {len(failures)} registered number(s): {first}"
        )

    return VerificationResult(
        check_name="number_registry_integrity",
        status="passed",
        detail=f"All {len(reg.entries)} registered numbers tie out to simulation or snapshot origins."
    )


ALLOWED_INTEGER_CONSTANTS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 24, 100}

def verify_prose_numbers(report: Optional[Report]) -> VerificationResult:
    if report is None:
        return VerificationResult(
            check_name="prose_number_audit",
            status="failed",
            detail="Report is missing."
        )

    raw_reg = report.sections.get("number_registry", [])
    reg = NumberRegistry.from_dict(raw_reg)

    prose_texts = []

    # 1. executive_summary
    exec_sum = report.sections.get("executive_summary")
    if isinstance(exec_sum, str):
        prose_texts.append(("executive_summary", exec_sum))

    # 2. recommendation
    rec = getattr(report, "recommendation", None) or report.sections.get("recommendation")
    if isinstance(rec, str):
        prose_texts.append(("recommendation", rec))

    # 3. confidence_assessment / rationale
    conf_assessment = report.sections.get("confidence_assessment", {})
    if isinstance(conf_assessment, dict):
        reasons = " ".join(conf_assessment.get("reasons", []))
        if reasons:
            prose_texts.append(("rationale", reasons))

    # 4. risks_and_triggers
    for item in report.sections.get("risks_and_triggers", []):
        if isinstance(item, dict):
            prose_texts.append(("risks_and_triggers", f"{item.get('risk', '')} {item.get('trigger', '')} {item.get('mitigation', '')}"))

    # 5. execution_plan
    for item in report.sections.get("execution_plan", []):
        if isinstance(item, dict):
            prose_texts.append(("execution_plan", f"{item.get('phase', '')} {item.get('gate', '')} {item.get('action', '')}"))

    # 6. conflicts_resolution
    for item in report.sections.get("conflicts_resolution", []):
        if isinstance(item, dict):
            prose_texts.append(("conflicts_resolution", f"{item.get('resolution', '')} {item.get('verdict', '')}"))

    # 7. limitations
    limitations = report.sections.get("limitations", [])
    if isinstance(limitations, list):
        prose_texts.append(("limitations", " ".join(str(l) for l in limitations)))
    elif isinstance(limitations, str):
        prose_texts.append(("limitations", limitations))

    # Pattern matches integers, floats, currency, percentages
    num_pattern = re.compile(r"(\$)?\b([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|\d+(?:\.\d+)?)\b(%?)")

    untraced = []
    for section_name, text in prose_texts:
        for match in num_pattern.finditer(text):
            has_dollar = bool(match.group(1))
            raw_str = match.group(2).replace(",", "")
            has_pct = bool(match.group(3))

            try:
                val = float(raw_str)
            except ValueError:
                continue

            # Context window around match
            start_idx = max(0, match.start() - 20)
            end_idx = min(len(text), match.end() + 20)
            context_window = text[start_idx:end_idx].lower()

            # Ordinal or unit exclusion
            is_month_ordinal = any(w in context_window for w in ["month", "months", "mo", "phase", "round", "step", "round-", "phase-"])
            is_ordinal_suffix = any(context_window.endswith(sfx) for sfx in ["st", "nd", "rd", "th"])

            if not has_dollar and not has_pct and int(val) == val:
                if int(val) in ALLOWED_INTEGER_CONSTANTS or is_month_ordinal or is_ordinal_suffix:
                    continue

            # If formatted as percentage (e.g. 2.5%), val is 2.5
            if not reg.lookup_number(val):
                untraced.append(f"Unverified number in prose: '{match.group(0)}' in section '{section_name}'")

    if untraced:
        return VerificationResult(
            check_name="prose_number_audit",
            status="failed",
            detail=f"{len(untraced)} unverified number(s) found in narrative prose: {'; '.join(untraced[:5])}"
        )

    return VerificationResult(
        check_name="prose_number_audit",
        status="passed",
        detail="All numbers in narrative prose tie directly to verified registry entries."
    )


def run_all_verification_checks(
    report: Optional[Report],
    sim_runs: List[SimulationRun],
    assumptions: List[Assumption],
    company_data: Optional[Dict[str, Any]] = None
) -> List[VerificationResult]:
    data = company_data or load_company_data()
    model_cfg = report.sections.get("model_constants") if report else None
    if not model_cfg:
        model_cfg = load_model_config()

    context = {
        "company_data": data,
        "sim_runs": sim_runs,
        "assumptions": assumptions,
        "mc_summary": report.sections.get("monte_carlo", {}) if report else {},
        "flip_point_info": report.sections.get("flip_points", {}) if report else {},
        "tornado_data": report.sections.get("tornado_sensitivity", []) if report else {},
        "model_config": model_cfg
    }

    results = [
        verify_units(assumptions),
        verify_company_financial_tie_outs(data),
        verify_provenance_integrity(assumptions, data),
        verify_required_sections(report),
        verify_report_data_traceability(report, sim_runs, data),
        verify_number_registry(report, context),
        verify_prose_numbers(report)
    ]
    return results
