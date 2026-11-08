import pytest
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from state.event_bus import EventBus
from orchestrator.checkpointer import SQLiteCheckpointer

@pytest.mark.asyncio
async def test_failure_injection_exception_retry_recovery(tmp_path):
    db_file = str(tmp_path / "fail_ex.db")
    bus = EventBus()
    supervisor = Supervisor(checkpointer=SQLiteCheckpointer(db_path=db_file), event_bus=bus)

    # Inject exception into CTO agent
    supervisor.inject_failure("cto", "exception")

    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)

    assert state.status in ["completed", "degraded"]
    events = [e.type for e in bus.get_events()]
    assert "agent_failed" in events
    assert "recovery_started" in events
    assert "recovery_done" in events

@pytest.mark.asyncio
async def test_failure_injection_timeout_recovery(tmp_path):
    db_file = str(tmp_path / "fail_to.db")
    bus = EventBus()
    supervisor = Supervisor(checkpointer=SQLiteCheckpointer(db_path=db_file), event_bus=bus)

    # Shorten agent timeout for test speed
    cto = supervisor.registry.get("cto")
    orig_to = cto.timeout_seconds
    cto.timeout_seconds = 0.05

    try:
        supervisor.inject_failure("cto", "timeout")
        decision = parse_decision_query("Should we launch a free plan?")
        state = await supervisor.execute_workflow(decision)

        assert state.status in ["completed", "degraded"]
        events = [e.type for e in bus.get_events()]
        assert "agent_failed" in events
    finally:
        cto.timeout_seconds = orig_to

@pytest.mark.asyncio
async def test_failure_injection_bad_output_recovery(tmp_path):
    db_file = str(tmp_path / "fail_bad.db")
    bus = EventBus()
    supervisor = Supervisor(checkpointer=SQLiteCheckpointer(db_path=db_file), event_bus=bus)

    supervisor.inject_failure("growth", "bad_output")
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)

    assert state.status in ["completed", "degraded"]
    events = [e.type for e in bus.get_events()]
    assert "agent_failed" in events
    assert "recovery_done" in events
