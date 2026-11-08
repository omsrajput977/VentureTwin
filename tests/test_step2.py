import pytest
import asyncio
from state.schemas import Task, Finding, Decision
from state.shared_state import WorkflowState
from agents.registry import default_registry
from agents.specialists import CFOAgent, GrowthAgent, CTOAgent, SkepticAgent

@pytest.mark.asyncio
async def test_specialist_agents_return_valid_findings():
    task = Task(id="test_task_1", owner_agent="CFO")
    cfo = default_registry.get("cfo")
    assert cfo is not None
    finding = await cfo.run(task, context={})
    assert isinstance(finding, Finding)
    assert finding.agent == "CFO"
    assert finding.recommendation in ["proceed_with_limits", "reject"]
    assert len(finding.assumptions) > 0
    assert all(a.provenance in ["verified_data", "simulated_estimate", "external_research", "ai_assumption"] for a in finding.assumptions)

@pytest.mark.asyncio
async def test_cfo_and_growth_diverge_naturally():
    cfo = default_registry.get("cfo")
    growth = default_registry.get("growth")

    cfo_task = Task(id="task_cfo", owner_agent="CFO")
    growth_task = Task(id="task_growth", owner_agent="Growth")

    cfo_finding = await cfo.run(cfo_task, context={})
    growth_finding = await growth.run(growth_task, context={})

    # Recommendations diverge
    assert cfo_finding.recommendation != growth_finding.recommendation
    assert growth_finding.recommendation == "proceed"
    assert cfo_finding.recommendation in ["proceed_with_limits", "reject"]

    # Assumption ranges diverge
    cfo_conv = next(a for a in cfo_finding.assumptions if a.name == "free_to_paid_conversion")
    growth_conv = next(a for a in growth_finding.assumptions if a.name == "free_to_paid_conversion")
    assert growth_conv.base > cfo_conv.base
    assert growth_conv.low > cfo_conv.base or growth_conv.base >= 0.035

@pytest.mark.asyncio
async def test_skeptic_challenges_growth_assumption():
    growth = default_registry.get("growth")
    skeptic = default_registry.get("skeptic")

    growth_task = Task(id="task_growth", owner_agent="Growth")
    growth_finding = await growth.run(growth_task, context={})
    
    initial_conf = next(a for a in growth_finding.assumptions if a.name == "free_to_paid_conversion").confidence

    state = WorkflowState(decision=Decision(id="dec_test", type="free_plan", question="Test?", objective="Evaluate free plan"))
    skeptic_task = Task(id="task_skeptic", owner_agent="Skeptic")
    skeptic_finding = await skeptic.run(skeptic_task, context={"findings": [growth_finding], "state": state})

    # Growth's conversion assumption was challenged via skeptic findings and recorded in state challenges
    assert "Challenged" in skeptic_finding.claim
    assert len(state.skeptic_challenges) >= 1
    assert state.skeptic_challenges[0]["assumption"] == "free_to_paid_conversion"

def test_registry_lists_active_and_extensible():
    available = default_registry.list_available()
    assert "cfo" in available
    assert "growth" in available
    assert "cto" in available
    assert "customer" in available
    assert "skeptic" in available

    registered = default_registry.list_registered()
    assert registered["ops"]["status"] == "planned"
    assert registered["market"]["status"] == "planned"
    assert registered["risk"]["status"] == "planned"

