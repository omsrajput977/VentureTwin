from typing import Dict, Any, Literal
from pydantic import BaseModel

class SimParamSpec(BaseModel):
    name: str
    unit: str
    lower_bound: float
    upper_bound: float
    default: float
    favorable_direction: Literal["higher", "lower"]
    description: str

SIM_PARAMS: Dict[str, SimParamSpec] = {
    "free_to_paid_conversion": SimParamSpec(
        name="free_to_paid_conversion",
        unit="rate",
        lower_bound=0.001,
        upper_bound=0.10,
        default=0.02,
        favorable_direction="higher",
        description="Monthly cohort conversion rate from active free users to paying tier."
    ),
    "monthly_free_signups": SimParamSpec(
        name="monthly_free_signups",
        unit="users/month",
        lower_bound=500.0,
        upper_bound=20000.0,
        default=3800.0,
        favorable_direction="higher",
        description="New organic top-of-funnel free accounts registered per month."
    ),
    "infra_cost_per_free_user": SimParamSpec(
        name="infra_cost_per_free_user",
        unit="USD/user/month",
        lower_bound=0.10,
        upper_bound=5.00,
        default=1.15,
        favorable_direction="lower",
        description="Incremental monthly compute, storage, and networking cost per active free account."
    ),
    "paid_to_free_cannibalization": SimParamSpec(
        name="paid_to_free_cannibalization",
        unit="rate",
        lower_bound=0.01,
        upper_bound=0.30,
        default=0.08,
        favorable_direction="lower",
        description="Fraction of new prospective paid customers who settle for the free tier instead."
    ),
    "free_user_ticket_rate": SimParamSpec(
        name="free_user_ticket_rate",
        unit="ratio",
        lower_bound=0.001,
        upper_bound=0.15,
        default=0.02,
        favorable_direction="lower",
        description="Monthly support tickets generated per active free user."
    ),
    "paid_funnel_lift": SimParamSpec(
        name="paid_funnel_lift",
        unit="ratio",
        lower_bound=1.0,
        upper_bound=1.50,
        default=1.18,
        favorable_direction="higher",
        description="Acquisition conversion multiplier for Strategy C from paid funnel investments."
    ),
    "usage_cap_infra_reduction": SimParamSpec(
        name="usage_cap_infra_reduction",
        unit="rate",
        lower_bound=0.10,
        upper_bound=0.60,
        default=0.35,
        favorable_direction="higher",
        description="Fractional cloud infrastructure cost reduction under usage caps (Strategy B)."
    ),
    "usage_cap_cannibalization_reduction": SimParamSpec(
        name="usage_cap_cannibalization_reduction",
        unit="rate",
        lower_bound=0.10,
        upper_bound=0.80,
        default=0.50,
        favorable_direction="higher",
        description="Fractional cannibalization reduction achieved by gating Starter features."
    ),
    "activation_drop_from_gating": SimParamSpec(
        name="activation_drop_from_gating",
        unit="rate",
        lower_bound=0.02,
        upper_bound=0.30,
        default=0.10,
        favorable_direction="lower",
        description="Reduction in free user activation caused by usage friction or feature gating."
    ),
    "cap_conversion_uplift": SimParamSpec(
        name="cap_conversion_uplift",
        unit="rate",
        lower_bound=0.01,
        upper_bound=0.35,
        default=0.15,
        favorable_direction="higher",
        description="Increase in free-to-paid conversion urgency when users hit usage ceilings."
    )
}

