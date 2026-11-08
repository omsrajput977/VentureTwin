from state.schemas import Decision, Task
from orchestrator.dag import TaskDAG, DAGValidationError

def decompose_decision(decision: Decision) -> TaskDAG:
    dag = TaskDAG()

    if decision.type == "unsupported":
        raise DAGValidationError(f"Cannot decompose unsupported decision type: {decision.question}")

    if decision.type == "free_plan":
        # 1. Parallel specialist analysis tasks
        analysis_tasks = [
            Task(id="task_cfo_analysis", owner_agent="cfo", depends_on=[]),
            Task(id="task_growth_analysis", owner_agent="growth", depends_on=[]),
            Task(id="task_cto_analysis", owner_agent="cto", depends_on=[]),
            Task(id="task_customer_analysis", owner_agent="customer", depends_on=[]),
            Task(id="task_product_analysis", owner_agent="product", depends_on=[])
        ]
        for t in analysis_tasks:
            dag.add_task(t)

        analysis_ids = [t.id for t in analysis_tasks]

        # 2. Skeptic Audit (depends on all analysis tasks)
        dag.add_task(Task(
            id="task_skeptic_audit",
            owner_agent="skeptic",
            depends_on=analysis_ids
        ))

        # 3. Conflict Detection and Simulation Resolution
        dag.add_task(Task(
            id="task_conflict_resolution",
            owner_agent="supervisor",
            depends_on=["task_skeptic_audit"]
        ))

        # 4. Scenario Simulation Engine
        dag.add_task(Task(
            id="task_simulation_engine",
            owner_agent="supervisor",
            depends_on=["task_conflict_resolution"]
        ))

        # 5. Workflow Verification Layer
        dag.add_task(Task(
            id="task_workflow_verification",
            owner_agent="skeptic",
            depends_on=["task_simulation_engine"]
        ))

        # 6. Consolidated Report Generation
        dag.add_task(Task(
            id="task_report_generation",
            owner_agent="supervisor",
            depends_on=["task_workflow_verification"]
        ))

    elif decision.type == "price_change":
        # Price change specialist tasks
        analysis_tasks = [
            Task(id="task_cfo_analysis", owner_agent="cfo", depends_on=[]),
            Task(id="task_growth_analysis", owner_agent="growth", depends_on=[]),
            Task(id="task_customer_analysis", owner_agent="customer", depends_on=[])
        ]
        for t in analysis_tasks:
            dag.add_task(t)

        analysis_ids = [t.id for t in analysis_tasks]

        dag.add_task(Task(
            id="task_skeptic_audit",
            owner_agent="skeptic",
            depends_on=analysis_ids
        ))
        dag.add_task(Task(
            id="task_conflict_resolution",
            owner_agent="supervisor",
            depends_on=["task_skeptic_audit"]
        ))
        dag.add_task(Task(
            id="task_simulation_engine",
            owner_agent="supervisor",
            depends_on=["task_conflict_resolution"]
        ))
        dag.add_task(Task(
            id="task_workflow_verification",
            owner_agent="skeptic",
            depends_on=["task_simulation_engine"]
        ))
        dag.add_task(Task(
            id="task_report_generation",
            owner_agent="supervisor",
            depends_on=["task_workflow_verification"]
        ))

    # Validate DAG integrity
    dag.validate()
    return dag
