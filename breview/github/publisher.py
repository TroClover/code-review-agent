"""GitHub review publisher - publishes review results to PRs."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


class ReviewPublisher:
    """Publishes review results to GitHub PRs.

    Uses GitHub API directly with GITHUB_TOKEN (for GitHub Actions)
    or GitHub App authentication.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")

    async def publish_review(
        self,
        repo: str,
        pr_number: int,
        sha: str,
        summary: str,
        issues: list[dict[str, Any]],
        is_approved: bool,
    ) -> bool:
        """Publish a review to a GitHub PR.

        Args:
            repo: Repository full name (owner/repo)
            pr_number: PR number
            sha: Commit SHA
            summary: Review summary text
            issues: List of issue dicts
            is_approved: Whether the review passes

        Returns:
            True if successful
        """
        if not self.token:
            logger.error("No GitHub token available")
            return False

        # Build inline comments
        comments = self._build_comments(issues)

        # Determine review event
        event = "APPROVE" if is_approved else "COMMENT"

        # Build review body
        body = self._build_review_body(summary, issues)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/reviews",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json",
                    },
                    json={
                        "body": body,
                        "event": event,
                        "commit_id": sha,
                        "comments": comments,
                    },
                )
                response.raise_for_status()
                logger.info(f"Published review to {repo}#{pr_number}")
                return True
        except Exception as e:
            logger.error(f"Failed to publish review: {e}")
            return False

    async def set_status(
        self,
        repo: str,
        sha: str,
        state: str,
        description: str = "",
        context: str = "breview/code-review",
    ) -> bool:
        """Set commit status.

        Args:
            repo: Repository full name
            sha: Commit SHA
            state: Status state (pending, success, failure, error)
            description: Status description
            context: Status context

        Returns:
            True if successful
        """
        if not self.token:
            logger.error("No GitHub token available")
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GITHUB_API_URL}/repos/{repo}/statuses/{sha}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json",
                    },
                    json={
                        "state": state,
                        "description": description[:140],
                        "context": context,
                    },
                )
                response.raise_for_status()
                logger.info(f"Set commit status: {state} for {sha[:8]}")
                return True
        except Exception as e:
            logger.error(f"Failed to set commit status: {e}")
            return False

    def _build_comments(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build inline comments for the review."""
        comments = []
        for issue in issues:
            file_path = issue.get("file_path", "")
            line = issue.get("line", 1)
            severity = issue.get("severity", "info")

            # Skip if no file path
            if not file_path:
                continue

            # Build comment body
            body = self._format_issue_comment(issue)

            comments.append({
                "path": file_path,
                "line": line,
                "body": body,
            })

        return comments

    def _format_issue_comment(self, issue: dict[str, Any]) -> str:
        """Format an issue as a PR comment."""
        severity = issue.get("severity", "info")
        title = issue.get("title", "Untitled")
        description = issue.get("description", "")
        suggestion = issue.get("suggestion", "")
        agent = issue.get("agent", "unknown")

        severity_emoji = {
            "critical": ":rotating_light:",
            "major": ":warning:",
            "minor": ":bulb:",
            "info": ":information_source:",
        }.get(severity, ":information_source:")

        lines = [
            f"{severity_emoji} **[{severity.upper()}]** {title}",
            "",
            description,
        ]

        if suggestion:
            lines.extend(["", "**Suggested fix:**", suggestion])

        lines.extend(["", f"*Detected by: {agent}*"])

        return "\n".join(lines)

    def _build_review_body(self, summary: str, issues: list[dict[str, Any]]) -> str:
        """Build the review body/summary."""
        lines = [summary, ""]

        # Add cost info if available
        if not issues:
            lines.append(":white_check_mark: No issues found. LGTM!")
        else:
            # Count by severity
            counts: dict[str, int] = {}
            for issue in issues:
                sev = issue.get("severity", "info")
                counts[sev] = counts.get(sev, 0) + 1

            lines.append(f"Found **{len(issues)}** issue(s):")
            for sev in ["critical", "major", "minor", "info"]:
                if sev in counts:
                    emoji = {
                        "critical": ":rotating_light:",
                        "major": ":warning:",
                        "minor": ":bulb:",
                        "info": ":information_source:",
                    }[sev]
                    lines.append(f"- {emoji} {counts[sev]} {sev}")

        lines.extend([
            "",
            "---",
            "*Powered by [Code Review Agent](https://github.com/TroClover/code-review-agent)*",
        ])

        return "\n".join(lines)
