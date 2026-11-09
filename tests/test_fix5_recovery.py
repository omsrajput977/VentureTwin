import pytest
import time
import asyncio
from state.schemas import Decision, Task, Finding
from agents.base_agent import BaseAgent
from agents.specialists import CFOAgent, CTOAgent
from orchestrator.supervisor import Supervisor
from orchestrator.decomposer import decompose_decision

@pytest.mark.asyncio
async def test_instant_timeout_injection():
    agent = CFOAgent()
    task = Task(id="t_cfo", owner_agent="CFO", kind="agent_analysis")
    start = time.time()
    with pytest.raises(asyncio.TimeoutError):
        await agent.run(task, context={}, injected_failure="timeout")
    duration = time.time() - start
    assert duration < 0.2, f"Timeout took too long: {duration}s"

@pytest.mark.asyncio
async def test_persistent_analysis_failure_degrades_workflow():
    dec = Decision(id="d_core_degrade", question="Should we launch a free plan?", type="free_plan", objective="Test")
    supervisor = Supervisor()
    # Inject persistent failure into CFO (analysis task)
    supervisor.inject_failure("cfo", "exception", persist=True)

    state = await supervisor.execute_workflow(dec)
    assert state.status == "degraded"
    assert "CFO" in state.recovered_agents or "CFO" in state.degraded_agents
    assert state.report is not None

@pytest.mark.asyncio
async def test_supervisor_task_failure_stops_workflow():
    dec = Decision(id="d_sup_fail", question="Should we launch a free plan?", type="free_plan", objective="Test")
    supervisor = Supervisor()
    async def bad_sim(task, state):
        raise RuntimeError("Engine offline")
    supervisor._run_simulation_task = bad_sim

    state = await supervisor.execute_workflow(dec)
    assert state.status == "failed"
    assert "task_simulation_engine" in state.failed_ids
    assert state.report is None

@pytest.mark.asyncio
async def test_non_core_specialist_failure_invokes_backup_analyst():
    dec = Decision(id="d_backup", question="Should we launch a free plan?", type="free_plan", objective="Test")
    supervisor = Supervisor()
    # Inject persistent failure into CTO (non-core specialist task)
    supervisor.inject_failure("cto", "persistent_exception")

    state = await supervisor.execute_workflow(dec)
    # Workflow should complete or degrade, but NOT fail terminally
    assert state.status in ["completed", "degraded"]
    # Check that CTO task completed via Backup Analyst
    assert state.tasks["task_cto_analysis"].status == "done"
    cto_finding = next((f for f in state.findings if "CTO" in f.agent or "cto" in f.task_id), None)
    assert cto_finding is not None
    assert any("backup" in lim.lower() for lim in cto_finding.limitations) or cto_finding.agent == "BACKUP_ANALYST"

