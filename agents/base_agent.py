import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, List
from state.schemas import Finding, Task, Assumption, Evidence
from agents.llm_client import LLMClient, llm_call

logger = logging.getLogger(__name__)

class AgentExecutionError(Exception):
    pass

class BaseAgent:
    def __init__(
        self,
        name: str,
        role: str,
        objective: str,
        system_prompt: str,
        tools: Optional[Dict[str, Callable]] = None,
        timeout_seconds: float = 30.0
    ):
        self.name = name
        self.role = role
        self.objective = objective
        self.system_prompt = system_prompt
        self.tools = tools or {}
        self.timeout_seconds = timeout_seconds
        self.last_heartbeat: float = time.time()
        self.is_degraded: bool = False

    def heartbeat(self) -> float:
        self.last_heartbeat = time.time()
        return self.last_heartbeat

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        if tool_name not in self.tools:
            raise ValueError(f"Agent {self.name} has no access to tool '{tool_name}'")
        func = self.tools[tool_name]
        if asyncio.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)

    async def run(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None,
        injected_failure: Optional[Any] = None
    ) -> Finding:
        """
        Executes the agent's task within timeout and validates the structured Finding output.
        """
        self.heartbeat()

        # Handle failure injection for resilience testing
        should_fail = False
        fail_mode = None
        if isinstance(injected_failure, dict):
            fail_mode = injected_failure.get("mode")
            persist = injected_failure.get("persist", False)
            fail_attempts = injected_failure.get("fail_attempts", 1)
            attempts_done = injected_failure.get("attempts_done", 0)
            if persist or attempts_done < fail_attempts:
                should_fail = True
                injected_failure["attempts_done"] = attempts_done + 1
        elif isinstance(injected_failure, str):
            fail_mode = injected_failure.replace("persistent_", "")
            should_fail = True

        if should_fail and fail_mode:
            if fail_mode == "timeout":
                raise asyncio.TimeoutError(f"Agent {self.name} timed out due to injected failure")
            elif fail_mode == "exception":
                raise AgentExecutionError(f"Agent {self.name} crashed with injected exception")
            elif fail_mode == "bad_output":
                raise ValueError(f"Injected bad output schema for {self.name}")

        try:
            finding = await asyncio.wait_for(
                self._execute_core(task, context, llm_client),
                timeout=self.timeout_seconds
            )
            # Ensure finding is validated against Pydantic schema
            if not isinstance(finding, Finding):
                finding = Finding.model_validate(finding)
            return finding
        except asyncio.TimeoutError:
            logger.error(f"Agent {self.name} timed out on task {task.id}")
            raise
        except Exception as e:
            logger.error(f"Agent {self.name} failed execution: {e}")
            raise

    async def _execute_core(
        self,
        task: Task,
        context: Dict[str, Any],
        llm_client: Optional[LLMClient] = None
    ) -> Finding:
        """
        Specialist agents implement this method to gather evidence from tools
        and generate structured assumptions and recommendations.
        """
        raise NotImplementedError("Subclasses must implement _execute_core")

