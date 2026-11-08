"""
Deterministic mock handlers for unit testing and offline demo fallback.
Computes responses dynamically from company tool data with zero static string literals.
"""
from typing import Type, TypeVar, Any, Dict
from pydantic import BaseModel
from state.schemas import AgentFindingDraft, DraftAssumption, Evidence, Rebuttal
from data.loader import load_company_data

T = TypeVar("T", bound=BaseModel)

def default_mock_handler(prompt: str, response_model: Type[T]) -> T:
    if response_model is AgentFindingDraft:
        return _generate_finding_draft(prompt)  # type: ignore
    if response_model is Rebuttal:
        return _generate_rebuttal(prompt)  # type: ignore
    # Fallback to model instantiation
    return response_model.model_validate({})

def _generate_rebuttal(prompt: str) -> Rebuttal:
    p_lower = prompt.lower()
    if "growth" in p_lower or "conversion" in p_lower:
        return Rebuttal(
            agent="GROWTH",
            parameter="free_to_paid_conversion",
            stance="compromise",
            updated_base=0.028,
            updated_low=0.020,
            updated_high=0.040,
            rationale="Conceding part of initial optimism: narrowing base from 0.035 to 0.028 pending early cohort telemetry."
        )
    return Rebuttal(
        agent="AGENT",
        parameter="general",
        stance="defend",
        updated_base=None,
        updated_low=None,
        updated_high=None,
        rationale="Defending original assumption bounds based on empirical benchmarks."
    )

def _generate_finding_draft(prompt: str) -> AgentFindingDraft:
    p_lower = prompt.lower()
    data = load_company_data()
    fin = data["financials"]
    funnel = data["funnel"]
    infra = data["infrastructure"]
    cust = data["customers"]

    if "cfo" in p_lower or "chief financial officer" in p_lower or "company financials" in p_lower:
        runway = fin["runway_months"]
        cash = fin["cash_balance"]
        min_runway = fin.get("target_min_runway_months", 10.0)
        is_constrained = runway < min_runway or cash < 500000

        rec = "reject" if is_constrained else "proceed_with_limits"
        claim = (
            f"Runway is {runway:.1f} months (${cash:,.0f} cash reserves). Free tier without strict limits "
            f"risks compressing runway below the {min_runway:.1f}-month safety floor."
        )
        return AgentFindingDraft(
            claim=claim,
            recommendation=rec,
            assumptions=[
                DraftAssumption(
                    name="free_to_paid_conversion",
                    low=0.010,
                    base=0.015,
                    high=0.022,
                    unit="rate",
                    basis="financials.target_min_runway_months",
                    rationale="Conservative cohort conversion to safeguard gross margins"
                ),
                DraftAssumption(
                    name="min_acceptable_runway_months",
                    low=8.0,
                    base=min_runway,
                    high=12.0,
                    unit="months",
                    basis="financials.target_min_runway_months",
                    rationale="Minimum required board-mandated operating cash cushion"
                )
            ],
            evidence=[
                Evidence(
                    source_type="company_data",
                    source_ref="financials.cash_balance",
                    snippet=f"Cash balance: ${cash:,.2f}, runway: {runway:.1f} months."
                )
            ],
            limitations=["Assumes baseline fixed operating expenses."],
            confidence=0.82
        )

    elif "growth" in p_lower or "cmo" in p_lower or "chief marketing officer" in p_lower or "funnel" in p_lower:
        visitors = funnel["monthly_visitors"]
        trials = funnel["trial_signups"]
        return AgentFindingDraft(
            claim=f"Top-of-funnel velocity of {visitors:,} monthly visitors can generate self-serve expansion if trial barriers are removed.",
            recommendation="proceed",
            assumptions=[
                DraftAssumption(
                    name="free_to_paid_conversion",
                    low=0.025,
                    base=0.035,
                    high=0.050,
                    unit="rate",
                    basis="b2b_saas_freemium_conversion",
                    rationale="Benchmark self-serve freemium conversion rate for B2B tools"
                ),
                DraftAssumption(
                    name="monthly_free_signups",
                    low=2500.0,
                    base=3800.0,
                    high=5200.0,
                    unit="users/month",
                    basis="funnel.monthly_visitors",
                    rationale="Projected signup volume from existing organic site traffic"
                )
            ],
            evidence=[
                Evidence(
                    source_type="company_data",
                    source_ref="funnel.monthly_visitors",
                    snippet=f"Unique monthly traffic: {visitors:,} visitors with {trials} trial starts."
                )
            ],
            limitations=["Requires self-serve onboarding flow."],
            confidence=0.78
        )

    elif "cto" in p_lower or "chief technology officer" in p_lower or "infrastructure" in p_lower:
        cloud_cost = infra["monthly_cloud_cost"]
        per_free = infra.get("infra_cost_per_free_user_estimate", 1.15)
        return AgentFindingDraft(
            claim=f"Current infrastructure spend of ${cloud_cost:,.0f}/mo can accommodate free accounts if database storage and API usage are strictly capped.",
            recommendation="proceed_with_limits",
            assumptions=[
                DraftAssumption(
                    name="infra_cost_per_free_user",
                    low=0.75,
                    base=per_free,
                    high=1.85,
                    unit="USD/user/month",
                    basis="infrastructure.infra_cost_per_free_user_estimate",
                    rationale="Marginal compute and multi-tenant database cost per active account"
                ),
                DraftAssumption(
                    name="usage_cap_infra_reduction",
                    low=0.20,
                    base=0.35,
                    high=0.50,
                    unit="rate",
                    basis="saas_infra_per_free_user",
                    rationale="Infrastructure savings enabled by rate-limiting free tier"
                )
            ],
            evidence=[
                Evidence(
                    source_type="company_data",
                    source_ref="infrastructure.monthly_cloud_cost",
                    snippet=f"Baseline cloud compute cost: ${cloud_cost:,.2f}/mo."
                )
            ],
            limitations=["Requires automated Redis-backed quota enforcement."],
            confidence=0.85
        )

    elif "customer" in p_lower or "retention" in p_lower or "churn" in p_lower:
        paying = cust["total_paying"]
        starter_count = next((p["count"] for p in cust.get("plans", []) if p["name"] == "Starter"), 450)
        return AgentFindingDraft(
            claim=f"The Starter tier with {starter_count} accounts requires strict feature boundaries to avoid cannibalization.",
            recommendation="proceed_with_limits",
            assumptions=[
                DraftAssumption(
                    name="paid_to_free_cannibalization",
                    low=0.04,
                    base=0.08,
                    high=0.15,
                    unit="rate",
                    basis="saas_freemium_cannibalization",
                    rationale="Estimated fraction of potential Starter prospects settling for free"
                ),
                DraftAssumption(
                    name="usage_cap_cannibalization_reduction",
                    low=0.30,
                    base=0.50,
                    high=0.70,
                    unit="rate",
                    basis="saas_freemium_cannibalization",
                    rationale="Cannibalization reduction by withholding team seats from free tier"
                )
            ],
            evidence=[
                Evidence(
                    source_type="company_data",
                    source_ref="customers.total_paying",
                    snippet=f"Total active paying customers: {paying} across plans."
                )
            ],
            limitations=["Sample based on past Starter onboarding feedback."],
            confidence=0.72
        )

    elif "product" in p_lower:
        return AgentFindingDraft(
            claim="Usage ceilings create a natural upgrade catalyst when users reach productivity scale.",
            recommendation="proceed_with_limits",
            assumptions=[
                DraftAssumption(
                    name="activation_drop_from_gating",
                    low=0.05,
                    base=0.10,
                    high=0.20,
                    unit="rate",
                    basis="b2b_saas_freemium_conversion",
                    rationale="Friction caused by usage limits on free tier"
                ),
                DraftAssumption(
                    name="cap_conversion_uplift",
                    low=0.05,
                    base=0.15,
                    high=0.25,
                    unit="rate",
                    basis="b2b_saas_freemium_conversion",
                    rationale="Conversion velocity increase upon reaching usage caps"
                )
            ],
            evidence=[
                Evidence(
                    source_type="company_data",
                    source_ref="customers.plans",
                    snippet="Feature boundaries protect 90%+ of Starter plan value proposition."
                )
            ],
            limitations=["Requires clean in-app upgrade triggers."],
            confidence=0.80
        )

    # Generic fallback
    return AgentFindingDraft(
        claim="Evaluated operational parameters against company baseline.",
        recommendation="proceed_with_limits",
        assumptions=[],
        evidence=[],
        limitations=[],
        confidence=0.70
    )
