import pytest
from state.schemas import Decision, SimulationRun, Assumption, Conflict, VerificationResult, Report
from report.number_registry import NumberRegistry, NumberEntry
from verification.verifier import (
    verify_number_registry,
    verify_prose_numbers,
    resolve_source_ref,
    run_all_verification_checks
)
from report.decision_logic import rank_strategies
from report.report_builder import build_consolidated_report
from orchestrator.decomposer import decompose_decision

def test_number_registry_resolvable_sources():
    reg = NumberRegistry()
    # Register with resolvable source strings
    reg.register_source(
        value=150000.0,
        path="sections.current_position.mrr",
        source_ref="company:financials.mrr"
    )
    reg.register_source(
        value=546485.75,
        path="sections.strategies_compared[0].net_contribution_12",
        source_ref="sim:B_usage_caps.net_contribution_12"
    )

    context = {
        "company_data": {"financials": {"mrr": 150000.0}},
        "sim_runs": [
            SimulationRun(
                id="sim_1",
                strategy="B_usage_caps",
                scenario="expected",
                outputs={"net_contribution_12": 546485.75}
            )
        ]
    }

    # Should resolve with 0 failure
    failures = reg.verify_with_context(context, rel_tol=1e-6)
    assert len(failures) == 0

    # If simulation output is tampered/different, verifier catches exact delta
    context["sim_runs"][0].outputs["net_contribution_12"] = 500000.0
    failures = reg.verify_with_context(context, rel_tol=1e-6)
    assert len(failures) == 1
    assert failures[0]["delta"] == pytest.approx(46485.75, rel=1e-3)

def test_safe_empty_ranking_when_all_infeasible():
    dec = Decision(
        id="d1",
        question="Should we launch a free plan?",
        type="free_plan",
        objective="Test",
        constraints={"min_runway_months": 24.0} # high runway floor
    )
    # Both runs have runway < 24.0
    sim_runs = [
        SimulationRun(
            id="s1",
            strategy="A_limited_features",
            scenario="expected",
            outputs={"runway_months_12": 15.0, "net_contribution_12": 100000.0, "mrr_12": 180000.0, "gross_margin_12": 0.75}
        ),
        SimulationRun(
            id="s2",
            strategy="B_usage_caps",
            scenario="expected",
            outputs={"runway_months_12": 14.0, "net_contribution_12": 120000.0, "mrr_12": 190000.0, "gross_margin_12": 0.72}
        )
    ]
    ranked = rank_strategies(sim_runs, dec.constraints)
    assert len(ranked) == 2
    assert all(not r.is_feasible for r in ranked)

    # Report builder should not crash, and must explicitly explain
    rep = build_consolidated_report(
        decision=dec,
        sim_runs=sim_runs,
        assumptions=[],
        conflicts=[],
        verification_results=[],
        tornado_data=[],
        flip_point_info={"has_flip_point": False}
    )
    assert "Do not proceed" in rep.recommendation
    assert "No strategy satisfies the minimum runway requirement of 24.0 months" in rep.sections["executive_summary"]

def test_dag_separates_draft_verification_finalize():
    dec = Decision(id="d1", question="Should we launch a free plan?", type="free_plan", objective="Test")
    dag = decompose_decision(dec)
    assert "task_report_draft" in dag.tasks
    assert "task_workflow_verification" in dag.tasks
    assert "task_report_finalize" in dag.tasks

    # Verify task ordering: draft -> verification -> finalize
    draft_task = dag.tasks["task_report_draft"]
    verif_task = dag.tasks["task_workflow_verification"]
    final_task = dag.tasks["task_report_finalize"]

    assert "task_simulation_engine" in draft_task.depends_on
    assert "task_report_draft" in verif_task.depends_on
    assert "task_workflow_verification" in final_task.depends_on

def test_strict_prose_scan_flags_unverified_numbers():
    rep = Report(
        decision_id="d1",
        recommendation="Proceed with B_usage_caps",
        confidence="High",
        sections={
            "number_registry": [
                {"value": 500000.0, "path": "test", "origin": "test", "source_ref": "test", "expected_value": 500000.0, "tolerance": 0.01}
            ],
            "executive_summary": "Net contribution is estimated at $500,000. An unexpected bonus of $999,999 was not registered."
        }
    )
    res = verify_prose_numbers(rep)
    assert res.status == "failed"
    assert "Unverified number in prose: '$999,999'" in res.detail

def test_wide_traceability_coverage():
    dec = Decision(id="d1", question="Should we launch a free plan?", type="free_plan", objective="Test")
    sim_runs = [
        SimulationRun(
            id="sim_1",
            strategy="B_usage_caps",
            scenario="expected",
            outputs={"runway_months_12": 18.0, "net_contribution_12": 546485.75, "mrr_12": 210000.0, "gross_margin_12": 0.78}
        )
    ]
    rep = build_consolidated_report(
        decision=dec,
        sim_runs=sim_runs,
        assumptions=[],
        conflicts=[],
        verification_results=[],
        tornado_data=[{"param": "monthly_free_signups", "swing": 45000.0}],
        flip_point_info={"has_flip_point": True, "threshold": 0.018}
    )
    reg_paths = [e["path"] for e in rep.sections["number_registry"]]
    # Verify coverage across sections
    assert any("current_position" in p for p in reg_paths)
    assert any("strategies_compared" in p for p in reg_paths)
    assert any("scenario_table" in p for p in reg_paths)
    assert any("tornado_sensitivity" in p for p in reg_paths)
    assert any("flip_points" in p for p in reg_paths)
    assert any("model_constants" in p for p in reg_paths)
    assert any("execution_plan" in p for p in reg_paths)

