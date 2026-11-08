import re
import uuid
from typing import Tuple, Dict, Any
from state.schemas import Decision

SUPPORTED_TYPES = ["free_plan", "price_change"]

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

    # Price change matching (Stretch support)
    if any(k in q_lower for k in ["raise price", "increase price", "cut price", "lower price", "pricing change", "price change"]):
        return Decision(
            id=dec_id,
            type="price_change",
            question=query,
            objective="Evaluate elasticity of demand, expansion MRR, and churn impact of adjusting tier prices.",
            constraints=effective_constraints
        )

    # Unsupported query
    return Decision(
        id=dec_id,
        type="unsupported",
        question=query,
        objective=(
            "Unsupported decision type. VentureTwin currently supports:\n"
            "1. 'free_plan' (e.g., 'Should we launch a free plan?')\n"
            "2. 'price_change' (e.g., 'What if we raise prices by 15%?')\n"
            "Please select or enter a pricing or packaging question."
        ),
        constraints=effective_constraints
    )
