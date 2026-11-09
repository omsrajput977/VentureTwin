import pytest
from orchestrator.parser import parse_decision_query
from state.schemas import Finding, Decision, SimulationRun, Assumption, Conflict
from report.report_builder import build_consolidated_report
from verification.verifier import run_all_verification_checks
from data.loader import load_company_data

def test_query_classification_word_boundaries():
    # Verify that 'strategy' containing 'rate' does not trigger price_increase
    d1 = parse_decision_query("Should I change my name to habibi for company strategy?", allow_all=True)
    assert d1.type == "strategic_decision"

    # Verify standard domains
    d2 = parse_decision_query("Should we raise Starter price by 20%?", allow_all=True)
    assert d2.type == "price_increase"

    d3 = parse_decision_query("Can we introduce an enterprise tier with custom SLAs?", allow_all=True)
    assert d3.type == "enterprise_tier"

    d4 = parse_decision_query("How do we reduce customer churn?", allow_all=True)
    assert d4.type == "churn_reduction"

    d5 = parse_decision_query("Should we launch a free plan?", allow_all=True)
    assert d5.type == "free_plan"

def test_decision_report_tethered_to_agent_rejection():
    data = load_company_data()
    decision = Decision(
        id="dec_habibi_1",
        type="strategic_decision",
        question="Should I change my name to habibi for company strategy?",
        objective="Evaluate proposal"
    )

    findings = [
        Finding(
            agent="CFO",
            task_id="t1",
            claim="Changing your personal name has zero correlation with cash reserves ($1,650,000) or our 13.2-month runway.",
            recommendation="reject",
            confidence=0.95
        ),
        Finding(
            agent="Growth",
            task_id="t2",
            claim="A personal name change does not accelerate acquisition beyond our current 65,000 monthly visitors.",
            recommendation="reject",
            confidence=0.95
        ),
        Finding(
            agent="CTO",
            task_id="t3",
            claim="Changing your personal name has zero technical impact on cloud infrastructure ($14,500/mo) or platform uptime.",
            recommendation="reject",
            confidence=0.95
        ),
        Finding(
            agent="Customer",
            task_id="t4",
            claim="Customer retention across our 450 paying accounts depends on software reliability, not personal naming changes.",
            recommendation="reject",
            confidence=0.95
        ),
        Finding(
            agent="Product",
            task_id="t5",
            claim="Personal founder name changes have zero bearing on product packaging or core tier gates.",
            recommendation="reject",
            confidence=0.90
        ),
    ]

    # Simulation runs for status quo and proposal
    sim_runs = [
        SimulationRun(
            id="sim_status_quo",
            strategy="C_status_quo",
            scenario="expected",
            parameters={},
            outputs={
                "mrr_12": 113000.0,
                "net_contribution_12": 520000.0,
                "runway_months_12": 14.5,
                "gross_margin_12": 0.76,
                "support_headcount_12": 2
            }
        ),
        SimulationRun(
            id="sim_adopt",
            strategy="A_adopt_proposal",
            scenario="expected",
            parameters={},
            outputs={
                "mrr_12": 110000.0,
                "net_contribution_12": 490000.0,
                "runway_months_12": 13.0,
                "gross_margin_12": 0.74,
                "support_headcount_12": 2
            }
        ),
    ]

    report = build_consolidated_report(
        decision=decision,
        sim_runs=sim_runs,
        assumptions=[],
        conflicts=[],
        verification_results=[],
        tornado_data=[],
        flip_point_info={"has_flip_point": False},
        mc_summary={"strategies": {}},
        company_data=data,
        findings=findings
    )

    # 1. Recommendation must be Reject
    assert "Reject" in report.recommendation

    # 2. Executive summary must synthesize agent claims
    exec_summary = report.sections["executive_summary"]
    assert "Reject: Do not proceed with proposal" in exec_summary
    assert "CFO:" in exec_summary or "Growth:" in exec_summary
    assert "Status Quo" in exec_summary

    # 3. Agent findings must be present in report sections
    assert "agent_findings" in report.sections
    assert len(report.sections["agent_findings"]) == 5
    assert report.sections["agent_findings"][0]["agent"] == "CFO"

    # 4. Strategy ranking places Status Quo at rank 1
    ranked = report.sections["strategies_compared"]
    assert ranked[0]["strategy"] == "C_status_quo"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["is_feasible"] is True

    # 5. All deterministic verification checks pass
    checks = run_all_verification_checks(
        report=report,
        sim_runs=sim_runs,
        assumptions=[],
        company_data=data
    )
    for c in checks:
        assert c.status == "passed", f"Verification check {c.check_name} failed: {c.detail}"
