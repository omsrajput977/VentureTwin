import math
from typing import Dict, Any, List
from pydantic import BaseModel

class MonthlyMetric(BaseModel):
    month: int
    paying_customers: int
    active_free_users: int
    mrr: float
    infra_cost: float
    support_cost: float
    gross_margin: float
    cash_balance: float
    runway_months: float
    net_contribution: float

def run_saas_dynamics(
    months: int,
    strategy: str,
    params: Dict[str, float],
    company_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic monthly simulation model over 12-24 months.
    Accurately models the cohort conversion economics and operational costs.
    """
    fin = company_data["financials"]
    cust = company_data["customers"]
    unit = company_data["unit_economics"]
    infra = company_data["infrastructure"]
    supp = company_data["support"]
    funnel = company_data["funnel"]

    # Baseline initialization
    paying = cust["total_paying"]
    active_free = 0
    cash = float(fin["cash_balance"])
    base_mrr = float(fin["mrr"])
    base_burn = float(fin["monthly_burn_net"])
    base_infra = float(infra["monthly_cloud_cost"])
    base_churn = float(cust["monthly_churn_rate"])

    arpu = unit.get("arpu", 168.50)
    baseline_trial_paid = float(funnel["new_paid_customers_monthly"])

    # Strategy levers
    free_signups_mo = params.get("monthly_free_signups", 3800.0)
    conversion_rate = params.get("free_to_paid_conversion", 0.022)
    cannibalization_rate = params.get("paid_to_free_cannibalization", 0.08)
    cost_per_free = params.get("infra_cost_per_free_user", 1.15)
    free_ticket_rate = params.get("free_user_ticket_rate", 0.02)
    activation_rate = 0.35  # fraction of signups who become active users
    churn_rate = base_churn

    if strategy == "C_no_free_plan":
        # Strategy C: No free tier, but conversion optimization lift on existing funnel
        free_signups_mo = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
        paid_acquisition_lift = params.get("paid_funnel_lift", 1.18)
    elif strategy == "B_usage_caps":
        # Usage caps reduce infrastructure load, limit support, and accelerate conversion
        cost_per_free = max(0.40, cost_per_free * 0.65)
        cannibalization_rate = max(0.02, cannibalization_rate * 0.40)
        free_ticket_rate = max(0.005, free_ticket_rate * 0.50)
        conversion_rate = conversion_rate * 1.15
        paid_acquisition_lift = 1.0
    else:  # Strategy A: Limited features
        paid_acquisition_lift = 1.0

    monthly_history: List[MonthlyMetric] = []
    cumulative_net_contribution = 0.0
    effective_baseline_paid = baseline_trial_paid * paid_acquisition_lift
    is_insolvent = False

    for m in range(1, months + 1):
        if is_insolvent:
            monthly_history.append(MonthlyMetric(
                month=m,
                paying_customers=0,
                active_free_users=0,
                mrr=0.0,
                infra_cost=0.0,
                support_cost=0.0,
                gross_margin=0.0,
                cash_balance=0.0,
                runway_months=0.0,
                net_contribution=round(cumulative_net_contribution, 2)
            ))
            continue

        # 1. User base dynamics
        free_churn = 0.12  # monthly active free user churn
        new_active_free = free_signups_mo * activation_rate
        active_free = int(active_free * (1.0 - free_churn) + new_active_free)

        # Conversions from free signups cohort
        converted_paid = free_signups_mo * conversion_rate
        
        # Cannibalization of baseline paid conversions
        cannibalized = effective_baseline_paid * cannibalization_rate

        # Paying churn
        churned_paying = paying * churn_rate
        new_paid = effective_baseline_paid + converted_paid - cannibalized
        paying = max(10, int(paying - churned_paying + new_paid))

        # 2. Financial dynamics
        mrr = paying * arpu
        incremental_infra = active_free * cost_per_free
        total_infra = base_infra + incremental_infra

        # Support load
        free_tickets = active_free * free_ticket_rate
        paid_tickets = paying * (supp["monthly_tickets"] / max(1, cust["total_paying"]))
        total_tickets = paid_tickets + free_tickets
        required_fte = math.ceil(total_tickets / 300.0)
        support_cost = required_fte * 7000.0

        gross_profit = mrr - total_infra - support_cost
        gross_margin = max(0.0, min(1.0, gross_profit / max(1.0, mrr)))

        # Incremental gross contribution compared to baseline month
        baseline_gp = base_mrr - base_infra - (supp["headcount_fte"] * 7000.0)
        diff_gp = gross_profit - baseline_gp
        cumulative_net_contribution += diff_gp

        # Cash & Runway
        burn = base_burn - diff_gp
        cash = cash - burn
        if cash <= 0:
            cash = 0.0
            runway = 0.0
            is_insolvent = True
        elif burn <= 0:
            runway = 999.0  # Cash-flow positive / self-sustaining
        else:
            runway = round(cash / burn, 1)

        monthly_history.append(MonthlyMetric(
            month=m,
            paying_customers=paying,
            active_free_users=active_free,
            mrr=round(mrr, 2),
            infra_cost=round(total_infra, 2),
            support_cost=round(support_cost, 2),
            gross_margin=round(gross_margin, 4),
            cash_balance=round(cash, 2),
            runway_months=round(runway, 1),
            net_contribution=round(cumulative_net_contribution, 2)
        ))

    m6 = monthly_history[5] if len(monthly_history) >= 6 else monthly_history[-1]
    m12 = monthly_history[11] if len(monthly_history) >= 12 else monthly_history[-1]
    m24 = monthly_history[23] if len(monthly_history) >= 24 else monthly_history[-1]

    return {
        "strategy": strategy,
        "mrr_6": m6.mrr,
        "mrr_12": m12.mrr,
        "mrr_24": m24.mrr,
        "net_contribution_6": m6.net_contribution,
        "net_contribution_12": m12.net_contribution,
        "net_contribution_24": m24.net_contribution,
        "runway_months_12": m12.runway_months,
        "gross_margin_12": m12.gross_margin,
        "support_headcount_12": math.ceil((m12.active_free_users * free_ticket_rate + m12.paying_customers * 1.83) / 300.0),
        "infra_cost_12": m12.infra_cost,
        "paying_customers_12": m12.paying_customers,
        "free_users_12": m12.active_free_users,
        "history": [m.model_dump() for m in monthly_history]
    }
