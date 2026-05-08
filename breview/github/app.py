"""GitHub App for handling webhooks and PR interactions."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


class GitHubApp:
    """GitHub App integration for automated PR reviews.

    Handles:
    - Webhook event processing (PR opened, synchronize, reopened)
    - PR review comment posting
    - Review status management
    """

    def __init__(
        self,
        app_id: str,
        private_key: str,
        webhook_secret: Optional[str] = None,
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.webhook_secret = webhook_secret
        self._installation_id: Optional[int] = None
        self._token: Optional[str] = None

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature.

        Args:
            payload: Raw request body
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            return True
        expected = "sha256=" + hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token.

        Args:
            installation_id: GitHub App installation ID

        Returns:
            Access token for the installation
        """
        import jwt

        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": self.app_id,
        }
        token = jwt.encode(payload, self.private_key, algorithm="RS256")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data["token"]
            return self._token

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        """Get the diff for a pull request.

        Args:
            repo_full_name: Repository full name (owner/repo)
            pr_number: PR number

        Returns:
            Unified diff content
        """
        token = await self._ensure_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/repos/{repo_full_name}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3.diff",
                },
            )
            response.raise_for_status()
            return response.text

    async def get_pr_info(self, repo_full_name: str, pr_number: int) -> dict[str, Any]:
        """Get PR metadata.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number

        Returns:
            PR metadata dict
        """
        token = await self._ensure_token()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/repos/{repo_full_name}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            return response.json()

    async def post_review(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        comments: list[dict[str, Any]] | None = None,
        event: str = "COMMENT",
        commit_sha: str = "",
    ) -> dict[str, Any]:
        """Post a review on a pull request.

        Args:
            repo_full_name: Repository full name (owner/repo)
            pr_number: PR number
            body: Review body/summary
            comments: List of inline comments
            event: Review event type (APPROVE, REQUEST_CHANGES, COMMENT)
            commit_sha: Commit SHA to attach the review to

        Returns:
            API response data
        """
        token = await self._ensure_token()
        review_data: dict[str, Any] = {
            "body": body,
            "event": event,
        }
        if comments:
            review_data["comments"] = [
                {
                    "path": c["path"],
                    "line": c["line"],
                    "body": c["body"],
                }
                for c in comments
            ]
        if commit_sha:
            review_data["commit_id"] = commit_sha

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/repos/{repo_full_name}/pulls/{pr_number}/reviews",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json=review_data,
            )
            response.raise_for_status()
            return response.json()

    async def post_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> dict[str, Any]:
        """Post a simple comment on a pull request.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number
            body: Comment body

        Returns:
            API response data
        """
        token = await self._ensure_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/repos/{repo_full_name}/issues/{pr_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={"body": body},
            )
            response.raise_for_status()
            return response.json()

    async def set_status(
        self,
        repo_full_name: str,
        sha: str,
        state: str,
        description: str = "",
        context: str = "breview",
    ) -> None:
        """Set commit status (pass/fail/pending).

        Args:
            repo_full_name: Repository full name
            sha: Commit SHA
            state: "success", "failure", "pending", or "error"
            description: Status description
            context: Status context name
        """
        token = await self._ensure_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/repos/{repo_full_name}/statuses/{sha}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "state": state,
                    "description": description,
                    "context": context,
                },
            )
            response.raise_for_status()

    async def _ensure_token(self) -> str:
        """Ensure we have a valid access token."""
        if not self._token:
            if not self._installation_id:
                raise RuntimeError("No installation ID set. Call get_installation_token first.")
            await self.get_installation_token(self._installation_id)
        return self._token or ""


import time
