"""Incremental review support - only re-review changed files."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IncrementalReviewManager:
    """Manages incremental reviews for PR updates."""

    def __init__(self, github_client: Any = None):
        self.github_client = github_client
        self._last_review_sha: dict[str, str] = {}  # pr_key -> sha

    def should_re_review(
        self,
        repo: str,
        pr_number: int,
        current_sha: str,
    ) -> bool:
        """Check if a re-review is needed.

        Args:
            repo: Repository full name
            pr_number: PR number
            current_sha: Current head SHA

        Returns:
            True if re-review is needed
        """
        pr_key = f"{repo}#{pr_number}"
        last_sha = self._last_review_sha.get(pr_key)

        if last_sha is None:
            return True  # Never reviewed

        return last_sha != current_sha

    def get_changed_files_since_last_review(
        self,
        repo: str,
        pr_number: int,
        current_sha: str,
    ) -> Optional[list[str]]:
        """Get files changed since last review.

        Args:
            repo: Repository full name
            pr_number: PR number
            current_sha: Current head SHA

        Returns:
            List of changed file paths, or None if full review needed
        """
        pr_key = f"{repo}#{pr_number}"
        last_sha = self._last_review_sha.get(pr_key)

        if last_sha is None or not self.github_client:
            return None  # Full review needed

        try:
            # Get comparison between last reviewed SHA and current
            comparison = self.github_client.repos(repo).compare(
                f"{last_sha}...{current_sha}"
            )
            return [f.filename for f in comparison.files]
        except Exception as e:
            logger.warning(f"Failed to get changed files: {e}")
            return None

    def record_review(self, repo: str, pr_number: int, sha: str) -> None:
        """Record that a review was completed for a PR."""
        pr_key = f"{repo}#{pr_number}"
        self._last_review_sha[pr_key] = sha
        logger.info(f"Recorded review for {pr_key} at {sha[:8]}")
