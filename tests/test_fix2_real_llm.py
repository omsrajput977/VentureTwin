import pytest
from pydantic import ValidationError
from state.schemas import Finding, AgentFindingDraft, DraftAssumption
from agents.specialists import CFOAgent, BaseAnalysisAgent
from agents.llm_client import clean_prompt_for_cache, LLMClient

def test_recommendation_must_be_constrained_literal():
    # Valid recommendations
    for valid_rec in ["proceed", "proceed_with_limits", "needs_more_info", "reject"]:
        draft = AgentFindingDraft(
            claim="Valid claim",
            recommendation=valid_rec,
            assumptions=[],
            evidence=[],
            confidence=0.8
        )
        assert draft.recommendation == valid_rec

    # Invalid recommendation raises ValidationError
    with pytest.raises(ValidationError):
        AgentFindingDraft(
            claim="Invalid claim",
            recommendation="strongly_support",  # Invented/invalid string
            assumptions=[],
            evidence=[],
            confidence=0.8
        )

def test_prompt_builder_contains_schema_params_and_bases():
    cfo = CFOAgent()
    prompt = cfo.build_prompt({"cash": 1000000})

    # Must contain SIM_PARAMS definitions
    assert "free_to_paid_conversion" in prompt
    assert "lower_bound" in prompt or "bounds" in prompt
    assert "favorable_direction" in prompt or "direction" in prompt

    # Must contain valid basis rule
    assert "basis" in prompt
    assert "b2b_saas_freemium_conversion" in prompt

    # Must contain allowed recommendation literals
    for rec in ["proceed", "proceed_with_limits", "needs_more_info", "reject"]:
        assert rec in prompt

    # Must contain inlined schema for AgentFindingDraft
    assert "AgentFindingDraft" in prompt or "properties" in prompt

def test_prompt_stability_clean_prompt_for_cache():
    p1 = "Decision dec_12345678 on task_cfo_abcdef at 2026-11-09T12:34:56.789Z"
    p2 = "Decision dec_87654321 on task_cfo_fedcba at 2026-11-09T18:22:11.000Z"

    c1 = clean_prompt_for_cache(p1)
    c2 = clean_prompt_for_cache(p2)
    assert c1 == c2
