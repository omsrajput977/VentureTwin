import pytest
from data.loader import load_company_data, load_benchmarks
from agents.specialists import (
    CFOAgent,
    GrowthAgent,
    CTOAgent,
    CustomerAgent,
    ProductAgent,
    SkepticAgent
)
from state.schemas import Task, Finding

@pytest.mark.asyncio
async def test_all_agent_sources_are_grounded():
    company_data = load_company_data()
    benchmark_ids = {b["id"] for b in load_benchmarks()}

    agents = [CFOAgent(), GrowthAgent(), CTOAgent(), CustomerAgent(), ProductAgent()]

    for agent in agents:
        task = Task(id=f"t_{agent.name.lower()}", owner_agent=agent.name)
        finding = await agent.run(task, context={})

        for asm in finding.assumptions:
            if asm.provenance == "verified_data":
                assert asm.source_ref is not None, f"Agent {agent.name} asm {asm.name} has no source_ref"
                parts = asm.source_ref.split(".")
                curr = company_data
                for p in parts:
                    assert p in curr, f"Invalid source_ref path '{asm.source_ref}' in agent {agent.name}"
                    curr = curr[p]

            elif asm.provenance == "external_research":
                assert asm.source_ref in benchmark_ids, f"Unknown benchmark id '{asm.source_ref}' in agent {agent.name}"

@pytest.mark.asyncio
async def test_skeptic_uses_grounded_company_threshold_not_literal():
    benchmarks = {b["id"]: b for b in load_benchmarks()}
    freemium_spec = benchmarks.get("b2b_saas_freemium_conversion", {})
    grounded_threshold = round(
        (freemium_spec.get("value_low", 0.01) + freemium_spec.get("value_high", 0.035)) / 2.0, 4
    )

    skeptic = SkepticAgent()
    cfo = CFOAgent()
    growth = GrowthAgent()

    cfo_f = await cfo.run(Task(id="t_cfo", owner_agent="CFO"), context={})
    growth_f = await growth.run(Task(id="t_growth", owner_agent="Growth"), context={})

    state_dict = {"skeptic_challenges": []}
    context = {"findings": [cfo_f, growth_f], "state": type("State", (), state_dict)()}

    skeptic_f = await skeptic.run(Task(id="t_skeptic", owner_agent="Skeptic"), context=context)

    # Skeptic challenge should reference the actual benchmark midpoint threshold
    assert len(state_dict["skeptic_challenges"]) > 0
    chal = state_dict["skeptic_challenges"][0]
    assert chal["grounded_threshold"] == grounded_threshold
    assert "b2b_saas_freemium_conversion" in chal["challenge"]
