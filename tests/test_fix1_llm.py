import pytest
from pydantic import ValidationError
from state.schemas import Assumption, AgentFindingDraft, DraftAssumption, Finding
from agents.llm_client import LLMClient, LLMConfigurationError
from agents.specialists import CFOAgent, GrowthAgent
from state.shared_state import WorkflowState
from state.schemas import Decision, Task

def test_assumption_validator_low_base_high():
    # Valid ordering
    a = Assumption(name="free_to_paid_conversion", low=0.01, base=0.02, high=0.03, unit="rate", provenance="ai_assumption")
    assert a.low <= a.base <= a.high

    # Invalid: low > base
    with pytest.raises(ValidationError):
        Assumption(name="test", low=0.05, base=0.02, high=0.03, unit="rate", provenance="ai_assumption")

    # Invalid: base > high
    with pytest.raises(ValidationError):
        Assumption(name="test", low=0.01, base=0.05, high=0.03, unit="rate", provenance="ai_assumption")

def test_llm_client_configuration_checks():
    # Real mode without explicit model or key must raise LLMConfigurationError
    with pytest.raises(LLMConfigurationError):
        LLMClient(mode="real", provider="gemini", model=None)

    with pytest.raises(LLMConfigurationError):
        LLMClient(mode="record", provider="openai", model="gpt-4o")

@pytest.mark.asyncio
async def test_agent_calls_llm_and_stub_reflects_in_finding():
    # Custom stub client returning controlled Draft
    stub_draft = AgentFindingDraft(
        claim="Stub claim based on test",
        recommendation="proceed_with_limits",
        assumptions=[
            DraftAssumption(
                name="free_to_paid_conversion",
                low=0.011,
                base=0.019,
                high=0.028,
                unit="rate",
                basis="financials.mrr",
                rationale="Controlled stub conversion rate"
            ),
            DraftAssumption(
                name="unmodeled_noise_metric",
                low=1.0,
                base=2.0,
                high=3.0,
                unit="count",
                basis="unmodeled",
                rationale="Should be ignored"
            )
        ],
        evidence=[],
        limitations=["Testing limitation"],
        confidence=0.88
    )

    stub_client = LLMClient(mode="mock", mock_handler=lambda prompt, model: stub_draft)
    cfo = CFOAgent()
    task = Task(id="task_cfo_test", owner_agent="CFO")
    state = WorkflowState(decision=Decision(id="dec_test", type="free_plan", question="Test?", objective="Evaluate free plan"))

    finding = await cfo.run(task, context={"state": state}, llm_client=stub_client)
    assert isinstance(finding, Finding)
    assert finding.claim == "Stub claim based on test"
    
    # Check that free_to_paid_conversion was adopted from the stub
    conv_asm = next(a for a in finding.assumptions if a.name == "free_to_paid_conversion")
    assert conv_asm.base == 0.019
    assert conv_asm.low == 0.011

    # Check that unmodeled metric was captured in state.ignored_assumptions
    assert "unmodeled_noise_metric" in state.ignored_assumptions

def test_mock_handler_requires_agent_key():
    from agents.mock_handlers import default_mock_handler
    # Missing metadata or missing agent_key must raise KeyError
    with pytest.raises(KeyError):
        default_mock_handler("Prompt with no metadata", AgentFindingDraft, metadata=None)

    with pytest.raises(KeyError):
        default_mock_handler("Prompt with empty metadata", AgentFindingDraft, metadata={})

def test_mock_handler_explicit_routing_and_distinct_outputs():
    from agents.mock_handlers import default_mock_handler
    cfo_draft = default_mock_handler("dummy", AgentFindingDraft, metadata={"agent_key": "cfo"})
    growth_draft = default_mock_handler("dummy", AgentFindingDraft, metadata={"agent_key": "growth"})
    cto_draft = default_mock_handler("dummy", AgentFindingDraft, metadata={"agent_key": "cto"})
    customer_draft = default_mock_handler("dummy", AgentFindingDraft, metadata={"agent_key": "customer"})
    product_draft = default_mock_handler("dummy", AgentFindingDraft, metadata={"agent_key": "product"})

    # All must have distinct assumption sets
    cfo_names = {a.name for a in cfo_draft.assumptions}
    growth_names = {a.name for a in growth_draft.assumptions}
    cto_names = {a.name for a in cto_draft.assumptions}
    customer_names = {a.name for a in customer_draft.assumptions}
    product_names = {a.name for a in product_draft.assumptions}

    assert cfo_names == {"free_to_paid_conversion"}
    assert growth_names == {"free_to_paid_conversion", "monthly_free_signups"}
    assert cto_names == {"infra_cost_per_free_user", "usage_cap_infra_reduction"}
    assert customer_names == {"paid_to_free_cannibalization", "usage_cap_cannibalization_reduction"}
    assert product_names == {"activation_drop_from_gating", "cap_conversion_uplift"}

    # Swapping agent_key swaps output
    swap1 = default_mock_handler("dummy", AgentFindingDraft, metadata={"agent_key": "cto"})
    assert {a.name for a in swap1.assumptions} == cto_names

def test_mock_rebuttal_holds_position_defend():
    from agents.mock_handlers import default_mock_handler
    from state.schemas import Rebuttal
    rebuttal = default_mock_handler("Critique on conversion", Rebuttal, metadata={"agent_key": "growth"})
    assert rebuttal.stance == "defend"
    assert rebuttal.updated_base is None

def test_every_analysis_agent_prompt_contains_own_key():
    from agents.specialists import CFOAgent, GrowthAgent, CTOAgent, CustomerAgent, ProductAgent
    agents = [CFOAgent(), GrowthAgent(), CTOAgent(), CustomerAgent(), ProductAgent()]
    for agent in agents:
        prompt = agent.build_prompt({})
        assert f"Agent Key: {agent.agent_key}" in prompt
        assert agent.agent_key in ["cfo", "growth", "cto", "customer", "product"]


