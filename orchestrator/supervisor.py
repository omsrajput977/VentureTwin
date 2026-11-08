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
from conflict.detector import detect_all_conflicts
from conflict.resolver import resolve_conflict_via_simulation
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
        self.injected_failures: Dict[str, str] = {}
        self.tornado_data: List[Dict[str, Any]] = []
        self.flip_point_info: Dict[str, Any] = {}
        self.mc_summary: Dict[str, Any] = {}

    def inject_failure(self, agent_name: str, mode: str, persist: bool = False, fail_attempts: int = 3) -> None:
        """Inject a mid-run failure: 'timeout', 'exception', or 'bad_output'"""
        key = f"persistent_{mode}" if persist else mode
        self.injected_failures[agent_name.lower()] = key

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
            state.status = "completed" if not state.degraded_agents else "degraded"

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
            payload={"task_id": task.id}
        )

        injected = self.injected_failures.get(agent_name)
        is_persistent = injected is not None and "persistent" in injected
        if not is_persistent and agent_name in self.injected_failures:
            del self.injected_failures[agent_name]

        max_attempts = task.max_attempts

        for attempt in range(1, max_attempts + 1):
            task.attempts = attempt
            fail_mode = injected
            if fail_mode and "persistent_" in fail_mode:
                fail_mode = fail_mode.replace("persistent_", "")
            current_injected = fail_mode if (is_persistent or attempt == 1) else None

            try:
                if agent is not None and task.id not in [
                    "task_workflow_verification"
                ]:
                    context = {"findings": state.findings, "state": state, "decision": state.decision}
                    finding = await agent.run(
                        task,
                        context=context,
                        llm_client=self.llm_client,
                        injected_failure=current_injected
                    )
                    state.add_finding(finding)
                    await self.event_bus.emit(
                        "finding_posted",
                        agent=agent_name,
                        payload={"task_id": task.id, "finding": finding.model_dump()}
                    )
                    return finding
                else:
                    return await self._run_builtin_supervisor_task(task, state)

            except Exception as e:
                logger.warning(f"Task {task.id} (agent {agent_name}) attempt {attempt} failed: {e}")
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
                    await asyncio.sleep(0.05 * attempt)
                    await self.event_bus.emit(
                        "recovery_done",
                        agent=agent_name,
                        payload={"task_id": task.id, "mode": "retry_ready"}
                    )
                else:
                    if task.kind == "core_analysis":
                        logger.error(f"Core analysis task {task.id} failed terminally after {max_attempts} attempts.")
                        state.mark_task_failed(task.id, str(e))
                        state.status = "failed"
                        raise RuntimeError(f"Core analysis task {task.id} failed terminally: {e}")

                    # Non-core task: first invoke Backup Analyst
                    state.degraded_agents.append(agent_name)
                    await self.event_bus.emit(
                        "recovery_started",
                        agent=agent_name,
                        payload={"task_id": task.id, "mode": "backup_analyst"}
                    )
                    try:
                        from agents.backup_agent import BackupAnalyst
                        backup = BackupAnalyst()
                        backup_finding = await backup.run_backup(task, state, self.llm_client)
                        state.add_finding(backup_finding)
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
                        fallback_finding = self._generate_fallback_finding(task, agent_name)
                        state.add_finding(fallback_finding)
                        await self.event_bus.emit(
                            "recovery_done",
                            agent=agent_name,
                            payload={"task_id": task.id, "mode": "degraded_completed"}
                        )
                        return fallback_finding

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
                    source_ref=None
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
        company_data = self.company_data or load_company_data()

        # Step: Discussion & Rebuttal Node
        if task.id == "task_agent_discussion":
            rebuttals_logged = []
            for chal in state.skeptic_challenges:
                target_agent = chal.get("agent", "")
                param = chal.get("assumption", "")
                concern = chal.get("challenge", "")

                prompt = (
                    f"Agent: {target_agent}\n"
                    f"Parameter Challenged: {param}\n"
                    f"Skeptic Critique: {concern}\n"
                    "Respond with a structured rebuttal: choose 'concede', 'defend', or 'compromise'. "
                    "Provide updated parameter bounds if conceding or compromising."
                )

                from agents.llm_client import llm_call
                from state.schemas import Rebuttal, Message
                rebuttal: Rebuttal = await llm_call(
                    prompt=prompt,
                    response_model=Rebuttal,
                    system_prompt=f"You are {target_agent}. Provide a bounded professional defense or concession to the Skeptic.",
                    client=self.llm_client
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
                    for f in state.findings:
                        if f.agent.lower() == target_agent.lower():
                            for a in f.assumptions:
                                if a.name == param:
                                    a.base = rebuttal.updated_base
                                    if rebuttal.updated_low is not None:
                                        a.low = rebuttal.updated_low
                                    if rebuttal.updated_high is not None:
                                        a.high = rebuttal.updated_high
                    for a in state.assumptions:
                        if a.proposed_by.lower() == target_agent.lower() and a.name == param:
                            a.base = rebuttal.updated_base
                            if rebuttal.updated_low is not None:
                                a.low = rebuttal.updated_low
                            if rebuttal.updated_high is not None:
                                a.high = rebuttal.updated_high

                rebuttals_logged.append(rebuttal)

            return {"status": "discussion_completed", "rebuttals_count": len(rebuttals_logged)}

        # Step 7: Conflict Resolution
        elif task.id == "task_conflict_resolution":
            raw_conflicts = detect_all_conflicts(state.findings)
            reconciled = reconcile_assumptions(state.assumptions)
            baseline_params = reconciled.expected_params

            resolved_conflicts = []
            for c in raw_conflicts:
                await self.event_bus.emit(
                    "conflict_detected",
                    agent="supervisor",
                    payload={"conflict_id": c.id, "type": c.type, "disputed_item": c.disputed_item}
                )
                res = resolve_conflict_via_simulation(
                    c,
                    state.findings,
                    company_data=company_data,
                    baseline_params=baseline_params
                )
                resolved_conflicts.append(res)
            state.conflicts = resolved_conflicts
            return {"status": "resolved", "conflicts_count": len(resolved_conflicts)}

        # Step 6: Simulation Engine
        elif task.id == "task_simulation_engine":
            reconciled = reconcile_assumptions(state.assumptions)
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

            # Compute sensitivity, Monte Carlo, and flip point
            self.tornado_data = run_sensitivity_analysis("B_usage_caps", reconciled, company_data)
            self.flip_point_info = find_flip_point(
                "B_usage_caps", "C_no_free_plan", "free_to_paid_conversion", reconciled, company_data
            )
            self.mc_summary = run_monte_carlo("B_usage_caps", reconciled, company_data, n_samples=300)

            return {"status": "simulated", "runs_count": len(sim_runs)}

        # Step 9: Verification Layer
        elif task.id == "task_workflow_verification":
            loopback_rounds = 0
            all_passed = False
            results = []

            while loopback_rounds <= 2:
                tentative_report = build_consolidated_report(
                    decision=state.decision,
                    sim_runs=state.simulation_runs,
                    assumptions=state.assumptions,
                    conflicts=state.conflicts,
                    verification_results=[],
                    tornado_data=self.tornado_data,
                    flip_point_info=self.flip_point_info,
                    mc_summary=self.mc_summary,
                    degraded_agents=state.degraded_agents,
                    company_data=company_data
                )

                results = run_all_verification_checks(
                    report=tentative_report,
                    sim_runs=state.simulation_runs,
                    assumptions=state.assumptions,
                    company_data=company_data
                )
                state.verification_results = results

                all_passed = all(r.status == "passed" for r in results)
                if all_passed or loopback_rounds == 2:
                    break

                loopback_rounds += 1
                state.round = min(state.max_rounds, state.round + 1)
                await self.event_bus.emit(
                    "recovery_started",
                    agent="supervisor",
                    payload={"mode": "verification_loopback", "round": loopback_rounds}
                )
                reconciled = reconcile_assumptions(state.assumptions)
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
            return {"status": "verified", "passed": all_passed}

        # Step 10: Consolidated Report Generation
        elif task.id == "task_report_generation":
            final_report = build_consolidated_report(
                decision=state.decision,
                sim_runs=state.simulation_runs,
                assumptions=state.assumptions,
                conflicts=state.conflicts,
                verification_results=state.verification_results,
                tornado_data=self.tornado_data,
                flip_point_info=self.flip_point_info,
                mc_summary=self.mc_summary,
                degraded_agents=state.degraded_agents,
                company_data=company_data
            )
            if not all(r.status == "passed" for r in state.verification_results):
                final_report.confidence = "Low"
                final_report.disclaimers.append("Verification Alert: One or more automated data tie-out checks failed.")

            state.report = final_report
            state.report = final_report
            await self.event_bus.emit(
                "report_ready",
                agent="supervisor",
                payload={"decision_id": final_report.decision_id, "recommendation": final_report.recommendation}
            )
            return {"status": "reported", "recommendation": final_report.recommendation}

        return {"status": "ok"}
