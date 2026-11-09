import pytest
from pathlib import Path
from agents.llm_client import CASSETTES_DIR, LLMClient, LLMReplayError
from orchestrator.supervisor import Supervisor
from orchestrator.parser import parse_decision_query

def _has_replay_cassettes(model: str = "gemini-3.5-flash") -> bool:
    if not CASSETTES_DIR.exists():
        return False
    matching = [
        f for f in CASSETTES_DIR.glob("*.json")
        if f.is_file() and f'"model": "{model}"' in f.read_text(encoding="utf-8", errors="ignore")
    ]
    return len(matching) >= 8

@pytest.mark.skipif(not _has_replay_cassettes("gemini-3.5-flash"), reason="RECORDING PENDING: run python scripts/run_real_demo.py locally with a key")
@pytest.mark.asyncio
async def test_replay_full_run():
    client = LLMClient(mode="replay", provider="gemini", model="gemini-3.5-flash")
    supervisor = Supervisor(llm_client=client)
    decision = parse_decision_query("Should we launch a free plan?")
    state = await supervisor.execute_workflow(decision)
    assert state.status in ["completed", "degraded"]
    assert state.report is not None

