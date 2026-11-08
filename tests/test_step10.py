import pytest
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from report.report_builder import render_markdown_report

@pytest.mark.asyncio
async def test_full_workflow_and_report_generation(tmp_path):
    supervisor = Supervisor()
    decision = parse_decision_query("Should we launch a free plan?")
    
    state = await supervisor.execute_workflow(decision)

    assert state.status in ["completed", "degraded"]
    assert state.report is not None
    report = state.report

    # Check 10 sections present
    sections = report.sections
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
    for sec in required:
        assert sec in sections, f"Section {sec} missing from report"

    # Check recommendation is data-driven
    assert "Proceed with" in report.recommendation
    assert report.confidence in ["Low", "Medium", "High"]

    # Check Markdown rendering
    md = render_markdown_report(report, workflow_status=state.status)
    assert "# VentureTwin Decision Stress-Test Report" in md
    assert "Status: Verified" in md or "Status: Degraded" in md
    assert "Executive Summary & Recommendation" in md
    assert "Current Company Baseline" in md

    # Check verification checks in report
    verifs = sections["verification_summary"]
    assert len(verifs) >= 4
    assert any(v["check_name"] == "report_traceability" for v in verifs)

