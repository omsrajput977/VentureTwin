import pytest
from orchestrator.parser import parse_decision_query
from orchestrator.dag import TaskDAG, DAGCycleError, DAGValidationError
from orchestrator.decomposer import decompose_decision
from state.schemas import Task

def test_parse_decision_queries():
    # Free plan query
    d1 = parse_decision_query("Should we launch a free plan?")
    assert d1.type == "free_plan"
    assert "runway" in d1.objective.lower()

    # Price change query
    d2 = parse_decision_query("What if we raise price by 15%?")
    assert d2.type == "price_change"

    # Unsupported query
    d3 = parse_decision_query("Should we rewrite our backend in Rust?")
    assert d3.type == "unsupported"
    assert "Unsupported decision type" in d3.objective
    assert "free_plan" in d3.objective

def test_decompose_free_plan_dag():
    decision = parse_decision_query("Should we launch a free tier for NimbusDesk?")
    dag = decompose_decision(decision)
    assert dag.validate() is True

    # Check parallel roots (tasks with no dependencies)
    roots = dag.get_ready_tasks(completed_ids=set(), active_ids=set())
    root_ids = {t.id for t in roots}
    assert "task_cfo_analysis" in root_ids
    assert "task_growth_analysis" in root_ids
    assert "task_cto_analysis" in root_ids
    assert "task_customer_analysis" in root_ids
    assert "task_product_analysis" in root_ids
    assert len(roots) == 5

    # Skeptic audit should not be ready initially
    assert "task_skeptic_audit" not in root_ids

    # Simulate completed roots
    ready_after_roots = dag.get_ready_tasks(completed_ids=root_ids, active_ids=set())
    assert len(ready_after_roots) == 1
    assert ready_after_roots[0].id == "task_skeptic_audit"

def test_dag_cycle_detection():
    dag = TaskDAG()
    t1 = Task(id="t1", owner_agent="a", depends_on=["t2"])
    t2 = Task(id="t2", owner_agent="b", depends_on=["t3"])
    t3 = Task(id="t3", owner_agent="c", depends_on=["t1"])  # Cycle t1 -> t2 -> t3 -> t1
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)

    with pytest.raises(DAGCycleError):
        dag.validate()

def test_dag_missing_dependency():
    dag = TaskDAG()
    t1 = Task(id="t1", owner_agent="a", depends_on=["missing_task"])
    dag.add_task(t1)

    with pytest.raises(DAGValidationError):
        dag.validate()
