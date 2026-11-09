"""
Deterministic mock handlers for unit testing and offline demo fallback.
Provides structured responses for specialist agents and rebuttals using explicit agent_key routing.
Note: Mock mode contains illustrative hardcoded ranges for parameters not directly present in company telemetry.
"""
from typing import Type, TypeVar, Any, Dict, Optional
from pydantic import BaseModel
from state.schemas import AgentFindingDraft, DraftAssumption, Evidence, Rebuttal
from data.loader import load_company_data

T = TypeVar("T", bound=BaseModel)

def default_mock_handler(
    prompt: str,
    response_model: Type[T],
    metadata: Optional[Dict[str, Any]] = None
) -> T:
    if metadata is None or "agent_key" not in metadata:
        raise KeyError(f"Mock mode requires 'agent_key' in metadata, received: {metadata}")

    agent_key = str(metadata["agent_key"]).lower()

    if response_model is AgentFindingDraft:
        return _generate_finding_draft(agent_key)  # type: ignore
    if response_model is Rebuttal:
        return _generate_rebuttal(agent_key, metadata)  # type: ignore

    # Fallback to model instantiation
    return response_model.model_validate({})

def _generate_rebuttal(agent_key: str, metadata: Dict[str, Any]) -> Rebuttal:
    param = metadata.get("parameter", "parameter")
    return Rebuttal(
        agent=agent_key.upper(),
        parameter=param,
        stance="defend",
        updated_base=None,
        updated_low=None,
        updated_high=None,
        rationale=f"{agent_key.upper()} defends its baseline assumption for {param} based on operating constraints."
    )

def _generate_finding_draft(agent_key: str) -> AgentFindingDraft:
    data = load_company_data()
    fin = data["financials"]
    funnel = data["funnel"]
    infra = data["infrastructure"]
    cust = data["customers"]

    if agent_key == "cfo":
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
                    basis="",
                    rationale="Conservative freemium cohort conversion rate to safeguard runway"
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

    elif agent_key == "growth":
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
                    basis="",
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

    elif agent_key == "cto":
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
                    basis="",
                    rationale="Infrastructure savings enabled by rate-limiting free tier compute"
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

    elif agent_key == "customer":
        paying = cust["total_paying"]
        starter_count = next((p["count"] for p in cust.get("plans", []) if p["name"] == "Starter"), None)
        claim_text = (
            f"The Starter tier with {starter_count} accounts requires strict feature boundaries to avoid cannibalization."
            if starter_count is not None else
            f"Total paying customer base of {paying} requires strict feature boundaries to avoid cannibalization."
        )
        return AgentFindingDraft(
            claim=claim_text,
            recommendation="proceed_with_limits",
            assumptions=[
                DraftAssumption(
                    name="paid_to_free_cannibalization",
                    low=0.04,
                    base=0.08,
                    high=0.15,
                    unit="rate",
                    basis="",
                    rationale="Estimated fraction of potential Starter prospects settling for free"
                ),
                DraftAssumption(
                    name="usage_cap_cannibalization_reduction",
                    low=0.30,
                    base=0.50,
                    high=0.70,
                    unit="rate",
                    basis="",
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

    elif agent_key == "product":
        plans = cust.get("plans", [])
        plan_names = ", ".join(p["name"] for p in plans) if plans else "existing tiers"
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
                    basis="",
                    rationale="Friction caused by usage limits on free tier"
                ),
                DraftAssumption(
                    name="cap_conversion_uplift",
                    low=0.05,
                    base=0.15,
                    high=0.25,
                    unit="rate",
                    basis="",
                    rationale="Conversion velocity increase upon reaching usage caps"
                )
            ],
            evidence=[
                Evidence(
                    source_type="company_data",
                    source_ref="customers.plans",
                    snippet=f"Monitored feature plans: {plan_names}."
                )
            ],
            limitations=["Requires clean in-app upgrade triggers."],
            confidence=0.80
        )

    raise KeyError(f"Unknown agent_key for mock draft: {agent_key}")
