import pytest
from state.schemas import Report, SimulationRun, Assumption
from verification.verifier import (
    verify_units,
    verify_company_financial_tie_outs,
    verify_provenance_integrity,
    verify_report_data_traceability,
    verify_required_sections,
    run_all_verification_checks
)
from data.loader import load_company_data

@pytest.fixture
def sample_valid_setup():
    data = load_company_data()
    sim_run = SimulationRun(
        id="sim_b_exp_1",
        strategy="B_usage_caps",
        scenario="expected",
        outputs={"net_contribution_12": 1009694.58, "mrr_12": 233878.0}
    )
    assumptions = [
        Assumption(
            name="min_runway",
            low=8, base=10, high=12,
            unit="months",
            provenance="verified_data",
            source_ref="financials.target_min_runway_months"
        )
    ]
    report = Report(
        decision_id="dec_test",
        recommendation="Proceed with Strategy B",
        confidence="High",
        sections={
            "executive_summary": "Summary...",
            "current_position": "Position...",
            "strategies_compared": "Strategies...",
            "scenario_table": [{
                "strategy": "B_usage_caps",
                "scenario": "expected",
                "net_contribution_12": 1009694.58,
                "mrr_12": 233878.0
            }],
            "conflicts_resolution": "Conflicts...",
            "tornado_sensitivity": [],
            "flip_points": {},
            "assumption_ledger": [],
            "risks_and_triggers": [],
            "verification_summary": []
        }
    )
    return report, [sim_run], assumptions, data

def test_verification_passes_when_untampered(sample_valid_setup):
    report, sim_runs, assumptions, data = sample_valid_setup
    results = run_all_verification_checks(report, sim_runs, assumptions, data)
    assert all(r.status == "passed" for r in results)

def test_verification_catches_tampered_number(sample_valid_setup):
    report, sim_runs, assumptions, data = sample_valid_setup
    # Tamper with the reported net contribution
    report.sections["scenario_table"][0]["net_contribution_12"] = 99999999.0
    res = verify_report_data_traceability(report, sim_runs, data)
    assert res.status == "failed"
    assert "Tampering detected" in res.detail

def test_missing_report_fails_verification(sample_valid_setup):
    _, sim_runs, assumptions, data = sample_valid_setup
    res = verify_report_data_traceability(None, sim_runs, data)
    assert res.status == "failed"

def test_missing_required_section(sample_valid_setup):
    report, _, _, _ = sample_valid_setup
    del report.sections["executive_summary"]
    res = verify_required_sections(report)
    assert res.status == "failed"
    assert "executive_summary" in res.detail
