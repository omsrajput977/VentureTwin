import json
from typing import Dict, Any, Optional, List, Tuple
from agents.base_agent import BaseAgent
from agents.llm_client import LLMClient, llm_call
from state.schemas import (
    Finding,
    Task,
    Assumption,
    Evidence,
    AgentFindingDraft,
    ProvenanceType
)
from simulation.params import SIM_PARAMS
from data.loader import load_company_data, load_benchmarks
from agents.tools import (
    lookup_financials,
    lookup_funnel,
    lookup_customers,
    lookup_infra_costs,
    lookup_support_metrics
)

def resolve_provenance_and_validate(
    draft_name: str,
    draft_low: float,
    draft_base: float,
    draft_high: float,
    draft_unit: str,
    basis: str,
    company_data: Dict[str, Any],
    benchmark_ids: set
) -> Tuple[Optional[Assumption], Optional[str]]:
    """
    Assigns provenance strictly in code.
    Filters against SIM_PARAMS. Unknown parameters return (None, draft_name).
    """
    if draft_name not in SIM_PARAMS:
        return None, draft_name

    spec = SIM_PARAMS[draft_name]
    clamped_low = max(spec.lower_bound, min(spec.upper_bound, draft_low))
    clamped_base = max(spec.lower_bound, min(spec.upper_bound, draft_base))
    clamped_high = max(spec.lower_bound, min(spec.upper_bound, draft_high))

    # Enforce low <= base <= high
    if clamped_low > clamped_base:
        clamped_low = clamped_base
    if clamped_base > clamped_high:
        clamped_high = clamped_base

    provenance: ProvenanceType = "ai_assumption"
    source_ref = None

    if basis in benchmark_ids:
        provenance = "external_research"
        source_ref = basis
    elif basis:
        # Check if basis matches a path in company_data
        parts = basis.split(".")
        curr: Any = company_data
        found = True
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                found = False
                break
        if found and isinstance(curr, (int, float)):
            if abs(float(curr) - float(clamped_base)) <= max(0.01, 0.05 * abs(float(curr))):
                provenance = "verified_data"
                source_ref = basis

    asm = Assumption(
        name=draft_name,
        low=round(clamped_low, 4),
        base=round(clamped_base, 4),
        high=round(clamped_high, 4),
        unit=spec.unit,
        provenance=provenance,
        source_ref=source_ref,
        confidence=0.85 if provenance == "verified_data" else 0.70 if provenance == "external_research" else 0.60
    )
    return asm, None


class CFOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CFO",
            role="Chief Financial Officer",
            objective="Protect runway and gross margins; prevent unmonetized cost explosions",
            system_prompt=(
                "You are the CFO. Your duty is to protect company runway and margins. "
                "Propose assumption ranges for financial levers; never generate final outcome numbers. "
                "Every claim must cite a tool data field."
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
        company_data = load_company_data()
        benchmarks = {b["id"] for b in load_benchmarks()}

        prompt = (
            f"Role: {self.role}\n"
            f"Objective: {self.objective}\n"
            f"Company Financials: {json.dumps(fin)}\n"
            f"Allowed SIM_PARAMS: {list(SIM_PARAMS.keys())}\n"
            "Evaluate decision to launch a free tier. Propose structured assumptions with ranges."
        )

        draft: AgentFindingDraft = await llm_call(
            prompt=prompt,
            response_model=AgentFindingDraft,
            system_prompt=self.system_prompt,
            client=llm_client
        )

        valid_assumptions = []
        for d_asm in draft.assumptions:
            asm, ignored = resolve_provenance_and_validate(
                d_asm.name, d_asm.low, d_asm.base, d_asm.high, d_asm.unit,
                d_asm.basis, company_data, benchmarks
            )
            if asm:
                asm.proposed_by = self.name
                valid_assumptions.append(asm)
            elif ignored and "state" in context:
                context["state"].ignored_assumptions.append(ignored)

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=draft.claim,
            recommendation=draft.recommendation,
            assumptions=valid_assumptions,
            evidence=draft.evidence,
            confidence=draft.confidence,
            limitations=draft.limitations,
            status="ok"
        )


class GrowthAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Growth",
            role="Chief Marketing Officer & VP Growth",
            objective="Maximize top-of-funnel acquisition, organic user growth, and conversion volume",
            system_prompt=(
                "You are the VP of Growth. Scale customer acquisition and build self-serve viral flywheels. "
                "Propose assumption ranges; never fabricate outcomes."
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
        company_data = load_company_data()
        benchmarks = {b["id"] for b in load_benchmarks()}

        prompt = (
            f"Role: {self.role}\n"
            f"Objective: {self.objective}\n"
            f"Company Funnel Data: {json.dumps(funnel)}\n"
            f"Allowed SIM_PARAMS: {list(SIM_PARAMS.keys())}\n"
            "Evaluate top-of-funnel opportunity for free plan. Propose structured assumptions."
        )

        draft: AgentFindingDraft = await llm_call(
            prompt=prompt,
            response_model=AgentFindingDraft,
            system_prompt=self.system_prompt,
            client=llm_client
        )

        valid_assumptions = []
        for d_asm in draft.assumptions:
            asm, ignored = resolve_provenance_and_validate(
                d_asm.name, d_asm.low, d_asm.base, d_asm.high, d_asm.unit,
                d_asm.basis, company_data, benchmarks
            )
            if asm:
                asm.proposed_by = self.name
                valid_assumptions.append(asm)
            elif ignored and "state" in context:
                context["state"].ignored_assumptions.append(ignored)

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=draft.claim,
            recommendation=draft.recommendation,
            assumptions=valid_assumptions,
            evidence=draft.evidence,
            confidence=draft.confidence,
            limitations=draft.limitations,
            status="ok"
        )


class CTOAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CTO",
            role="Chief Technology Officer",
            objective="Ensure platform scalability, uptime SLAs, and contain cloud compute/database costs",
            system_prompt=(
                "You are the CTO. Evaluate infrastructure load and marginal cloud cost per active free user. "
                "Propose parameter bounds; do not compute outcome metrics."
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
        company_data = load_company_data()
        benchmarks = {b["id"] for b in load_benchmarks()}

        prompt = (
            f"Role: {self.role}\n"
            f"Objective: {self.objective}\n"
            f"Infrastructure Telemetry: {json.dumps(infra)}\n"
            f"Allowed SIM_PARAMS: {list(SIM_PARAMS.keys())}\n"
            "Evaluate infrastructure feasibility and usage caps."
        )

        draft: AgentFindingDraft = await llm_call(
            prompt=prompt,
            response_model=AgentFindingDraft,
            system_prompt=self.system_prompt,
            client=llm_client
        )

        valid_assumptions = []
        for d_asm in draft.assumptions:
            asm, ignored = resolve_provenance_and_validate(
                d_asm.name, d_asm.low, d_asm.base, d_asm.high, d_asm.unit,
                d_asm.basis, company_data, benchmarks
            )
            if asm:
                asm.proposed_by = self.name
                valid_assumptions.append(asm)
            elif ignored and "state" in context:
                context["state"].ignored_assumptions.append(ignored)

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=draft.claim,
            recommendation=draft.recommendation,
            assumptions=valid_assumptions,
            evidence=draft.evidence,
            confidence=draft.confidence,
            limitations=draft.limitations,
            status="ok"
        )


class CustomerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Customer",
            role="VP Customer Success & Retention",
            objective="Protect existing customer base from churn, minimize cannibalization of paid plans",
            system_prompt=(
                "You are the VP of Customer Success. Protect paying subscribers from cannibalization. "
                "Propose churn and cannibalization assumption ranges."
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
        company_data = load_company_data()
        benchmarks = {b["id"] for b in load_benchmarks()}

        prompt = (
            f"Role: {self.role}\n"
            f"Objective: {self.objective}\n"
            f"Customer Metrics: {json.dumps(customers)}\n"
            f"Allowed SIM_PARAMS: {list(SIM_PARAMS.keys())}\n"
            "Evaluate cannibalization and retention impact."
        )

        draft: AgentFindingDraft = await llm_call(
            prompt=prompt,
            response_model=AgentFindingDraft,
            system_prompt=self.system_prompt,
            client=llm_client
        )

        valid_assumptions = []
        for d_asm in draft.assumptions:
            asm, ignored = resolve_provenance_and_validate(
                d_asm.name, d_asm.low, d_asm.base, d_asm.high, d_asm.unit,
                d_asm.basis, company_data, benchmarks
            )
            if asm:
                asm.proposed_by = self.name
                valid_assumptions.append(asm)
            elif ignored and "state" in context:
                context["state"].ignored_assumptions.append(ignored)

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=draft.claim,
            recommendation=draft.recommendation,
            assumptions=valid_assumptions,
            evidence=draft.evidence,
            confidence=draft.confidence,
            limitations=draft.limitations,
            status="ok"
        )


class ProductAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Product",
            role="VP Product",
            objective="Define product packaging, feature gates, and self-serve upgrade milestones",
            system_prompt="You are the VP of Product. Propose gating friction and conversion uplift assumptions."
        )

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        company_data = load_company_data()
        benchmarks = {b["id"] for b in load_benchmarks()}

        prompt = (
            f"Role: {self.role}\n"
            f"Objective: {self.objective}\n"
            f"Allowed SIM_PARAMS: {list(SIM_PARAMS.keys())}\n"
            "Propose feature gating tradeoffs for Strategy B usage caps."
        )

        draft: AgentFindingDraft = await llm_call(
            prompt=prompt,
            response_model=AgentFindingDraft,
            system_prompt=self.system_prompt,
            client=llm_client
        )

        valid_assumptions = []
        for d_asm in draft.assumptions:
            asm, ignored = resolve_provenance_and_validate(
                d_asm.name, d_asm.low, d_asm.base, d_asm.high, d_asm.unit,
                d_asm.basis, company_data, benchmarks
            )
            if asm:
                asm.proposed_by = self.name
                valid_assumptions.append(asm)
            elif ignored and "state" in context:
                context["state"].ignored_assumptions.append(ignored)

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=draft.claim,
            recommendation=draft.recommendation,
            assumptions=valid_assumptions,
            evidence=draft.evidence,
            confidence=draft.confidence,
            limitations=draft.limitations,
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
        challenges: List[Dict[str, Any]] = []

        benchmarks = {b["id"]: b for b in load_benchmarks()}
        freemium_spec = benchmarks.get("b2b_saas_freemium_conversion", {})
        grounded_threshold = round(
            (freemium_spec.get("value_low", 0.01) + freemium_spec.get("value_high", 0.035)) / 2.0, 4
        )

        # Audit assumptions against grounded benchmark midpoint (no magic literals)
        for f in findings:
            for asm in f.assumptions:
                if asm.name == "free_to_paid_conversion" and asm.base > grounded_threshold:
                    challenge = {
                        "agent": f.agent,
                        "assumption": asm.name,
                        "base": asm.base,
                        "grounded_threshold": grounded_threshold,
                        "challenge": (
                            f"Proposed conversion ({asm.base*100:.1f}%) exceeds grounded freemium benchmark midpoint "
                            f"({grounded_threshold*100:.2f}% from b2b_saas_freemium_conversion) without self-serve historical telemetry."
                        ),
                        "confidence_penalty": 0.15
                    }
                    challenges.append(challenge)
                    if "state" in context:
                        context["state"].skeptic_challenges.append(challenge)

        claim = (
            f"Challenged {len(challenges)} assumption(s). Free conversion estimate exceeds grounded benchmark midpoint "
            f"({grounded_threshold*100:.2f}% in b2b_saas_freemium_conversion) and carries external research provenance."
        ) if challenges else "All reviewed assumptions meet baseline provenance standards."

        return Finding(
            agent=self.name,
            task_id=task.id,
            claim=claim,
            recommendation="proceed_with_limits",
            assumptions=[],
            evidence=[
                Evidence(
                    source_type="external",
                    source_ref="b2b_saas_freemium_conversion",
                    snippet=f"Grounded freemium benchmark midpoint is {grounded_threshold*100:.2f}%. Challenged {len(challenges)} optimistic estimate(s)."
                )
            ],
            confidence=0.90,
            limitations=["Skeptic review based strictly on submitted findings and historical data."],
            status="ok"
        )
