import pytest
from pathlib import Path
from agents.llm_client import CASSETTES_DIR, LLMClient, LLMReplayError
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query

has_cassettes = CASSETTES_DIR.exists() and any(CASSETTES_DIR.glob("*.json"))

@pytest.mark.skipif(not has_cassettes, reason="RECORDING PENDING: run python scripts/run_real_demo.py locally with a key")
@pytest.mark.asyncio
async def test_replay_full_run():
    client = LLMClient(mode="replay", provider="gemini", model="gemini-1.5-pro")
    supervisor = Supervisor(llm_client=client)
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)
    assert state.status in ["completed", "degraded"]
    assert state.report is not None

