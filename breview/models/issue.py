"""Issue and severity models for review findings."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for review issues."""

    CRITICAL = "critical"  # Must fix: security vulnerabilities, crashes, data corruption
    MAJOR = "major"  # Should fix: logic errors, performance issues, anti-patterns
    MINOR = "minor"  # Consider fixing: style issues, minor improvements
    INFO = "info"  # Suggestions: best practices, alternative approaches


class IssueLocation(BaseModel):
    """Location of an issue in the codebase."""

    file_path: str = Field(description="Relative path to the file")
    line_start: int = Field(description="Starting line number")
    line_end: Optional[int] = Field(default=None, description="Ending line number (for ranges)")
    function_name: Optional[str] = Field(default=None, description="Function/method containing the issue")
    class_name: Optional[str] = Field(default=None, description="Class containing the issue")


class Issue(BaseModel):
    """A single review issue found by an agent."""

    id: str = Field(description="Unique issue identifier")
    title: str = Field(description="Short title of the issue")
    description: str = Field(description="Detailed description of the problem")
    severity: Severity = Field(description="Severity level")
    category: str = Field(description="Issue category: style, logic, security, performance, safety")
    location: IssueLocation = Field(description="Where the issue was found")
    suggestion: Optional[str] = Field(default=None, description="Suggested fix")
    code_snippet: Optional[str] = Field(default=None, description="Relevant code snippet")
    knowledge_ids: list[str] = Field(default_factory=list, description="Related knowledge entry IDs")
    source_agent: str = Field(description="Which agent found this issue")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score 0-1")

    def to_comment_body(self) -> str:
        """Format issue as a GitHub PR comment."""
        severity_emoji = {
            Severity.CRITICAL: ":rotating_light:",
            Severity.MAJOR: ":warning:",
            Severity.MINOR: ":bulb:",
            Severity.INFO: ":information_source:",
        }
        lines = [
            f"{severity_emoji.get(self.severity, '')} **[{self.severity.value.upper()}]** {self.title}",
            "",
            self.description,
        ]
        if self.suggestion:
            lines.extend(["", "**Suggested fix:**", self.suggestion])
        if self.knowledge_ids:
            knowledge_links = ", ".join(f"[KB-{kid}]" for kid in self.knowledge_ids)
            lines.extend(["", f"📚 Related knowledge: {knowledge_links}"])
        return "\n".join(lines)
