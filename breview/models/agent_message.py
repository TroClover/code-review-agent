"""Agent communication message models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .issue import Issue


class AgentType(str, Enum):
    """Types of agents in the system."""

    ORCHESTRATOR = "orchestrator"
    STYLE = "style"
    CODE_REVIEW = "code_review"
    SAFETY = "safety"
    CONTEXT = "context"
    KNOWLEDGE = "knowledge"
    REPORT = "report"


class MessageType(str, Enum):
    """Types of messages between agents."""

    TASK = "task"  # Orchestrator → Agent: "do this work"
    RESULT = "result"  # Agent → Orchestrator: "here are my findings"
    CONTEXT_DATA = "context_data"  # Context Agent → review agents: shared context
    ERROR = "error"  # Agent → Orchestrator: "something went wrong"


class AgentMessage(BaseModel):
    """Message passed between agents in the pipeline."""

    message_id: str = Field(description="Unique message ID")
    message_type: MessageType
    source_agent: AgentType
    target_agent: AgentType
    payload: dict[str, Any] = Field(default_factory=dict, description="Message payload")
    issues: list[Issue] = Field(default_factory=list, description="Issues found (for result messages)")
    error: Optional[str] = Field(default=None, description="Error message (for error messages)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def create_task(cls, source: AgentType, target: AgentType, payload: dict[str, Any]) -> AgentMessage:
        """Create a task message from orchestrator to an agent."""
        import uuid

        return cls(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.TASK,
            source_agent=source,
            target_agent=target,
            payload=payload,
        )

    @classmethod
    def create_result(cls, source: AgentType, issues: list[Issue]) -> AgentMessage:
        """Create a result message from an agent back to orchestrator."""
        import uuid

        return cls(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.RESULT,
            source_agent=source,
            target_agent=AgentType.ORCHESTRATOR,
            issues=issues,
        )

    @classmethod
    def create_error(cls, source: AgentType, error: str) -> AgentMessage:
        """Create an error message from an agent back to orchestrator."""
        import uuid

        return cls(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.ERROR,
            source_agent=source,
            target_agent=AgentType.ORCHESTRATOR,
            error=error,
        )
