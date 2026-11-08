from typing import Dict, List, Set, Optional, Any
from state.schemas import Task

class DAGValidationError(Exception):
    pass

class DAGCycleError(DAGValidationError):
    pass

class TaskDAG:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}

    def add_task(self, task: Task) -> None:
        self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def validate(self) -> bool:
        """
        Validates that:
        1. All task dependencies reference existing tasks in the DAG.
        2. There are no directed cycles.
        """
        # 1. Dependency existence check
        for t_id, task in self.tasks.items():
            for dep in task.depends_on:
                if dep not in self.tasks:
                    raise DAGValidationError(f"Task '{t_id}' depends on nonexistent task '{dep}'")

        # 2. Cycle detection via DFS (3-color state: 0=unvisited, 1=visiting, 2=visited)
        visited_state: Dict[str, int] = {t_id: 0 for t_id in self.tasks}

        def dfs(node_id: str, path: List[str]):
            visited_state[node_id] = 1  # visiting
            path.append(node_id)

            task = self.tasks[node_id]
            for dep in task.depends_on:
                if visited_state[dep] == 1:
                    cycle = " -> ".join(path + [dep])
                    raise DAGCycleError(f"Cycle detected in task DAG: {cycle}")
                if visited_state[dep] == 0:
                    dfs(dep, path)

            path.pop()
            visited_state[node_id] = 2  # visited

        for node in self.tasks:
            if visited_state[node] == 0:
                dfs(node, [])

        return True

    def get_ready_tasks(self, completed_ids: Set[str], active_ids: Set[str]) -> List[Task]:
        """
        Returns all tasks whose dependencies are completed and are not already completed/active.
        """
        ready = []
        for t_id, task in self.tasks.items():
            if t_id in completed_ids or t_id in active_ids:
                continue
            if all(dep in completed_ids for dep in task.depends_on):
                ready.append(task)
        return ready

    def is_complete(self, completed_ids: Set[str]) -> bool:
        return len(self.tasks) > 0 and all(t_id in completed_ids for t_id in self.tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            t_id: {
                "id": t.id,
                "owner_agent": t.owner_agent,
                "depends_on": t.depends_on,
                "status": t.status
            }
            for t_id, t in self.tasks.items()
        }
