import math
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from data.loader import load_model_config

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
    company_data: Dict[str, Any],
    model_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Deterministic monthly simulation model over 12-24 months.
    Accurately models the cohort conversion economics and operational costs.
    Externalized constants loaded from model_config.
    """
    if model_config is None:
        model_config = load_model_config()

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

    # Externalized model dynamics constants
    baseline_activation_rate = float(model_config.get("baseline_activation_rate", 0.35))
    free_churn = float(model_config.get("free_user_monthly_churn", 0.12))
    support_cost_per_fte = float(model_config.get("monthly_support_cost_per_fte", 7000.0))
    tickets_per_fte = float(model_config.get("tickets_per_fte_monthly", 300.0))
    paid_tickets_per_cust = float(model_config.get("paid_tickets_per_customer_monthly", 1.83))
    supp_reduction_factor = float(model_config.get("support_ticket_reduction_factor", 0.40))
    supp_reduction_floor = float(model_config.get("support_ticket_reduction_floor", 0.002))
    min_paying_floor = int(model_config.get("min_paying_customer_floor", 10))
    min_infra_floor = float(model_config.get("min_infra_cost_floor", 0.10))
    min_cann_floor = float(model_config.get("min_cannibalization_floor", 0.005))
    min_act_floor = float(model_config.get("min_activation_retention_floor", 0.05))

    # Strategy levers from calibrated parameters
    free_signups_mo = params.get("monthly_free_signups", 3800.0)
    conversion_rate = params.get("free_to_paid_conversion", 0.02)
    cannibalization_rate = params.get("paid_to_free_cannibalization", 0.08)
    cost_per_free = params.get("infra_cost_per_free_user", 1.15)
    free_ticket_rate = params.get("free_user_ticket_rate", 0.02)
    churn_rate = base_churn
    activation_rate = baseline_activation_rate
    effective_signups = free_signups_mo

    # Strategy levers from calibrated parameters and domain strategy targets
    if "20pct" in strategy or "20_percent" in strategy:
        arpu = arpu * 1.20
        churn_rate = base_churn * 1.20
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
        paid_acquisition_lift = 0.96
    elif "10pct" in strategy or "grandfather" in strategy:
        arpu = arpu * 1.10
        churn_rate = base_churn * 1.04
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
        paid_acquisition_lift = 1.02
    elif "enterprise_dedicated" in strategy or "dedicated_sla" in strategy:
        arpu = arpu * 1.30
        base_infra = base_infra + 2800.0
        paid_acquisition_lift = 1.08
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
    elif "self_serve_pro" in strategy or "hybrid_tier" in strategy:
        arpu = arpu * 1.14
        paid_acquisition_lift = 1.12
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
    elif "proactive_csm" in strategy:
        churn_rate = max(0.008, base_churn * 0.65)
        base_infra = base_infra + 400.0
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
        paid_acquisition_lift = 1.05
    elif "automated_health" in strategy:
        churn_rate = max(0.012, base_churn * 0.80)
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
        paid_acquisition_lift = 1.02
    elif "status_quo" in strategy:
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
        paid_acquisition_lift = 1.0
    elif strategy == "C_no_free_plan":
        # Strategy C: No free tier, but conversion optimization lift on existing funnel
        free_signups_mo = 0.0
        effective_signups = 0.0
        conversion_rate = 0.0
        cannibalization_rate = 0.0
        cost_per_free = 0.0
        free_ticket_rate = 0.0
        paid_acquisition_lift = params.get("paid_funnel_lift", 1.18)
    elif strategy == "B_usage_caps":
        # Strategy B trade-off:
        # Pros: lowers infra costs, lowers cannibalization, increases upgrade urgency
        # Cons: gating friction reduces top-of-funnel activation volume
        usage_cap_infra_red = params.get("usage_cap_infra_reduction", 0.35)
        usage_cap_cann_red = params.get("usage_cap_cannibalization_reduction", 0.50)
        cap_conv_uplift = params.get("cap_conversion_uplift", 0.15)
        act_drop = params.get("activation_drop_from_gating", 0.10)

        cost_per_free = max(min_infra_floor, cost_per_free * (1.0 - usage_cap_infra_red))
        cannibalization_rate = max(min_cann_floor, cannibalization_rate * (1.0 - usage_cap_cann_red))
        free_ticket_rate = max(supp_reduction_floor, free_ticket_rate * supp_reduction_factor)
        conversion_rate = conversion_rate * (1.0 + cap_conv_uplift)
        effective_signups = free_signups_mo * max(min_act_floor, 1.0 - act_drop)
        activation_rate = baseline_activation_rate * max(min_act_floor, 1.0 - act_drop)
        paid_acquisition_lift = 1.0
    else:  # Strategy A: Limited features
        paid_acquisition_lift = 1.0
        effective_signups = free_signups_mo
        activation_rate = baseline_activation_rate

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
        new_active_free = effective_signups * baseline_activation_rate
        active_free = int(active_free * (1.0 - free_churn) + new_active_free)

        # Conversions from free signups cohort
        converted_paid = effective_signups * conversion_rate
        
        # Cannibalization of baseline paid conversions
        cannibalized = effective_baseline_paid * cannibalization_rate

        # Paying churn
        churned_paying = paying * churn_rate
        new_paid = effective_baseline_paid + converted_paid - cannibalized
        paying = max(min_paying_floor, int(paying - churned_paying + new_paid))

        # 2. Financial dynamics
        mrr = paying * arpu
        incremental_infra = active_free * cost_per_free
        total_infra = base_infra + incremental_infra

        # Support load
        free_tickets = active_free * free_ticket_rate
        paid_tickets = paying * paid_tickets_per_cust
        total_tickets = paid_tickets + free_tickets
        required_fte = math.ceil(total_tickets / tickets_per_fte)
        support_cost = required_fte * support_cost_per_fte

        gross_profit = mrr - total_infra - support_cost
        gross_margin = max(0.0, min(1.0, gross_profit / max(1.0, mrr)))

        # Incremental gross contribution compared to baseline month
        baseline_gp = base_mrr - base_infra - (supp["headcount_fte"] * support_cost_per_fte)
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
        "support_headcount_12": math.ceil((m12.active_free_users * free_ticket_rate + m12.paying_customers * paid_tickets_per_cust) / tickets_per_fte),
        "infra_cost_12": m12.infra_cost,
        "paying_customers_12": m12.paying_customers,
        "free_users_12": m12.active_free_users,
        "history": [m.model_dump() for m in monthly_history]
    }
