"""Review request and result models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .issue import Issue, Severity


class ReviewProfile(str, Enum):
    """Review profile determines review depth and thresholds.

    Configured per repository/branch, NOT per person.
    """

    STRICT = "strict"  # main/release branches: all checks, low thresholds
    STANDARD = "standard"  # feature branches (default): core checks, medium thresholds
    RELAXED = "relaxed"  # experimental/WIP branches: high-priority only, high thresholds


class PRInfo(BaseModel):
    """Information about a pull request."""

    repo_full_name: str = Field(description="Repository full name (owner/repo)")
    pr_number: int = Field(description="PR number")
    title: str = Field(description="PR title")
    description: str = Field(default="", description="PR description/body")
    author: str = Field(description="PR author username")
    profile: ReviewProfile = Field(default=ReviewProfile.STANDARD, description="Review profile based on branch")
    base_branch: str = Field(default="main", description="Target branch")
    head_branch: str = Field(description="Source branch")
    head_sha: str = Field(default="", description="Head commit SHA")
    changed_files: list[str] = Field(default_factory=list)
    additions: int = Field(default=0)
    deletions: int = Field(default=0)


class ReviewRequest(BaseModel):
    """A request to review code changes."""

    pr_info: PRInfo = Field(description="PR metadata")
    diff_content: str = Field(description="Raw git diff content")
    is_incremental: bool = Field(default=False, description="Whether this is a re-review of updated PR")
    agents_to_run: list[str] = Field(default_factory=list, description="Specific agents to invoke (empty = all)")
    skip_linter: bool = Field(default=False, description="Skip linter integration")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewResult(BaseModel):
    """Aggregated result from all agents."""

    request: ReviewRequest = Field(description="Original request")
    issues: list[Issue] = Field(default_factory=list)
    summary: str = Field(default="", description="Overall review summary")
    agents_executed: list[str] = Field(default_factory=list)
    agents_skipped: list[str] = Field(default_factory=list)
    agents_failed: list[str] = Field(default_factory=list)
    duration_seconds: float = Field(default=0.0)
    total_tokens_used: int = Field(default=0)
    is_approved: bool = Field(default=False, description="Whether the PR passes review")
    blocking_issues_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def critical_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.CRITICAL]

    @property
    def major_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.MAJOR]

    @property
    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.severity.value] = counts.get(issue.severity.value, 0) + 1
        return counts
