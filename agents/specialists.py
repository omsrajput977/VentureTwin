from typing import Dict, Any, Optional, List
from agents.base_agent import BaseAgent
from agents.llm_client import LLMClient, llm_call
from state.schemas import Finding, Task, Assumption, Evidence
from agents.tools import (
    lookup_financials,
    lookup_funnel,
    lookup_customers,
    lookup_infra_costs,
    lookup_support_metrics
)

class CFOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CFO",
            role="Chief Financial Officer",
            objective="Protect runway and gross margins; prevent unmonetized cost explosions",
            system_prompt=(
                "You are the CFO. Your duty is to protect company runway and margins. "
                "Evaluate the proposed decision against cash reserves and burn rate constraints."
            ),
            tools={"lookup_financials": lookup_financials}
        )

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        fin = await self.execute_tool("lookup_financials")
        runway = fin["runway_months"]
        cash = fin["cash_balance"]
        min_runway = fin.get("target_min_runway_months", 10.0)

        # Dynamic calculation based on cash constraint
        is_constrained = runway < min_runway or cash < 500000
        rec = "reject" if is_constrained else "proceed_with_limits"
        claim = (
            f"Runway is {runway:.1f} months ($1.65M cash). Free plan without strict usage caps "
            f"risks compressing runway below the {min_runway:.1f}-month safety threshold."
        ) if not is_constrained else (
            f"Severe runway hazard ({runway:.1f} months). Free plan cannot be financed under current cash reserves."
        )

        assumptions = [
            Assumption(
                name="free_to_paid_conversion",
                low=0.010,
                base=0.015,
                high=0.022,
                unit="rate",
                provenance="simulated_estimate",
                confidence=0.70,
                proposed_by=self.name,
                source_ref="cfo_cohort_analysis"
            ),
            Assumption(
                name="min_acceptable_runway_months",
                low=8.0,
                base=min_runway,
                high=12.0,
                unit="months",
                provenance="verified_data",
                confidence=0.95,
                proposed_by=self.name,
                source_ref="financials.target_min_runway_months"
            )
        ]

        evidence = [
            Evidence(
                source_type="company_data",
                source_ref="financials.cash_balance",
                snippet=f"Cash balance: ${cash:,.2f}, Net monthly burn: ${fin['monthly_burn_net']:,.2f}, Runway: {runway:.1f} months."
            )
        ]

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=claim,
            recommendation=rec,
            assumptions=assumptions,
            evidence=evidence,
            confidence=0.82,
            limitations=["Assumes fixed baseline opex without secondary headcount expansion."],
            status="ok"
        )


class GrowthAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Growth",
            role="Chief Marketing Officer & VP Growth",
            objective="Maximize top-of-funnel acquisition, organic user growth, and conversion volume",
            system_prompt=(
                "You are the VP of Growth. Your duty is to scale customer acquisition, reduce trial friction, "
                "and build self-serve viral flywheels."
            ),
            tools={"lookup_funnel": lookup_funnel}
        )

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        funnel = await self.execute_tool("lookup_funnel")
        visitors = funnel["monthly_visitors"]

        assumptions = [
            Assumption(
                name="free_to_paid_conversion",
                low=0.025,
                base=0.035,
                high=0.050,
                unit="rate",
                provenance="external_research",
                confidence=0.65,
                proposed_by=self.name,
                source_ref="funnel_benchmark_survey"
            ),
            Assumption(
                name="monthly_free_signups",
                low=2500.0,
                base=3800.0,
                high=5200.0,
                unit="users/month",
                provenance="simulated_estimate",
                confidence=0.70,
                proposed_by=self.name,
                source_ref="funnel_top_estimate"
            )
        ]

        evidence = [
            Evidence(
                source_type="company_data",
                source_ref="funnel.monthly_visitors",
                snippet=f"Site receives {visitors:,} unique visitors/month with only {funnel['trial_signups']} trial starts."
            )
        ]

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim="A friction-free entry tier will unlock top-of-funnel velocity, generating 3,800+ signups/mo.",
            recommendation="proceed",
            assumptions=assumptions,
            evidence=evidence,
            confidence=0.78,
            limitations=["Dependent on product onboarding self-serve experience."],
            status="ok"
        )


class CTOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CTO",
            role="Chief Technology Officer",
            objective="Ensure platform scalability, uptime SLAs, and contain cloud compute/database costs",
            system_prompt=(
                "You are the CTO. Evaluate infrastructure load, serverless compute limits, "
                "and marginal infrastructure costs per active free user."
            ),
            tools={"lookup_infra_costs": lookup_infra_costs}
        )

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        infra = await self.execute_tool("lookup_infra_costs")
        per_free_cost = infra.get("infra_cost_per_free_user_estimate", 1.15)

        assumptions = [
            Assumption(
                name="infra_cost_per_free_user",
                low=0.75,
                base=per_free_cost,
                high=1.85,
                unit="USD/user/month",
                provenance="verified_data",
                confidence=0.88,
                proposed_by=self.name,
                source_ref="infrastructure.infra_cost_per_free_user_estimate"
            )
        ]

        evidence = [
            Evidence(
                source_type="company_data",
                source_ref="infrastructure.monthly_cloud_cost",
                snippet=f"Baseline cloud spend is ${infra['monthly_cloud_cost']:,}/mo; estimated free-user cost is ${per_free_cost:.2f}/user/mo."
            )
        ]

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim="Infrastructure can absorb up to 5,000 free users if rate limits and database storage quotas are strictly capped.",
            recommendation="proceed_with_limits",
            assumptions=assumptions,
            evidence=evidence,
            confidence=0.85,
            limitations=["Requires engineering to implement Redis-based quota enforcers."],
            status="ok"
        )


class CustomerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Customer",
            role="VP Customer Success & Retention",
            objective="Protect existing customer base from churn, minimize cannibalization of paid plans",
            system_prompt=(
                "You are the VP of Customer Success. Ensure existing paying accounts do not downgrade "
                "and support queues remain responsive."
            ),
            tools={"lookup_customers": lookup_customers, "lookup_support": lookup_support_metrics}
        )

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        customers = await self.execute_tool("lookup_customers")
        total_paying = customers["total_paying"]

        assumptions = [
            Assumption(
                name="paid_to_free_cannibalization",
                low=0.04,
                base=0.08,
                high=0.15,
                unit="rate",
                provenance="ai_assumption",
                confidence=0.60,
                proposed_by=self.name,
                source_ref="starter_tier_feature_overlap"
            )
        ]

        evidence = [
            Evidence(
                source_type="company_data",
                source_ref="customers.total_paying",
                snippet=f"Currently {total_paying} active paying subscribers, with 450 on Starter ($79/mo)."
            )
        ]

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim="Starter plan ($79/mo) faces cannibalization risk of 8-15% if the free tier includes exports or integrations.",
            recommendation="proceed_with_limits",
            assumptions=assumptions,
            evidence=evidence,
            confidence=0.72,
            limitations=["Survey sample on Starter users is limited to last quarter."],
            status="ok"
        )


class ProductAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Product",
            role="VP Product",
            objective="Define product packaging, feature gates, and self-serve upgrade milestones",
            system_prompt="You are the VP of Product. Design gating boundaries between Free, Starter, and Pro plans."
        )

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        return Finding(
            agent=self.name,
            task_id=task.id,
            claim="Strategy B (Usage Caps) creates the most natural friction point for self-serve upgrades without gating essential utility.",
            recommendation="proceed_with_limits",
            assumptions=[
                Assumption(
                    name="activation_drop_from_gating",
                    low=0.05,
                    base=0.10,
                    high=0.20,
                    unit="rate",
                    provenance="simulated_estimate",
                    confidence=0.70,
                    proposed_by=self.name,
                    source_ref="product_onboarding_benchmarks"
                )
            ],
            evidence=[
                Evidence(
                    source_type="calculation",
                    source_ref="feature_matrix",
                    snippet="Capping at 3 team members and 500 tickets/mo protects 92% of Starter value proposition."
                )
            ],
            confidence=0.80,
            limitations=["Depends on UI upgrade prompts deployed in app."],
            status="ok"
        )


class SkepticAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Skeptic",
            role="Chief Skeptic & Assumption Auditor",
            objective="Stress-test claims, challenge optimism, downgrade unproven confidence scores",
            system_prompt=(
                "You are the Skeptic. You scrutinize assumptions from Growth, CFO, and other agents. "
                "Expose unproven extrapolations, missing controls, and demand provenance verification."
            )
        )

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        findings: List[Finding] = context.get("findings", [])
        challenged_assumptions = []

        # Audit findings for unverified optimism
        for f in findings:
            for asm in f.assumptions:
                if asm.name == "free_to_paid_conversion" and asm.base > 0.025:
                    # Challenge Growth's assumption
                    asm.challenged_by_skeptic = True
                    asm.confidence = round(max(0.3, asm.confidence - 0.20), 2)
                    challenged_assumptions.append(asm)

        claim = (
            f"Challenged {len(challenged_assumptions)} assumption(s). Growth's conversion estimate of 3.5% "
            f"lacks historical self-serve telemetry in NimbusDesk's data and carries external research provenance."
        ) if challenged_assumptions else "All reviewed assumptions meet baseline provenance standards."

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=claim,
            recommendation="proceed_with_limits",
            assumptions=[],
            evidence=[
                Evidence(
                    source_type="calculation",
                    source_ref="skeptic_audit_log",
                    snippet=f"Downgraded confidence on {len(challenged_assumptions)} speculative assumption(s)."
                )
            ],
            confidence=0.90,
            limitations=["Skeptic review based strictly on submitted findings and historical data."],
            status="ok"
        )
