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

    # 2. If allow_all=True (frontend interaction), validate that query is a business/strategic decision
    if allow_all:
        saas_decision_terms = [
            "plan", "tier", "free", "freemium", "pricing", "price", "charge", "cost", "fee",
            "subscription", "discount", "starter", "pro", "enterprise", "churn", "retention",
            "cancel", "customer", "support", "ticket", "mrr", "arr", "revenue", "runway",
            "cash", "burn", "margin", "growth", "funnel", "conversion", "trial", "signup",
            "visitor", "traffic", "acquisition", "cac", "ltv", "infra", "infrastructure",
            "cloud", "server", "scale", "launch", "introduce", "expand", "gating", "caps",
            "limit", "feature", "usage", "hire", "spend", "sales", "marketing", "raise",
            "increase", "cut", "lower", "reduce", "optimize", "strategy", "decision"
        ]
        is_strategic = any(term in q_lower for term in saas_decision_terms)
        
        if not is_strategic:
            return Decision(
                id=dec_id,
                type="unsupported",
                question=query,
                objective=(
                    f"Out of Domain: '{query}' is not a SaaS business strategy decision. "
                    "VentureTwin is an executive digital twin for NimbusDesk evaluating pricing, packaging, "
                    "churn reduction, infrastructure scaling, and financial runway strategies."
                ),
                constraints=effective_constraints
            )

        if any(k in q_lower for k in ["price", "pricing", "raise", "increase", "cut", "discount", "tier", "billing", "rate"]):
            obj = f"Evaluate revenue elasticity, customer churn risk, and runway implications of: {query}"
        elif any(k in q_lower for k in ["churn", "retention", "cancel", "support"]):
            obj = f"Evaluate retention dynamics, support load, and customer lifetime value for: {query}"
        elif any(k in q_lower for k in ["infra", "cloud", "server", "cost", "burn"]):
            obj = f"Evaluate cloud infrastructure unit costs, engineering capacity, and runway burn for: {query}"
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
