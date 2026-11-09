import re
import uuid
from typing import Tuple, Dict, Any
from state.schemas import Decision

SUPPORTED_TYPES = ["free_plan"]

def parse_decision_query(
    query: str,
    constraints: Dict[str, Any] = None,
    allow_all: bool = False
) -> Decision:
    """
    Parses a strategic decision query.
    If allow_all=True (used by FastAPI frontend intake), any user query is accepted
    and processed through the full multi-agent orchestration DAG.
    """
    q_lower = query.lower().strip() if query else ""
    dec_id = f"dec_{uuid.uuid4().hex[:8]}"
    effective_constraints = constraints or {"min_runway_months": 10.0}

    # Empty query check
    if not q_lower:
        return Decision(
            id=dec_id,
            type="unsupported",
            question=query or "",
            objective="Empty or invalid query provided.",
            constraints=effective_constraints
        )

    # 1. Free plan / freemium matching
    if any(k in q_lower for k in ["free plan", "free tier", "freemium", "free user", "free account"]):
        return Decision(
            id=dec_id,
            type="free_plan",
            question=query,
            objective="Evaluate financial runway, acquisition velocity, infra strain, and cannibalization of launching a free tier.",
            constraints=effective_constraints
        )

    # 2. If allow_all=True (frontend interaction), dynamically route any strategic question to the engine
    if allow_all:
        if any(k in q_lower for k in ["price", "pricing", "raise", "increase", "cut", "discount", "tier", "billing", "rate"]):
            obj = f"Evaluate revenue elasticity, customer churn risk, and runway implications of: {query}"
        else:
            obj = f"Evaluate financial runway, growth velocity, operational capacity, and unit economics for: {query}"
        return Decision(
            id=dec_id,
            type="free_plan",
            question=query,
            objective=obj,
            constraints=effective_constraints
        )

    # 3. Price change matching (Demarcated as planned for v0.2 in strict offline tests)
    if any(k in q_lower for k in ["raise price", "increase price", "cut price", "lower price", "pricing change", "price change"]):
        return Decision(
            id=dec_id,
            type="unsupported",
            question=query,
            objective="VentureTwin v0.1 MVP specializes in Freemium / Free Plan packaging decisions. Price change elasticity modeling is planned for v0.2 roadmap.",
            constraints=effective_constraints
        )

    # 4. Generic unsupported query
    return Decision(
        id=dec_id,
        type="unsupported",
        question=query,
        objective=(
            "Unsupported decision type. VentureTwin v0.1 MVP specializes in 'free_plan' freemium packaging decisions "
            "(e.g., 'Should we launch a free plan?' or 'Should we introduce usage caps on free tier?'). "
            "Price change elasticity modeling is planned for v0.2 roadmap."
        ),
        constraints=effective_constraints
    )
