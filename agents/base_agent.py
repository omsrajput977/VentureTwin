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
        injected_failure: Optional[str] = None
    ) -> Finding:
        """
        Executes the agent's task within timeout and validates the structured Finding output.
        """
        self.heartbeat()

        # Handle failure injection for resilience testing
        if injected_failure == "timeout":
            raise asyncio.TimeoutError(f"Agent {self.name} timed out due to injected failure")
        elif injected_failure == "exception":
            raise AgentExecutionError(f"Agent {self.name} crashed with injected exception")
        elif injected_failure == "bad_output":
            # Returns an invalid dictionary or raises validation error
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

