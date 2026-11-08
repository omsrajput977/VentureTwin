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
