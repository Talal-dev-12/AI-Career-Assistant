"""
Base Agent
Member 1 — Integration Lead

All AI agents must inherit from BaseAgent and implement the `run` method.
This enforces a consistent interface the orchestrator can rely on.
"""

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Contract all AI agents must fulfil.

    Each agent is stateless — all context arrives via `payload` and
    all results are returned from `run`. Agents must not write to the
    database directly; they return structured data and the orchestrator
    or backend service handles persistence.
    """

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name, used in logs and tracing."""
        ...

    @abstractmethod
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the agent's primary task.

        Args:
            payload: Task-specific input data. Schema is defined per agent
                     in its own module docstring and integration contract.

        Returns:
            dict with at minimum:
                - "status": "success" | "partial" | "failed"
                - Agent-specific output keys (see each agent's contract)

        Raises:
            AgentError: On unrecoverable failure. The orchestrator catches
                        this and marks the TaskResult as failed.
        """
        ...

    async def validate_payload(self, payload: dict[str, Any], required_keys: list[str]) -> None:
        """Helper to assert required payload keys are present."""
        missing = [k for k in required_keys if k not in payload]
        if missing:
            raise AgentError(f"{self.agent_name} missing payload keys: {missing}")

    def log(self, level: str, msg: str, **kwargs) -> None:
        getattr(logger, level)("[%s] %s %s", self.agent_name, msg, kwargs or "")


class AgentError(Exception):
    """Raised when an agent cannot complete its task."""
    pass
