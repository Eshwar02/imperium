"""Base agent contract. All sub-agents implement `run`."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Shared per-run context handed to every sub-agent."""
    repository_id: str
    repo_path: str
    rkb: Any = None                       # RKB facade handle
    scratch: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    name: str = "base"
    role: str = ""  # llm/routing.py key; subclasses set their assigned role

    @abstractmethod
    def run(self, ctx: AgentContext) -> dict:
        """Do the agent's work; return a structured result merged by the orchestrator."""
        raise NotImplementedError
