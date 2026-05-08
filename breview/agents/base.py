"""Base class for all agents in the review system."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ..models.agent_message import AgentMessage, AgentType, MessageType
from ..models.issue import Issue

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all review agents.

    Each agent:
    - Receives a task message from the orchestrator
    - Processes it (possibly calling LLM)
    - Returns a result message with issues found
    - Handles errors gracefully (never crashes the pipeline)
    """

    agent_type: AgentType
    name: str

    def __init__(self, config: Any):
        self.config = config
        self._token_usage = 0

    @abstractmethod
    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Execute the agent's task and return a result message.

        Args:
            message: Task message from orchestrator with payload

        Returns:
            Result message with issues found, or error message on failure
        """
        ...

    async def run(self, message: AgentMessage) -> AgentMessage:
        """Run the agent with error handling and timing.

        This is the entry point called by the orchestrator.
        Wraps execute() with timeout, error handling, and metrics.
        """
        start_time = time.monotonic()
        try:
            logger.info(f"[{self.name}] Starting execution")
            result = await asyncio.wait_for(self.execute(message), timeout=600)
            duration = time.monotonic() - start_time
            logger.info(f"[{self.name}] Completed in {duration:.1f}s, found {len(result.issues)} issues")
            return result
        except asyncio.TimeoutError:
            logger.error(f"[{self.name}] Timed out after 300s")
            return AgentMessage.create_error(self.agent_type, f"{self.name} timed out after 300s")
        except Exception as e:
            logger.error(f"[{self.name}] Failed: {e}", exc_info=True)
            return AgentMessage.create_error(self.agent_type, f"{self.name} failed: {str(e)}")

    @property
    def token_usage(self) -> int:
        """Total tokens used by this agent."""
        return self._token_usage
