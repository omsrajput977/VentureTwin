from state.schemas import Decision, Task
from orchestrator.dag import TaskDAG, DAGValidationError

def decompose_decision(decision: Decision) -> TaskDAG:
    dag = TaskDAG()

    if decision.type != "free_plan":
        raise DAGValidationError(
            f"VentureTwin v0.1 MVP specializes in Freemium / Free Plan packaging decisions. "
            f"Price change elasticity modeling is planned for v0.2 roadmap. (Query: {decision.question})"
        )

    # 1. Parallel specialist analysis tasks
    analysis_tasks = [
        Task(id="task_cfo_analysis", owner_agent="cfo", depends_on=[], kind="core_analysis"),
        Task(id="task_growth_analysis", owner_agent="growth", depends_on=[], kind="core_analysis"),
        Task(id="task_cto_analysis", owner_agent="cto", depends_on=[], kind="specialist_analysis"),
        Task(id="task_customer_analysis", owner_agent="customer", depends_on=[], kind="specialist_analysis"),
        Task(id="task_product_analysis", owner_agent="product", depends_on=[], kind="specialist_analysis")
    ]
    for t in analysis_tasks:
        dag.add_task(t)

    analysis_ids = [t.id for t in analysis_tasks]

    # 2. Skeptic Audit (depends on all analysis tasks)
    dag.add_task(Task(
        id="task_skeptic_audit",
        owner_agent="skeptic",
        depends_on=analysis_ids,
        kind="agent_critique"
    ))

    # 3. Agent Discussion & Rebuttal Node (bounded 1-round peer challenge)
    dag.add_task(Task(
        id="task_agent_discussion",
        owner_agent="supervisor",
        depends_on=["task_skeptic_audit"],
        kind="agent_discussion"
    ))

    # 4. Conflict Detection and Simulation Resolution
    dag.add_task(Task(
        id="task_conflict_resolution",
        owner_agent="supervisor",
        depends_on=["task_agent_discussion"],
        kind="supervisor_coordination"
    ))

    # 5. Scenario Simulation Engine
    dag.add_task(Task(
        id="task_simulation_engine",
        owner_agent="supervisor",
        depends_on=["task_conflict_resolution"],
        kind="supervisor_coordination"
    ))

    # 6. Workflow Verification Layer
    dag.add_task(Task(
        id="task_workflow_verification",
        owner_agent="skeptic",
        depends_on=["task_simulation_engine"],
        kind="agent_critique"
    ))

    # 7. Consolidated Report Generation
    dag.add_task(Task(
        id="task_report_generation",
        owner_agent="supervisor",
        depends_on=["task_workflow_verification"],
        kind="supervisor_coordination"
    ))

    # Validate DAG integrity
    dag.validate()
    return dag

    # Validate DAG integrity
    dag.validate()
    return dag

