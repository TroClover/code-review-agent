"""Webhook handler for GitHub PR events."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine, Optional

from .app import GitHubApp

logger = logging.getLogger(__name__)

# Event types we care about
PR_OPENED = "opened"
PR_SYNCHRONIZE = "synchronize"
PR_REOPENED = "reopened"

HANDLED_PR_ACTIONS = {PR_OPENED, PR_SYNCHRONIZE, PR_REOPENED}


class WebhookHandler:
    """Handles incoming GitHub webhook events.

    Processes PR events and triggers the review pipeline.
    """

    def __init__(
        self,
        github_app: GitHubApp,
        on_pr_review: Optional[Callable[[dict[str, Any]], Coroutine]] = None,
    ):
        self.github_app = github_app
        self.on_pr_review = on_pr_review

    async def handle_event(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle a webhook event.

        Args:
            event_type: GitHub event type (from X-GitHub-Event header)
            payload: Webhook payload

        Returns:
            Response dict
        """
        if event_type == "pull_request":
            return await self._handle_pull_request(payload)
        elif event_type == "pull_request_review":
            return await self._handle_pr_review(payload)
        else:
            logger.info(f"Ignoring event type: {event_type}")
            return {"status": "ignored", "event": event_type}

    async def _handle_pull_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle pull_request event.

        Triggers review on opened, synchronize, and reopened actions.
        """
        action = payload.get("action")
        if action not in HANDLED_PR_ACTIONS:
            logger.info(f"Ignoring PR action: {action}")
            return {"status": "ignored", "action": action}

        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})

        repo_full_name = repo.get("full_name", "")
        pr_number = pr.get("number", 0)
        pr_title = pr.get("title", "")
        author = pr.get("user", {}).get("login", "")
        head_sha = pr.get("head", {}).get("sha", "")
        is_incremental = action == PR_SYNCHRONIZE

        logger.info(
            f"PR #{pr_number} {action} in {repo_full_name} by {author}",
        )

        # Fetch diff
        try:
            diff_content = await self.github_app.get_pr_diff(repo_full_name, pr_number)
        except Exception as e:
            logger.error(f"Failed to fetch diff for {repo_full_name}#{pr_number}: {e}")
            return {"status": "error", "error": str(e)}

        # Build review request data
        review_data = {
            "repo_full_name": repo_full_name,
            "pr_number": pr_number,
            "pr_title": pr_title,
            "author": author,
            "head_sha": head_sha,
            "diff_content": diff_content,
            "is_incremental": is_incremental,
            "pr_description": pr.get("body", ""),
        }

        # Trigger review callback
        if self.on_pr_review:
            try:
                await self.on_pr_review(review_data)
            except Exception as e:
                logger.error(f"Review callback failed: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}

        return {"status": "review_triggered", "pr_number": pr_number}

    async def _handle_pr_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle pull_request_review event.

        Useful for tracking human review comments for knowledge extraction.
        """
        action = payload.get("action")
        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})

        if action != "submitted":
            return {"status": "ignored", "action": action}

        logger.info(
            f"Review submitted on {repo.get('full_name')}#{pr.get('number')} "
            f"by {review.get('user', {}).get('login')}"
        )

        return {"status": "review_noted"}
