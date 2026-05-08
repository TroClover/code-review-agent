"""Knowledge entry models for the knowledge base."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeType(str, Enum):
    """Types of knowledge entries."""

    CODING_STANDARD = "coding_standard"  # Team-wide coding standard
    ISSUE_PATTERN = "issue_pattern"  # Pattern extracted from repeated issues
    BEST_PRACTICE = "best_practice"  # Positive pattern from good code
    PERSONAL_GAP = "personal_gap"  # Individual developer weakness


class KnowledgeGranularity(str, Enum):
    """Granularity level of knowledge."""

    TEAM = "team"  # Applies to entire team
    PERSONAL = "personal"  # Applies to specific developer
    ISSUE_TYPE = "issue_type"  # Applies to specific issue category


class CodeExample(BaseModel):
    """A code example (good or bad) for a knowledge entry."""

    language: str = Field(description="Programming language: python, cpp")
    code: str = Field(description="Code snippet")
    is_good: bool = Field(description="True = good example, False = bad example")
    explanation: Optional[str] = Field(default=None, description="Why this is good/bad")


class KnowledgeEntry(BaseModel):
    """A single knowledge entry in the knowledge base."""

    id: str = Field(description="Unique knowledge ID")
    title: str = Field(description="Short title")
    description: str = Field(description="Detailed description of the knowledge")
    knowledge_type: KnowledgeType
    granularity: KnowledgeGranularity
    category: str = Field(description="Category: naming, error_handling, performance, security, safety, etc.")
    severity: str = Field(default="major", description="Default severity when this rule is violated")
    examples: list[CodeExample] = Field(default_factory=list)
    applicable_to: list[str] = Field(default_factory=list, description="Applicable file patterns or roles")
    source: str = Field(description="Where this knowledge came from: agent_review, human_comment, manual")
    source_weight: float = Field(default=1.0, ge=0.0, le=2.0, description="Weight: human=2.0, agent=1.0")
    trigger_count: int = Field(default=0, description="How many times this pattern was observed")
    target_developer: Optional[str] = Field(default=None, description="For personal granularity: developer username")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
