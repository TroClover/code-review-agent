"""Notification integration for review completion alerts."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends notifications when reviews complete.

    Supports: Slack, Email, Feishu (飞书)
    """

    def __init__(
        self,
        channel: str = "slack",
        webhook_url: Optional[str] = None,
        enabled: bool = False,
    ):
        self.channel = channel
        self.webhook_url = webhook_url
        self.enabled = enabled

    async def send_review_notification(
        self,
        repo_full_name: str,
        pr_number: int,
        pr_title: str,
        author: str,
        issue_count: int,
        severity_counts: dict[str, int],
        is_approved: bool,
        duration_seconds: float,
    ) -> None:
        """Send a notification about a completed review.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number
            pr_title: PR title
            author: PR author
            issue_count: Total issues found
            severity_counts: Issues by severity
            is_approved: Whether the review passed
            duration_seconds: How long the review took
        """
        if not self.enabled:
            return

        message = self._format_message(
            repo_full_name, pr_number, pr_title, author,
            issue_count, severity_counts, is_approved, duration_seconds,
        )

        try:
            if self.channel == "slack":
                await self._send_slack(message)
            elif self.channel == "feishu":
                await self._send_feishu(message)
            else:
                logger.warning(f"Unsupported notification channel: {self.channel}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def _format_message(
        self,
        repo: str,
        pr_number: int,
        title: str,
        author: str,
        issue_count: int,
        severity_counts: dict[str, int],
        is_approved: bool,
        duration: float,
    ) -> str:
        """Format notification message."""
        status = ":white_check_mark: Approved" if is_approved else ":x: Changes Requested"
        severity_str = ", ".join(f"{k}: {v}" for k, v in severity_counts.items() if v > 0)

        return (
            f"*BRT Code Review Complete*\n"
            f"Repository: `{repo}`\n"
            f"PR: #{pr_number} - {title}\n"
            f"Author: {author}\n"
            f"Status: {status}\n"
            f"Issues: {issue_count} ({severity_str})\n"
            f"Duration: {duration:.1f}s"
        )

    async def _send_slack(self, message: str) -> None:
        """Send notification to Slack via webhook."""
        if not self.webhook_url:
            logger.warning("No Slack webhook URL configured")
            return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json={"text": message},
            )
            response.raise_for_status()

    async def _send_feishu(self, message: str) -> None:
        """Send notification to Feishu via webhook."""
        if not self.webhook_url:
            logger.warning("No Feishu webhook URL configured")
            return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.webhook_url,
                json={
                    "msg_type": "text",
                    "content": {"text": message},
                },
            )
            response.raise_for_status()
