import pytest
import asyncio
from state.schemas import Decision, Task, Finding
from orchestrator.supervisor import Supervisor
from orchestrator.decomposer import decompose_decision

def test_task_kinds_on_decomposed_tasks():
    dec = Decision(id="d_decomp", question="Should we launch a free plan?", type="free_plan", objective="Evaluate")
    dag = decompose_decision(dec)

    # All five analysis tasks must have kind='agent_analysis'
    analysis_task_ids = [
        "task_cfo_analysis",
        "task_growth_analysis",
        "task_cto_analysis",
        "task_customer_analysis",
        "task_product_analysis"
    ]
    for tid in analysis_task_ids:
        assert tid in dag.tasks
        assert dag.tasks[tid].kind == "agent_analysis"

    # Supervisor tasks must have their specific kinds
    assert dag.tasks["task_skeptic_audit"].kind == "skeptic_audit"
    assert dag.tasks["task_agent_discussion"].kind == "discussion"
    assert dag.tasks["task_conflict_resolution"].kind == "conflict_resolution"
    assert dag.tasks["task_simulation_engine"].kind == "simulation"
    assert dag.tasks["task_workflow_verification"].kind == "verification"
    assert dag.tasks["task_report_draft"].kind == "report_draft"
    assert dag.tasks["task_report_finalize"].kind == "report_finalize"

@pytest.mark.asyncio
async def test_persistent_cfo_failure_degrades_not_kills_workflow():
    dec = Decision(id="d_cfo_deg", question="Should we launch a free plan?", type="free_plan", objective="Evaluate")
    supervisor = Supervisor()
    supervisor.inject_failure("cfo", "exception", persist=True)

    state = await supervisor.execute_workflow(dec)
    # Must complete or degrade, NEVER failed
    assert state.status == "degraded"
    assert state.report is not None
    assert "CFO" in state.recovered_agents or "CFO" in state.degraded_agents

@pytest.mark.asyncio
async def test_supervisor_task_failure_fails_workflow_with_checkpoint():
    dec = Decision(id="d_sim_fail", question="Should we launch a free plan?", type="free_plan", objective="Evaluate")
    supervisor = Supervisor()

    # Hook to force simulation task to fail
    orig_sim = supervisor._run_simulation_task
    async def failing_sim(task, state):
        raise RuntimeError("Simulated compute cluster failure")
    supervisor._run_simulation_task = failing_sim

    state = await supervisor.execute_workflow(dec)
    assert state.status == "failed"
    assert "task_simulation_engine" in state.failed_ids
    assert state.report is None

@pytest.mark.parametrize("agent_key", ["cfo", "growth", "cto", "customer", "product"])
@pytest.mark.parametrize("mode", ["timeout", "exception", "bad_output"])
@pytest.mark.parametrize("persist", [False, True])
@pytest.mark.asyncio
async def test_failure_modes_and_agents_never_fail_workflow(agent_key, mode, persist):
    dec = Decision(id=f"d_{agent_key}_{mode}_{persist}", question="Should we launch a free plan?", type="free_plan", objective="Evaluate")
    supervisor = Supervisor()
    supervisor.inject_failure(agent_key, mode, persist=persist, fail_attempts=1)
    state = await supervisor.execute_workflow(dec)
    assert state.status in ["completed", "degraded"], f"Failed for {agent_key}/{mode}/{persist}: status={state.status}"
    assert state.report is not None

