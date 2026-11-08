from typing import Dict, Any, Optional, List
from agents.base_agent import BaseAgent
from agents.specialists import (
    CFOAgent,
    GrowthAgent,
    CTOAgent,
    CustomerAgent,
    ProductAgent,
    SkepticAgent
)

class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {
            "cfo": CFOAgent(),
            "growth": GrowthAgent(),
            "cto": CTOAgent(),
            "customer": CustomerAgent(),
            "product": ProductAgent(),
            "skeptic": SkepticAgent()
        }
        
        # Placeholder / Extensible agents (not built in 10-day MVP, as specified in prompt)
        self._extensible_agents: Dict[str, Dict[str, str]] = {
            "ops": {
                "role": "VP Operations",
                "status": "planned",
                "description": "Internal process workflows and tooling efficiency"
            },
            "market": {
                "role": "Market Intelligence Lead",
                "status": "planned",
                "description": "Competitor pricing telemetry and macro sector trends"
            },
            "risk": {
                "role": "Chief Risk Officer",
                "status": "planned",
                "description": "Regulatory, compliance, and enterprise contract terms"
            }
        }

    def get(self, name: str) -> Optional[BaseAgent]:
        key = name.lower()
        return self._agents.get(key)

    def list_available(self) -> List[str]:
        return list(self._agents.keys())

    def list_registered(self) -> Dict[str, Any]:
        result = {}
        for k, a in self._agents.items():
            result[k] = {
                "name": a.name,
                "role": a.role,
                "objective": a.objective,
                "status": "implemented"
            }
        for k, info in self._extensible_agents.items():
            result[k] = info
        return result

default_registry = AgentRegistry()

