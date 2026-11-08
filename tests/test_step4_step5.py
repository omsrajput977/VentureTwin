import pytest
import asyncio
import time
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query
from orchestrator.checkpointer import SQLiteCheckpointer
from state.event_bus import EventBus

@pytest.mark.asyncio
async def test_parallel_execution_and_dependencies(tmp_path):
    db_file = str(tmp_path / "test_cp.db")
    checkpointer = SQLiteCheckpointer(db_path=db_file)
    event_bus = EventBus()
    supervisor = Supervisor(checkpointer=checkpointer, event_bus=event_bus)

    decision = parse_decision_query("Should we launch a free plan?")
    
    start_time = time.time()
    state = await supervisor.execute_workflow(decision)
    elapsed = time.time() - start_time

    assert state.status in ["completed", "degraded"]
    # All tasks completed
    assert all(t.status == "done" for t in state.tasks.values())
    assert len(state.findings) >= 5

    # Check event order
    events = event_bus.get_events()
    event_types = [e.type for e in events]
    assert "task_created" in event_types
    assert "agent_started" in event_types
    assert "finding_posted" in event_types

    # First event is task_created
    assert event_types[0] == "task_created"

@pytest.mark.asyncio
async def test_checkpoint_and_resume(tmp_path):
    db_file = str(tmp_path / "resume_test.db")
    checkpointer = SQLiteCheckpointer(db_path=db_file)
    
    # 1. Run first supervisor on decision
    decision = parse_decision_query("Should we launch a free tier?")
    supervisor1 = Supervisor(checkpointer=checkpointer)
    state1 = await supervisor1.execute_workflow(decision)
    
    # Check that checkpoints exist
    completed = checkpointer.get_completed_tasks(decision.id)
    assert len(completed) == len(state1.tasks)

    # 2. Simulate resuming on a completed or partially completed run
    supervisor2 = Supervisor(checkpointer=checkpointer)
    state2 = await supervisor2.execute_workflow(decision, resume_from_checkpoint=True)
    assert state2.status == "completed"
    assert len(state2.tasks) == len(state1.tasks)

@pytest.mark.asyncio
async def test_event_bus_subscriptions():
    bus = EventBus()
    received = []

    def listener(evt):
        received.append(evt.type)

    bus.subscribe(listener)
    await bus.emit("task_created", agent="supervisor", payload={"id": "t1"})
    await bus.emit("agent_started", agent="cfo", payload={"id": "t1"})

    assert received == ["task_created", "agent_started"]

