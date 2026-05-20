"""GitHub commit status management."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CommitStatusManager:
    """Manages GitHub commit statuses for review results."""

    def __init__(self, github_client: Any = None):
        self.github_client = github_client

    def set_status(
        self,
        repo: str,
        sha: str,
        state: str,
        description: str = "",
        context: str = "breview/code-review",
    ) -> bool:
        """Set a commit status on GitHub.

        Args:
            repo: Repository full name (owner/repo)
            sha: Commit SHA
            state: Status state (pending, success, failure, error)
            description: Short description
            context: Status context (default: breview/code-review)

        Returns:
            True if successful
        """
        if not self.github_client:
            logger.warning("No GitHub client configured, skipping status update")
            return False

        try:
            self.github_client.repos(repo).statuses(sha).create(
                state=state,
                description=description[:140],  # GitHub limit
                context=context,
            )
            logger.info(f"Set commit status: {state} for {sha[:8]}")
            return True
        except Exception as e:
            logger.error(f"Failed to set commit status: {e}")
            return False

    def set_pending(self, repo: str, sha: str) -> bool:
        """Set pending status."""
        return self.set_status(repo, sha, "pending", "Review in progress...")

    def set_success(self, repo: str, sha: str, issue_count: int = 0) -> bool:
        """Set success status."""
        desc = f"Review passed ({issue_count} issue(s))" if issue_count else "Review passed"
        return self.set_status(repo, sha, "success", desc)

    def set_failure(self, repo: str, sha: str, critical_count: int = 0) -> bool:
        """Set failure status."""
        desc = f"Review failed ({critical_count} critical issue(s))" if critical_count else "Review failed"
        return self.set_status(repo, sha, "failure", desc)
