import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Set, List
from state.schemas import (
    Decision,
    Task,
    Finding,
    Assumption,
    Conflict,
    SimulationRun,
    VerificationResult,
    Report,
    Event
)
from state.shared_state import WorkflowState
from state.event_bus import EventBus
from orchestrator.dag import TaskDAG
from orchestrator.decomposer import decompose_decision
from orchestrator.checkpointer import SQLiteCheckpointer
from agents.registry import AgentRegistry, default_registry
from agents.llm_client import LLMClient
from simulation.engine import (
    simulate,
    run_monte_carlo,
    run_sensitivity_analysis,
    find_flip_point
)
from simulation.reconcile import reconcile_assumptions, ReconciledParams
from conflict.detector import detect_all_conflicts, generate_deterministic_conflict_id
from conflict.resolver import resolve_conflict_via_simulation
from simulation.params import SIM_PARAMS
from verification.verifier import run_all_verification_checks
from report.report_builder import build_consolidated_report
from data.loader import load_company_data

logger = logging.getLogger(__name__)

class Supervisor:
    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        checkpointer: Optional[SQLiteCheckpointer] = None,
        event_bus: Optional[EventBus] = None,
        llm_client: Optional[LLMClient] = None,
        company_data: Optional[Dict[str, Any]] = None
    ):
        self.registry = registry or default_registry
        self.checkpointer = checkpointer or SQLiteCheckpointer()
        self.event_bus = event_bus or EventBus()
        self.llm_client = llm_client
        self.company_data = company_data
        self.agent_delay_hook = None
        self.injected_failures: Dict[str, str] = {}
        self.tornado_data: List[Dict[str, Any]] = []
        self.flip_point_info: Dict[str, Any] = {}
        self.mc_summary: Dict[str, Any] = {}
        self.current_state: Optional[WorkflowState] = None

    def inject_failure(
        self,
        agent_name: str,
        mode: str,
        persist: bool = False,
        fail_attempts: int = 1
    ) -> None:
        """Inject a mid-run failure: 'timeout', 'exception', or 'bad_output'"""
        clean_mode = mode.replace("persistent_", "")
        is_persist = persist or mode.startswith("persistent_")
        self.injected_failures[agent_name.lower()] = {
            "mode": clean_mode,
            "persist": is_persist,
            "fail_attempts": fail_attempts,
            "attempts_done": 0
        }

    async def execute_workflow(
        self,
        decision: Decision,
        resume_from_checkpoint: bool = False
    ) -> WorkflowState:
        """
        Executes the full DAG workflow asynchronously with parallel dispatch,
        checkpointing, event emission, and failure recovery.
        """
        state: Optional[WorkflowState] = None
        if resume_from_checkpoint:
            state = self.checkpointer.load_latest_checkpoint(decision.id)

        if state is None:
            dag = decompose_decision(decision)
            state = WorkflowState(
                decision=decision,
                tasks=dag.tasks,
                status="running"
            )
            for task in dag.tasks.values():
                await self.event_bus.emit(
                    "task_created",
                    agent="supervisor",
                    payload={"task_id": task.id, "owner": task.owner_agent}
                )
        else:
            dag = TaskDAG()
            for t in state.tasks.values():
                dag.add_task(t)

        completed_ids: Set[str] = {
            t.id for t in state.tasks.values() if t.status == "done"
        }
        active_ids: Set[str] = set()
        self.current_state = state

        while not dag.is_complete(completed_ids):
            ready_tasks = dag.get_ready_tasks(completed_ids, active_ids)

            if not ready_tasks:
                if active_ids:
                    await asyncio.sleep(0.05)
                    continue
                else:
                    state.status = "failed"
                    break

            for task in ready_tasks:
                active_ids.add(task.id)

            if int(os.getenv("LLM_MAX_CONCURRENCY", "1")) <= 1:
                # Sequential execution prevents burst rate limits on free-tier LLM providers
                results = []
                for task in ready_tasks:
                    try:
                        res = await self._run_task_with_recovery(task, state)
                        results.append(res)
                    except Exception as exc:
                        results.append(exc)
            else:
                task_coroutines = [
                    self._run_task_with_recovery(task, state)
                    for task in ready_tasks
                ]
                results = await asyncio.gather(*task_coroutines, return_exceptions=True)

            for task, res in zip(ready_tasks, results):
                active_ids.remove(task.id)
                if isinstance(res, Exception):
                    logger.error(f"Task {task.id} failed terminally: {res}")
                    state.mark_task_failed(task.id, str(res))
                    state.status = "failed"
                elif res is not None:
                    completed_ids.add(task.id)
                    state.mark_task_done(task.id)
                    self.checkpointer.save_checkpoint(state, task.id)

            if state.status == "failed":
                break

        if dag.is_complete(completed_ids):
            state.status = "completed" if (not state.degraded_agents and not state.recovered_agents) else "degraded"

        state.events = self.event_bus.get_events()
        return state

    async def _run_task_with_recovery(
        self,
        task: Task,
        state: WorkflowState
    ) -> Optional[Any]:
        agent_name = task.owner_agent.lower()
        agent = self.registry.get(agent_name)

        await self.event_bus.emit(
            "agent_started",
            agent=agent_name,
            payload={"task_id": task.id, "kind": task.kind}
        )

        if self.agent_delay_hook is not None:
            delay_res = self.agent_delay_hook(agent_name)
            if asyncio.iscoroutine(delay_res):
                await delay_res

        injected = self.injected_failures.get(agent_name)
        max_attempts = task.max_attempts

        for attempt in range(1, max_attempts + 1):
            task.attempts = attempt
            # Dynamically check injected_failures on each attempt for live mid-run injections
            if not injected:
                injected = self.injected_failures.get(agent_name)
            try:
                if task.kind == "agent_analysis":
                    if agent is None:
                        raise ValueError(f"Agent '{agent_name}' not found in registry for analysis task {task.id}")
                    context = {"findings": state.findings, "state": state, "decision": state.decision}
                    finding = await agent.run(
                        task,
                        context=context,
                        llm_client=self.llm_client,
                        injected_failure=injected
                    )
                    # Check if failure was injected dynamically mid-run while agent was executing
                    mid_injected = self.injected_failures.get(agent_name)
                    if mid_injected and not injected:
                        mode = mid_injected.get("mode", "exception")
                        if mode == "timeout":
                            raise asyncio.TimeoutError(f"Agent {agent_name.upper()} timed out due to mid-run injected failure")
                        elif mode == "bad_output":
                            raise ValueError(f"Injected bad output schema for {agent_name.upper()}")
                        else:
                            from agents.base_agent import AgentExecutionError
                            raise AgentExecutionError(f"Agent {agent_name.upper()} crashed with mid-run injected exception")

                    state.add_finding(finding)
                    await self.event_bus.emit(
                        "finding_posted",
                        agent=agent_name,
                        payload={"task_id": task.id, "finding": finding.model_dump()}
                    )
                    return finding
                elif task.kind in [
                    "skeptic_audit",
                    "discussion",
                    "conflict_resolution",
                    "simulation",
                    "report_draft",
                    "verification",
                    "report_finalize"
                ]:
                    return await self._run_builtin_supervisor_task(task, state)
                else:
                    raise ValueError(f"Unknown or unsupported task kind: {task.kind}")

            except Exception as e:
                logger.warning(f"Task {task.id} (kind {task.kind}, agent {agent_name}) attempt {attempt} failed: {e}")
                await self.event_bus.emit(
                    "agent_failed",
                    agent=agent_name,
                    payload={"task_id": task.id, "attempt": attempt, "error": str(e)}
                )

                if attempt < max_attempts:
                    await self.event_bus.emit(
                        "recovery_started",
                        agent=agent_name,
                        payload={"task_id": task.id, "mode": "retry"}
                    )
                    await asyncio.sleep(0.02 * attempt)
                    await self.event_bus.emit(
                        "recovery_done",
                        agent=agent_name,
                        payload={"task_id": task.id, "mode": "retry_ready"}
                    )
                else:
                    # Final attempt failed
                    if task.kind == "agent_analysis":
                        # Attempt BackupAnalyst
                        await self.event_bus.emit(
                            "recovery_started",
                            agent=agent_name,
                            payload={"task_id": task.id, "mode": "backup_analyst"}
                        )
                        try:
                            from agents.backup_agent import BackupAnalyst
                            backup = BackupAnalyst()
                            backup_finding = await backup.run_backup(task, state, self.llm_client)
                            backup_finding.recovered_via_backup = True
                            backup_finding.confidence = min(backup_finding.confidence, 0.70)
                            if agent_name.upper() not in state.recovered_agents:
                                state.recovered_agents.append(agent_name.upper())
                            state.add_finding(backup_finding)
                            # Workflow remains 'running' until full DAG completes, then transitions to 'degraded'
                            await self.event_bus.emit(
                                "recovery_done",
                                agent=agent_name,
                                payload={"task_id": task.id, "mode": "backup_analyst_completed"}
                            )
                            return backup_finding
                        except Exception as backup_err:
                            logger.warning(f"Backup analyst failed for {task.id}: {backup_err}")
                            await self.event_bus.emit(
                                "recovery_started",
                                agent=agent_name,
                                payload={"task_id": task.id, "mode": "degraded_fallback"}
                            )
                            if agent_name.upper() not in state.degraded_agents:
                                state.degraded_agents.append(agent_name.upper())
                            fallback_finding = self._generate_fallback_finding(task, agent_name)
                            state.add_finding(fallback_finding)
                            # Workflow remains 'running' until full DAG completes, then transitions to 'degraded'
                            await self.event_bus.emit(
                                "recovery_done",
                                agent=agent_name,
                                payload={"task_id": task.id, "mode": "degraded_completed"}
                            )
                            return fallback_finding
                    else:
                        # Supervisor-run task failure: terminal failure!
                        logger.error(f"Supervisor task {task.id} (kind {task.kind}) failed terminally: {e}")
                        state.mark_task_failed(task.id, str(e))
                        state.status = "failed"
                        await self.event_bus.emit(
                            "workflow_failed",
                            agent="supervisor",
                            payload={"task_id": task.id, "error": str(e)}
                        )
                        self.checkpointer.save_checkpoint(state, task.id)
                        raise RuntimeError(f"Supervisor task {task.id} failed terminally: {e}")

        return None

    def _generate_fallback_finding(self, task: Task, agent_name: str) -> Finding:
        return Finding(
            agent=agent_name.upper(),
            task_id=task.id,
            claim=f"Agent {agent_name.upper()} ran in degraded fallback mode after unrecoverable failure.",
            recommendation="proceed_with_limits",
            assumptions=[
                Assumption(
                    name=f"{agent_name}_fallback_estimate",
                    low=1.0, base=1.0, high=1.0,
                    unit="ratio",
                    provenance="fallback_degraded",
                    confidence=0.30,
                    proposed_by=agent_name.upper(),
                    source_ref="system.fallback_degraded"
                )
            ],
            evidence=[],
            confidence=0.30,
            limitations=[f"Generated via fallback due to {agent_name} process failure."],
            status="ok",
            degraded=True,
            degraded_reason=f"Unrecoverable failure on {task.id}"
        )

    async def _run_builtin_supervisor_task(self, task: Task, state: WorkflowState) -> Any:
        if task.kind == "skeptic_audit" or task.id == "task_skeptic_audit":
            skeptic = self.registry.get("skeptic")
            if not skeptic:
                raise ValueError("Skeptic agent not found in registry")
            injected = self.injected_failures.get("skeptic")
            context = {"findings": state.findings, "state": state, "decision": state.decision}
            finding = await skeptic.run(task, context=context, llm_client=self.llm_client, injected_failure=injected)
            mid_injected = self.injected_failures.get("skeptic")
            if mid_injected and not injected:
                mode = mid_injected.get("mode", "exception")
                if mode == "timeout":
                    raise asyncio.TimeoutError("Agent SKEPTIC timed out due to mid-run injected failure")
                elif mode == "bad_output":
                    raise ValueError("Injected bad output schema for SKEPTIC")
                else:
                    from agents.base_agent import AgentExecutionError
                    raise AgentExecutionError("Agent SKEPTIC crashed with mid-run injected exception")
            state.add_finding(finding)
            await self.event_bus.emit(
                "finding_posted",
                agent="skeptic",
                payload={"task_id": task.id, "finding": finding.model_dump()}
            )
            return finding
        elif task.kind == "discussion" or task.id == "task_agent_discussion":
            return await self._run_discussion_task(task, state)
        elif task.kind == "conflict_resolution" or task.id == "task_conflict_resolution":
            return await self._run_conflict_resolution_task(task, state)
        elif task.kind == "simulation" or task.id == "task_simulation_engine":
            return await self._run_simulation_task(task, state)
        elif task.kind == "report_draft" or task.id == "task_report_draft":
            return await self._run_report_draft_task(task, state)
        elif task.kind == "verification" or task.id == "task_workflow_verification":
            return await self._run_verification_task(task, state)
        elif task.kind == "report_finalize" or task.id in ["task_report_finalize", "task_report_generation"]:
            return await self._run_report_finalize_task(task, state)
        else:
            raise ValueError(f"Unknown supervisor task kind: {task.kind} (id: {task.id})")

    async def _run_discussion_task(self, task: Task, state: WorkflowState) -> Any:
        rebuttals_logged = []
        consolidated_map: Dict[str, Any] = {}

        # Consolidate multi-agent rebuttals into 1 structured call in real/record mode to prevent RPM rate limit spikes
        if self.llm_client and self.llm_client.mode in ["real", "record"] and len(state.skeptic_challenges) > 1:
            from state.schemas import DiscussionRebuttalsDraft
            critiques_summary = [
                {
                    "agent": c.get("agent", ""),
                    "parameter": c.get("assumption", ""),
                    "critique": c.get("challenge", "")
                }
                for c in state.skeptic_challenges
            ]
            prompt = (
                "You are facilitating the executive cross-agent discussion. "
                "The Skeptic has audited peer assumptions and raised these critiques:\n"
                f"{json.dumps(critiques_summary, indent=2)}\n\n"
                "For EACH challenged agent above, formulate a structured rebuttal: "
                "choose 'concede', 'defend', or 'compromise'. "
                "Provide updated parameter bounds (updated_low, updated_base, updated_high) if conceding or compromising. "
                "Return a JSON object containing a list of 'rebuttals'."
            )
            try:
                draft: DiscussionRebuttalsDraft = await llm_call(
                    prompt=prompt,
                    response_model=DiscussionRebuttalsDraft,
                    system_prompt="You coordinate executive cross-agent rebuttals. Return strictly valid JSON matching the schema.",
                    client=self.llm_client,
                    metadata={"agent_key": "discussion", "task_kind": "discussion"}
                )
                for reb in draft.rebuttals:
                    consolidated_map[reb.agent.lower()] = reb
            except Exception as e:
                logger.warning(f"Consolidated rebuttal call failed ({e}). Falling back to individual/telemetry handling.")

        for chal in state.skeptic_challenges:
            target_agent = chal.get("agent", "")
            param = chal.get("assumption", "")
            concern = chal.get("challenge", "")

            if target_agent.lower() in consolidated_map:
                rebuttal = consolidated_map[target_agent.lower()]
            else:
                prompt = (
                    f"Agent: {target_agent}\n"
                    f"Parameter Challenged: {param}\n"
                    f"Skeptic Critique: {concern}\n"
                    "Respond with a structured rebuttal: choose 'concede', 'defend', or 'compromise'. "
                    "Provide updated parameter bounds if conceding or compromising."
                )

                from agents.llm_client import llm_call
                from state.schemas import Rebuttal, Message
                try:
                    rebuttal = await llm_call(
                        prompt=prompt,
                        response_model=Rebuttal,
                        system_prompt=f"You are {target_agent}. Provide a bounded professional defense or concession to the Skeptic.",
                        client=self.llm_client,
                        metadata={"agent_key": target_agent.lower(), "parameter": param, "task_kind": "discussion"}
                    )
                except Exception as reb_err:
                    logger.warning(f"Rebuttal call failed for {target_agent}: {reb_err}. Maintaining telemetry defense.")
                    rebuttal = Rebuttal(
                        agent=target_agent,
                        parameter=param,
                        stance="defend",
                        rationale="Maintained baseline estimate grounded in verified telemetry."
                    )

            state.rebuttals.append(rebuttal)
            msg = Message(
                from_agent=target_agent,
                to_agent="Skeptic",
                round=1,
                content=f"[{rebuttal.stance.upper()}] {rebuttal.rationale}"
            )
            state.discussion_messages.append(msg)
            await self.event_bus.emit(
                "finding_posted",
                agent=target_agent,
                payload={"type": "rebuttal", "rebuttal": rebuttal.model_dump()}
            )

            if rebuttal.stance in ["concede", "compromise"] and rebuttal.updated_base is not None:
                spec = SIM_PARAMS.get(param)
                if spec:
                    raw_low = rebuttal.updated_low if rebuttal.updated_low is not None else spec.lower_bound
                    raw_base = rebuttal.updated_base
                    raw_high = rebuttal.updated_high if rebuttal.updated_high is not None else spec.upper_bound
                    clamped_low = max(spec.lower_bound, min(spec.upper_bound, raw_low))
                    clamped_base = max(spec.lower_bound, min(spec.upper_bound, raw_base))
                    clamped_high = max(spec.lower_bound, min(spec.upper_bound, raw_high))
                    if clamped_low > clamped_base:
                        clamped_low = clamped_base
                    if clamped_base > clamped_high:
                        clamped_high = clamped_base

                    orig_id = None
                    for f in state.findings:
                        if f.agent.lower() == target_agent.lower():
                            for a in f.assumptions:
                                if a.name == param:
                                    orig_id = a.id or f"asm_{target_agent.lower()}_{param}"
                                    a.id = orig_id
                                    a.revision_of = orig_id
                                    a.revision_rationale = rebuttal.rationale
                                    a.base = round(clamped_base, 4)
                                    a.low = round(clamped_low, 4)
                                    a.high = round(clamped_high, 4)
                    for a in state.assumptions:
                        if (a.proposed_by or "").lower() == target_agent.lower() and a.name == param:
                            orig_id = a.id or orig_id or f"asm_{target_agent.lower()}_{param}"
                            a.id = orig_id
                            a.revision_of = orig_id
                            a.revision_rationale = rebuttal.rationale
                            a.base = round(clamped_base, 4)
                            a.low = round(clamped_low, 4)
                            a.high = round(clamped_high, 4)

                    # Check if the revised range now overlaps with peer agents' ranges on the same parameter
                    peer_ranges = []
                    for f in state.findings:
                        if f.agent.lower() != target_agent.lower():
                            for a in f.assumptions:
                                if a.name == param:
                                    peer_ranges.append((f.agent, a.low, a.high))

                    if peer_ranges:
                        now_overlaps_all = all(
                            not (clamped_high < p_low or p_high < clamped_low)
                            for _, p_low, p_high in peer_ranges
                        )
                        if now_overlaps_all:
                            agents_involved = sorted([target_agent] + [p[0] for p in peer_ranges])
                            cid = generate_deterministic_conflict_id("non_overlapping_ranges", param, agents_involved)
                            converged_c = Conflict(
                                id=cid,
                                type="non_overlapping_ranges",
                                agents=agents_involved,
                                disputed_item=param,
                                status="resolved_converged",
                                resolution=f"Resolved via discussion: {target_agent} revised range to [{clamped_low:.4f}, {clamped_high:.4f}] based on skeptic critique ({rebuttal.rationale}). Ranges now converge.",
                                sides=[{"agent": target_agent, "base": clamped_base, "range": [clamped_low, clamped_high]}] + [
                                    {"agent": p[0], "range": [p[1], p[2]]} for p in peer_ranges
                                ]
                            )
                            state.conflicts.append(converged_c)

            rebuttals_logged.append(rebuttal)

        return {"status": "discussion_completed", "rebuttals_count": len(rebuttals_logged)}

    async def _run_conflict_resolution_task(self, task: Task, state: WorkflowState) -> Any:
        company_data = self.company_data or load_company_data()
        raw_conflicts = detect_all_conflicts(state.findings)
        reconciled = reconcile_assumptions(state.assumptions)
        baseline_params = reconciled.expected_params

        existing_converged = [c for c in state.conflicts if c.status == "resolved_converged"]
        existing_converged_ids = {c.id for c in existing_converged}

        resolved_conflicts = list(existing_converged)
        for c in raw_conflicts:
            if c.id in existing_converged_ids:
                continue
            await self.event_bus.emit(
                "conflict_detected",
                agent="supervisor",
                payload={"conflict_id": c.id, "type": c.type, "disputed_item": c.disputed_item}
            )
            res = resolve_conflict_via_simulation(
                conflict=c,
                findings=state.findings,
                company_data=company_data,
                baseline_params=baseline_params,
                decision=state.decision,
                state_simulation_runs=state.simulation_runs
            )
            resolved_conflicts.append(res)
        state.conflicts = resolved_conflicts
        return {"status": "resolved", "conflicts_count": len(resolved_conflicts)}

    async def _run_simulation_task(self, task: Task, state: WorkflowState) -> Any:
        company_data = self.company_data or load_company_data()
        reconciled = reconcile_assumptions(state.assumptions)
        
        # Select strategy set dynamically based on decision type
        dec_type = getattr(state.decision, "type", "free_plan")
        if dec_type == "price_increase":
            strategies = ["A_20pct_price_increase", "B_10pct_with_grandfathering", "C_status_quo_pricing"]
        elif dec_type == "enterprise_tier":
            strategies = ["A_enterprise_dedicated_sla", "B_self_serve_pro_tier", "C_status_quo"]
        elif dec_type == "churn_reduction":
            strategies = ["A_proactive_csm_program", "B_automated_health_scoring", "C_status_quo"]
        elif dec_type == "strategic_decision":
            strategies = ["A_adopt_proposal", "B_targeted_pilot", "C_status_quo"]
        else:
            strategies = ["A_limited_features", "B_usage_caps", "C_no_free_plan"]

        scenarios = [
            "conservative",
            "expected",
            "optimistic",
            "stress_infra_doubles",
            "stress_conversion_collapse",
            "stress_large_customer_churn"
        ]

        sim_runs = []
        for strat in strategies:
            for scen in scenarios:
                r = simulate(strat, scen, reconciled, company_data=company_data)
                sim_runs.append(r)
                await self.event_bus.emit(
                    "simulation_run",
                    agent="supervisor",
                    payload={"simulation_id": r.id, "strategy": strat, "scenario": scen}
                )

        state.simulation_runs = sim_runs

        # Dynamic strategy ranking, sensitivity, and flip point
        from report.decision_logic import rank_strategies, compute_dynamic_strategy_comparison
        ranked = rank_strategies(sim_runs, state.decision.constraints, company_data=company_data)
        comparison = compute_dynamic_strategy_comparison(ranked, reconciled, company_data)
        self.tornado_data = comparison["margin_tornado"]
        self.flip_point_info = comparison["flip_point"]

        # 500-sample multi-strategy Monte Carlo on shared parameter draws
        top_strat_name = ranked[0].strategy if (ranked and ranked[0].is_feasible) else (ranked[0].strategy if ranked else strategies[0])
        self.mc_summary = run_monte_carlo(top_strat_name, reconciled, company_data, n_samples=500, all_strategies=strategies)

        return {"status": "simulated", "runs_count": len(sim_runs)}

    async def _run_report_draft_task(self, task: Task, state: WorkflowState) -> Any:
        company_data = self.company_data or load_company_data()
        all_degraded = list(dict.fromkeys(state.degraded_agents + state.recovered_agents))
        draft_report = build_consolidated_report(
            decision=state.decision,
            sim_runs=state.simulation_runs,
            assumptions=state.assumptions,
            conflicts=state.conflicts,
            verification_results=[],
            tornado_data=getattr(self, "tornado_data", []),
            flip_point_info=getattr(self, "flip_point_info", {"has_flip_point": False}),
            mc_summary=getattr(self, "mc_summary", None),
            degraded_agents=all_degraded,
            company_data=company_data,
            findings=state.findings
        )
        state.draft_report = draft_report
        state.report = draft_report
        return {"status": "drafted", "recommendation": draft_report.recommendation}

    async def _run_verification_task(self, task: Task, state: WorkflowState) -> Any:
        company_data = self.company_data or load_company_data()
        loopback_rounds = 0
        all_passed = False
        results = []

        while loopback_rounds <= 2:
            current_target = state.draft_report or state.report
            if current_target is None:
                await self._run_report_draft_task(task, state)
                current_target = state.draft_report

            results = run_all_verification_checks(
                report=current_target,
                sim_runs=state.simulation_runs,
                assumptions=state.assumptions,
                company_data=company_data
            )
            state.verification_results = results
            all_passed = all(r.status == "passed" for r in results)

            if all_passed or loopback_rounds == 2:
                break

            loopback_rounds += 1
            state.verification_attempts = loopback_rounds
            state.round = min(state.max_rounds, state.round + 1)

            # Determine responsible task
            failed_checks = [r.check_name for r in results if r.status == "failed"]
            await self.event_bus.emit(
                "recovery_started",
                agent="supervisor",
                payload={"mode": "verification_loopback", "round": loopback_rounds, "failed_checks": failed_checks}
            )

            # If simulation issue, rerun simulation
            if any(c in ["number_registry_integrity", "report_traceability"] for c in failed_checks):
                sim_task = Task(id="task_simulation_engine", kind="simulation", owner_agent="supervisor", description="Rerun simulation")
                await self._run_simulation_task(sim_task, state)

            # Rerun report draft
            draft_task = Task(id="task_report_draft", kind="report_draft", owner_agent="supervisor", description="Rerun report draft")
            await self._run_report_draft_task(draft_task, state)

            await self.event_bus.emit(
                "recovery_done",
                agent="supervisor",
                payload={"mode": "verification_loopback_completed", "round": loopback_rounds}
            )

        evt_type = "verification_passed" if all_passed else "verification_failed"
        await self.event_bus.emit(
            evt_type,
            agent="skeptic",
            payload={"all_passed": all_passed, "results": [r.model_dump() for r in results], "loopback_rounds": loopback_rounds}
        )
        return {"status": "verified", "passed": all_passed, "loopback_rounds": loopback_rounds}

    async def _run_report_finalize_task(self, task: Task, state: WorkflowState) -> Any:
        import hashlib, json
        company_data = self.company_data or load_company_data()

        all_degraded = list(dict.fromkeys(state.degraded_agents + state.recovered_agents))
        final_report = build_consolidated_report(
            decision=state.decision,
            sim_runs=state.simulation_runs,
            assumptions=state.assumptions,
            conflicts=state.conflicts,
            verification_results=state.verification_results,
            tornado_data=getattr(self, "tornado_data", []),
            flip_point_info=getattr(self, "flip_point_info", {"has_flip_point": False}),
            mc_summary=getattr(self, "mc_summary", None),
            degraded_agents=all_degraded,
            company_data=company_data,
            findings=state.findings
        )

        all_passed = all(r.status == "passed" for r in state.verification_results)
        if not all_passed:
            final_report.confidence = "Low"
            final_report.disclaimers.append("Verification Alert: One or more automated data tie-out checks failed.")
            final_report.sections["verification_status"] = "degraded"
        else:
            final_report.sections["verification_status"] = "verified"

        # Compute verification hash
        sections_str = json.dumps(final_report.sections, sort_keys=True, default=str)
        verif_hash = f"sha256:{hashlib.sha256(sections_str.encode('utf-8')).hexdigest()}"
        final_report.sections["verification_hash"] = verif_hash

        state.report = final_report
        await self.event_bus.emit(
            "report_ready",
            agent="supervisor",
            payload={"decision_id": final_report.decision_id, "recommendation": final_report.recommendation, "verification_hash": verif_hash}
        )
        return {"status": "reported", "recommendation": final_report.recommendation, "verification_hash": verif_hash}

    async def _run_report_generation_task(self, task: Task, state: WorkflowState) -> Any:
        return await self._run_report_finalize_task(task, state)
