import pytest
from data.loader import load_seeded_decisions, load_model_config
from api.app import compute_calibration_summary
from report.report_builder import build_consolidated_report
from state.schemas import Decision, SimulationRun, Assumption, Conflict

def test_dynamic_calibration_summary_no_hardcoding():
    seeded = load_seeded_decisions()
    summary = compute_calibration_summary(seeded)

    assert summary["total_evaluated_past_decisions"] == len(seeded)
    # Ensure mean_arr_error_pct is computed dynamically and matches mathematical average of absolute errors
    pct_errors = [3.16, 15.71, 10.0, 35.0]
    expected_mean = round(sum(pct_errors) / len(pct_errors), 1)
    assert summary["mean_arr_error_pct"] == expected_mean
    assert summary["most_common_drift_factor"] in [
        "annual_commitment_takeup_rate",
        "price_elasticity_of_demand",
        "enterprise_procurement_delay",
        "user_metering_friction"
    ]

def test_report_completeness_and_execution_plan():
    dec = Decision(
        id="d_rep",
        question="Should we launch a free plan?",
        type="free_plan",
        objective="Evaluate free plan",
        constraints={"min_runway_months": 10.0}
    )
    sim_run = SimulationRun(
        id="s1",
        strategy="B_usage_caps",
        scenario="expected",
        outputs={"net_contribution_12": 943667.25, "mrr_12": 233878.0, "runway_months_12": 128.0}
    )
    rep = build_consolidated_report(
        decision=dec,
        sim_runs=[sim_run],
        assumptions=[],
        conflicts=[],
        verification_results=[],
        tornado_data=[],
        flip_point_info={"has_flip_point": True, "threshold": 0.0183}
    )
    sec = rep.sections
    assert "execution_plan" in sec
    assert len(sec["execution_plan"]) >= 2
    assert "model_constants" in sec
    assert "llm_mode" in sec
    assert "number_registry" in sec

    # Execution gate references the actual runway threshold and flip point threshold
    phase1 = sec["execution_plan"][0]
    assert "10.0" in phase1["gate"] or "10" in phase1["gate"]
    assert "1.83%" in phase1["gate"] or "0.0183" in phase1["gate"]
