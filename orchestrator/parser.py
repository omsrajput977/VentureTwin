import re
import uuid
from typing import Tuple, Dict, Any
from state.schemas import Decision

SUPPORTED_TYPES = ["free_plan"]

def parse_decision_query(query: str, constraints: Dict[str, Any] = None) -> Decision:
    q_lower = query.lower().strip()
    dec_id = f"dec_{uuid.uuid4().hex[:8]}"
    effective_constraints = constraints or {"min_runway_months": 10.0}

    # Free plan matching
    if any(k in q_lower for k in ["free plan", "free tier", "freemium", "free user", "free account"]):
        return Decision(
            id=dec_id,
            type="free_plan",
            question=query,
            objective="Evaluate financial runway, acquisition velocity, infra strain, and cannibalization of launching a free tier.",
            constraints=effective_constraints
        )

    # Price change matching (Demarcated as planned for v0.2)
    if any(k in q_lower for k in ["raise price", "increase price", "cut price", "lower price", "pricing change", "price change"]):
        return Decision(
            id=dec_id,
            type="unsupported",
            question=query,
            objective="VentureTwin v0.1 MVP specializes in Freemium / Free Plan packaging decisions. Price change elasticity modeling is planned for v0.2 roadmap.",
            constraints=effective_constraints
        )

    # Generic unsupported query
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

