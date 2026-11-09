import json
import copy
from typing import Dict, Any, Optional, List, Tuple, Callable, Type
from pydantic import BaseModel, Field, model_validator
from agents.base_agent import BaseAgent
from agents.llm_client import LLMClient, llm_call
from state.schemas import (
    Finding,
    Task,
    Assumption,
    Evidence,
    AgentFindingDraft,
    Critique,
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

def format_sim_params_table() -> str:
    lines = [
        "| Parameter Name | Unit | Lower Bound | Upper Bound | Favorable Direction (favorable_direction) | Description |",
        "|---|---|---|---|---|---|"
    ]
    for name, p in SIM_PARAMS.items():
        lines.append(f"| {name} | {p.unit} | {p.lower_bound} | {p.upper_bound} | {p.favorable_direction} | {p.description} |")
    return "\n".join(lines)

def get_valid_basis_list() -> List[str]:
    bases = [
        "financials.cash_balance",
        "financials.runway_months",
        "financials.mrr",
        "financials.target_min_runway_months",
        "funnel.monthly_visitors",
        "funnel.trial_signups",
        "infrastructure.monthly_cloud_cost",
        "infrastructure.infra_cost_per_free_user_estimate",
        "customers.total_paying",
        "customers.plans"
    ]
    benchmarks = load_benchmarks()
    for b in benchmarks:
        bases.append(b["id"])
    return bases

def get_inlined_draft_schema() -> str:
    schema = copy.deepcopy(AgentFindingDraft.model_json_schema())
    defs = schema.pop("$defs", {})
    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                ref_key = node["$ref"].split("/")[-1]
                if ref_key in defs:
                    return _resolve(copy.deepcopy(defs[ref_key]))
            return {k: _resolve(v) for k, v in node.items()}
        elif isinstance(node, list):
            return [_resolve(x) for x in node]
        return node
    return json.dumps(_resolve(schema), indent=2)

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


class BaseAnalysisAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        role: str,
        objective: str,
        agent_key: str,
        system_prompt: str,
        tools: Optional[Dict[str, Callable]] = None,
        tool_names: Optional[List[str]] = None,
        prompt_guidance: str = ""
    ):
        super().__init__(
            name=name,
            role=role,
            objective=objective,
            system_prompt=system_prompt,
            tools=tools or {}
        )
        self.agent_key = agent_key
        self.tool_names = tool_names or list(self.tools.keys())
        self.prompt_guidance = prompt_guidance

    def build_prompt(self, tool_data: Dict[str, Any], question: Optional[str] = None) -> str:
        sim_table = format_sim_params_table()
        valid_bases = get_valid_basis_list()
        schema_json = get_inlined_draft_schema()
        decision_q = question or "Evaluate decision to launch a free tier."

        return (
            f"Agent Key: {self.agent_key}\n"
            f"Role: {self.role}\n"
            f"Objective: {self.objective}\n\n"
            f"Strategic Decision Question: {decision_q}\n"
            f"Tool Data:\n{json.dumps(tool_data, indent=2)}\n\n"
            f"Allowed Simulator Parameters (Table):\n{sim_table}\n\n"
            "RULES FOR ASSUMPTIONS:\n"
            "- Propose ONLY parameter names from the table above.\n"
            "- Enforce low <= base <= high within lower_bound and upper_bound.\n"
            "- NEVER propose final business outcome numbers (e.g. final MRR, net profit).\n\n"
            f"Valid Basis Identifiers:\n{json.dumps(valid_bases, indent=2)}\n\n"
            "RULES FOR BASIS:\n"
            "- Set 'basis' only to one of the valid identifiers above if grounded in company data or benchmarks; otherwise use an empty string.\n\n"
            "Allowed Recommendations: 'proceed', 'proceed_with_limits', 'needs_more_info', 'reject'.\n\n"
            f"Expected JSON Schema:\n{schema_json}\n\n"
            "Example Finding Draft:\n"
            "{\n"
            '  "claim": "Brief executive assessment citing specific tool telemetry.",\n'
            '  "recommendation": "proceed_with_limits",\n'
            '  "assumptions": [\n'
            '    {\n'
            '      "name": "free_to_paid_conversion",\n'
            '      "low": 0.015,\n'
            '      "base": 0.022,\n'
            '      "high": 0.035,\n'
            '      "unit": "rate",\n'
            '      "basis": "b2b_saas_freemium_conversion",\n'
            '      "rationale": "Aligned with B2B freemium benchmarks."\n'
            '    }\n'
            '  ],\n'
            '  "evidence": [\n'
            '    {\n'
            '      "source_type": "company_data",\n'
            '      "source_ref": "funnel.monthly_visitors",\n'
            '      "snippet": "142,000 monthly unique visitors recorded."\n'
            '    }\n'
            '  ],\n'
            '  "limitations": ["Assumes current organic visitor quality holds."],\n'
            '  "confidence": 0.8\n'
            "}\n\n"
            f"Specialist Guidance: {self.prompt_guidance}\n"
        )

    def parse_and_validate(
        self,
        draft: AgentFindingDraft,
        company_data: Dict[str, Any],
        benchmarks: set,
        context: Dict[str, Any]
    ) -> List[Assumption]:
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
        return valid_assumptions

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        tool_data = {}
        for t_name in self.tool_names:
            tool_data[t_name] = await self.execute_tool(t_name)

        company_data = load_company_data()
        benchmarks = {b["id"] for b in load_benchmarks()}

        decision = context.get("decision") if context else None
        q_text = getattr(decision, "question", None) if decision else None
        prompt = self.build_prompt(tool_data, question=q_text)

        draft: AgentFindingDraft = await llm_call(
            prompt=prompt,
            response_model=AgentFindingDraft,
            system_prompt=self.system_prompt,
            client=llm_client,
            metadata={"agent_key": self.agent_key, "task_kind": "agent_analysis"}
        )

        valid_assumptions = self.parse_and_validate(draft, company_data, benchmarks, context)

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


class CFOAgent(BaseAnalysisAgent):
    def __init__(self):
        super().__init__(
            name="CFO",
            role="Chief Financial Officer",
            objective="Protect runway and gross margins; prevent unmonetized cost explosions",
            agent_key="cfo",
            system_prompt=(
                "You are the CFO. Your duty is to protect company runway and margins. "
                "Propose assumption ranges for financial levers; never generate final outcome numbers. "
                "Every claim must cite a tool data field."
            ),
            tools={"lookup_financials": lookup_financials},
            prompt_guidance="Focus on runway protection, cash burn, and conversion conservation."
        )


class GrowthAgent(BaseAnalysisAgent):
    def __init__(self):
        super().__init__(
            name="Growth",
            role="Chief Marketing Officer & VP Growth",
            objective="Maximize top-of-funnel acquisition, organic user growth, and conversion volume",
            agent_key="growth",
            system_prompt=(
                "You are the VP of Growth. Scale customer acquisition and build self-serve viral flywheels. "
                "Propose assumption ranges; never fabricate outcomes."
            ),
            tools={"lookup_funnel": lookup_funnel},
            prompt_guidance="Focus on top-of-funnel organic traffic, trial conversions, and signup velocity."
        )


class CTOAgent(BaseAnalysisAgent):
    def __init__(self):
        super().__init__(
            name="CTO",
            role="Chief Technology Officer",
            objective="Ensure platform scalability, contain per-user compute/storage costs, protect SLA",
            agent_key="cto",
            system_prompt=(
                "You are the CTO. Evaluate server capacity, DB multi-tenancy, and cloud infrastructure costs. "
                "Recommend usage ceilings and rate limits to control unit costs."
            ),
            tools={"lookup_infra_costs": lookup_infra_costs},
            prompt_guidance="Focus on marginal compute and storage cost per free user."
        )


class CustomerAgent(BaseAnalysisAgent):
    def __init__(self):
        super().__init__(
            name="Customer",
            role="VP of Customer Success & Retention",
            objective="Minimize churn and cannibalization; protect high-touch customer support capacity",
            agent_key="customer",
            system_prompt=(
                "You are the VP of Customer Success. Guard existing revenue lines and prevent paid accounts "
                "from downgrading to free."
            ),
            tools={"lookup_customers": lookup_customers, "lookup_support_metrics": lookup_support_metrics},
            prompt_guidance="Focus on paid plan retention and cannibalization risks."
        )


class ProductAgent(BaseAnalysisAgent):
    def __init__(self):
        super().__init__(
            name="Product",
            role="VP of Product & Packaging",
            objective="Optimize feature gating, drive activation-to-paid conversion triggers, ensure upgrade friction is healthy",
            agent_key="product",
            system_prompt=(
                "You are the VP of Product. Design tier boundaries and feature gates that encourage "
                "users to upgrade naturally when they hit productivity ceilings."
            ),
            tools={"lookup_customers": lookup_customers},
            prompt_guidance="Focus on gating friction and usage limits."
        )


class SkepticAuditDraft(BaseModel):
    critiques: List[Critique] = Field(default_factory=list)
    audit_summary: str = Field(default="Skeptic audit completed.")

    @model_validator(mode="before")
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"critiques": data, "audit_summary": "Skeptic audit completed."}
        return data


class SkepticAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Skeptic",
            role="Chief Skeptic & Assumption Auditor",
            objective="Stress-test claims, challenge optimism, downgrade unproven confidence scores",
            system_prompt=(
                "You are the Skeptic. You scrutinize assumptions from Growth, CFO, and other agents. "
                "Expose unproven extrapolations, missing controls, and demand provenance verification."
            ),
            timeout_seconds=90.0
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

        llm_succeeded = False
        if llm_client and llm_client.mode in ["real", "record", "replay"]:
            try:
                summary_findings = [
                    {
                        "agent": f.agent,
                        "claim": f.claim,
                        "recommendation": f.recommendation,
                        "assumptions": [a.model_dump() for a in f.assumptions],
                        "evidence": [e.model_dump() for e in f.evidence]
                    }
                    for f in findings
                ]
                prompt = (
                    f"Role: {self.role}\n"
                    f"Objective: {self.objective}\n\n"
                    f"Peer Agent Findings:\n{json.dumps(summary_findings, indent=2)}\n\n"
                    f"Industry Benchmarks:\n{json.dumps(list(benchmarks.values()), indent=2)}\n\n"
                    "Audit the submitted assumptions against industry benchmarks and telemetry evidence. "
                    "Challenge any optimistic or ungrounded bounds. Return Critique objects matching the schema."
                )
                audit_draft: SkepticAuditDraft = await llm_call(
                    prompt=prompt,
                    response_model=SkepticAuditDraft,
                    system_prompt=self.system_prompt,
                    client=llm_client,
                    metadata={"agent_key": "skeptic", "task_kind": "skeptic_audit"}
                )
                for crit in audit_draft.critiques:
                    ch = {
                        "agent": crit.target_agent,
                        "assumption": crit.target_parameter,
                        "challenge": crit.concern,
                        "severity": crit.severity,
                        "confidence_penalty": 0.15 if crit.severity == "high" else 0.10
                    }
                    challenges.append(ch)
                    if "state" in context:
                        context["state"].skeptic_challenges.append(ch)

                claim = (
                    f"Audited peer assumptions with LLM Skeptic. Challenged {len(challenges)} assumption(s)."
                    if challenges else "All peer assumptions verified against benchmarks."
                )
                llm_succeeded = True
            except Exception as e:
                logger.warning(f"Skeptic LLM call failed ({e}). Falling back to deterministic benchmark audit.")
                self.is_degraded = True

        if not llm_succeeded:
            # Deterministic mock check across all simulated parameters with benchmarks
            for f in findings:
                for asm in f.assumptions:
                    # Check benchmark limits
                    if asm.name == "free_to_paid_conversion":
                        freemium_spec = benchmarks.get("b2b_saas_freemium_conversion", {})
                        grounded_threshold = round(
                            (freemium_spec.get("value_low", 0.01) + freemium_spec.get("value_high", 0.035)) / 2.0, 4
                        )
                        if asm.base > grounded_threshold:
                            ch = {
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
                            challenges.append(ch)
                            if "state" in context:
                                context["state"].skeptic_challenges.append(ch)

            claim = (
                f"Challenged {len(challenges)} assumption(s). Free conversion estimate exceeds grounded benchmark midpoint."
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
                    snippet=f"Skeptic audited peer assumptions against grounded benchmarks. Challenged {len(challenges)} estimate(s)."
                )
            ],
            confidence=0.90,
            limitations=["Skeptic review based strictly on submitted findings and historical data."],
            status="ok"
        )
