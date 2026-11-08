import pytest
from state.schemas import Report, Decision, VerificationResult
from report.number_registry import NumberRegistry, NumberEntry
from verification.verifier import verify_number_registry, verify_prose_numbers

def test_number_registry_verifies_all_entries():
    reg = NumberRegistry()
    reg.register(
        value=852825.70,
        path="sections.scenario_table[0].net_contribution_12",
        origin="simulation_run:sim_101",
        expected_value=852825.70,
        tolerance=0.01
    )
    reg.register(
        value=128.0,
        path="sections.strategies_compared[0].runway_months_12",
        origin="simulation_run:sim_101",
        expected_value=128.0,
        tolerance=0.1
    )
    # Valid report
    rep = Report(
        decision_id="d1",
        sections={"number_registry": reg.to_dict()},
        recommendation="Proceed with B",
        confidence="High"
    )
    res = verify_number_registry(rep)
    assert res.status == "passed"

    # Tampered number
    reg_tampered = NumberRegistry()
    reg_tampered.register(
        value=999999.00,
        path="sections.scenario_table[0].net_contribution_12",
        origin="simulation_run:sim_101",
        expected_value=852825.70,
        tolerance=0.01
    )
    rep_tampered = Report(
        decision_id="d1",
        sections={"number_registry": reg_tampered.to_dict()},
        recommendation="Proceed with B",
        confidence="High"
    )
    res_tampered = verify_number_registry(rep_tampered)
    assert res_tampered.status == "failed"

def test_prose_number_audit_catches_untraced_number():
    reg = NumberRegistry()
    reg.register(value=943667.25, path="exec", origin="sim", expected_value=943667.25)
    reg.register(value=128.0, path="exec", origin="sim", expected_value=128.0)
    reg.register(value=10.0, path="exec", origin="constraint", expected_value=10.0)

    # Clean prose with registered numbers only
    clean_report = Report(
        decision_id="d1",
        sections={
            "number_registry": reg.to_dict(),
            "executive_summary": "Under Strategy B, net contribution is $943,667.25 with 128.0 months runway (safety threshold: 10.0 mo over 12 months)."
        },
        recommendation="Proceed",
        confidence="High"
    )
    res_clean = verify_prose_numbers(clean_report)
    assert res_clean.status == "passed"

    # Rogue prose containing hallucinated number $4,500,000
    rogue_report = Report(
        decision_id="d1",
        sections={
            "number_registry": reg.to_dict(),
            "executive_summary": "Our AI predicts $4,500,000 in net profit with 128.0 months runway!"
        },
        recommendation="Proceed",
        confidence="High"
    )
    res_rogue = verify_prose_numbers(rogue_report)
    assert res_rogue.status == "failed"
    assert "4,500,000" in res_rogue.detail or "4500000" in res_rogue.detail
