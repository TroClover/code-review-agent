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
                # First try with inline comments
                review_data: dict[str, Any] = {
                    "body": body,
                    "event": event,
                    "commit_id": sha,
                }

                # Only add comments if we have valid ones
                if comments:
                    review_data["comments"] = comments

                response = await client.post(
                    f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/reviews",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json",
                    },
                    json=review_data,
                )

                # If inline comments fail, try without them
                if response.status_code == 422 and comments:
                    logger.warning("Inline comments failed, posting review without them")
                    review_data.pop("comments", None)
                    response = await client.post(
                        f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/reviews",
                        headers={
                            "Authorization": f"Bearer {self.token}",
                            "Accept": "application/vnd.github+json",
                        },
                        json=review_data,
                    )

                response.raise_for_status()
                logger.info(f"Published review to {repo}#{pr_number}")

                # Post inline comments as separate comments if needed
                if comments and "comments" not in review_data:
                    await self._post_inline_comments_separately(client, repo, pr_number, comments)

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

            # Add issue details to summary
            lines.append("")
            lines.append("### Issues Found")
            lines.append("")
            for issue in issues[:10]:  # Limit to first 10 issues
                severity = issue.get("severity", "info")
                emoji = {
                    "critical": ":rotating_light:",
                    "major": ":warning:",
                    "minor": ":bulb:",
                    "info": ":information_source:",
                }.get(severity, ":information_source:")
                title = issue.get("title", "Untitled")
                file_path = issue.get("file_path", "")
                line = issue.get("line", "")
                description = issue.get("description", "")[:200]

                lines.append(f"{emoji} **[{severity.upper()}]** {title}")
                if file_path:
                    lines.append(f"  - File: `{file_path}:{line}`")
                if description:
                    lines.append(f"  - {description}")
                lines.append("")

        lines.extend([
            "",
            "---",
            "*Powered by [Code Review Agent](https://github.com/TroClover/code-review-agent)*",
        ])

        return "\n".join(lines)

    async def _post_inline_comments_separately(
        self,
        client: httpx.AsyncClient,
        repo: str,
        pr_number: int,
        comments: list[dict[str, Any]],
    ) -> None:
        """Post inline comments as separate issue comments."""
        for comment in comments[:10]:  # Limit to 10 comments
            try:
                body = f"**{comment['path']}:{comment['line']}**\n\n{comment['body']}"
                await client.post(
                    f"{GITHUB_API_URL}/repos/{repo}/issues/{pr_number}/comments",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/vnd.github+json",
                    },
                    json={"body": body},
                )
            except Exception as e:
                logger.warning(f"Failed to post inline comment: {e}")
