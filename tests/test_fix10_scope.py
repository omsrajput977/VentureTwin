import pytest
from orchestrator.parser import parse_decision_query, SUPPORTED_TYPES
from orchestrator.decomposer import decompose_decision
from orchestrator.dag import DAGValidationError
from state.schemas import Decision

def test_price_change_honest_scope_limitation():
    assert "free_plan" in SUPPORTED_TYPES
    assert "price_change" not in SUPPORTED_TYPES

    d = parse_decision_query("What if we raise Starter price by 15%?")
    assert d.type == "unsupported"
    assert "planned for v0.2" in d.objective.lower()

    # Attempting to decompose an unsupported or price_change decision raises DAGValidationError
    with pytest.raises(DAGValidationError) as exc:
        decompose_decision(d)
    assert "v0.2" in str(exc.value)

def test_freemium_queries_remain_supported():
    for q in [
        "Should we launch a free plan?",
        "Should we launch a free tier?",
        "What happens if we introduce freemium?",
        "Should we introduce usage caps on free tier?"
    ]:
        d = parse_decision_query(q)
        assert d.type == "free_plan"
        dag = decompose_decision(d)
        assert dag.validate() is True

def test_frontend_allow_all_supports_any_question():
    """Verifies frontend dynamic query intake accepts arbitrary strategic questions."""
    for q in [
        "What if we raise Starter price by 15%?",
        "Should we hire 5 enterprise sales reps?",
        "Can we launch an enterprise tier with custom SLAs?",
        "How do we reduce customer churn and protect runway?"
    ]:
        d = parse_decision_query(q, allow_all=True)
        assert d.type == "free_plan"
        assert d.question == q
        dag = decompose_decision(d)
        assert dag.validate() is True
