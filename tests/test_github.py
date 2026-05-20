"""Tests for GitHub integration (with mocked HTTP calls)."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from breview.github.app import GitHubApp
from breview.github.webhook import WebhookHandler, PR_OPENED, PR_SYNCHRONIZE, PR_REOPENED
from breview.github.notification import NotificationService


class TestGitHubAppWebhookVerification:
    """Tests for webhook signature verification."""

    def test_verify_valid_signature(self):
        secret = "test-secret"
        payload = b'{"action": "opened"}'
        expected_sig = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        app = GitHubApp(app_id="123", private_key="key", webhook_secret=secret)
        assert app.verify_webhook(payload, expected_sig) is True

    def test_verify_invalid_signature(self):
        app = GitHubApp(app_id="123", private_key="key", webhook_secret="secret")
        assert app.verify_webhook(b"data", "sha256=invalid") is False

    def test_verify_no_secret_always_passes(self):
        app = GitHubApp(app_id="123", private_key="key", webhook_secret=None)
        assert app.verify_webhook(b"data", "anything") is True


class TestGitHubAppStatus:
    """Tests for commit status setting."""

    @pytest.mark.asyncio
    async def test_set_status_success(self):
        app = GitHubApp(app_id="123", private_key="key")
        app._token = "test-token"

        with patch("breview.github.app.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                post=AsyncMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await app.set_status(
                "org/repo", "abc123", "success", "All checks passed"
            )


class TestWebhookHandler:
    """Tests for webhook event handling."""

    def setup_method(self):
        self.github_app = GitHubApp(app_id="123", private_key="key")
        self.review_callback = AsyncMock()
        self.handler = WebhookHandler(
            github_app=self.github_app,
            on_pr_review=self.review_callback,
        )

    @pytest.mark.asyncio
    async def test_handle_pr_opened(self):
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "title": "Fix bug",
                "user": {"login": "developer"},
                "head": {"sha": "abc123"},
                "body": "Fixes #10",
            },
            "repository": {"full_name": "org/repo"},
        }

        self.github_app.get_pr_diff = AsyncMock(return_value="diff content")

        result = await self.handler.handle_event("pull_request", payload)
        assert result["status"] == "review_triggered"
        assert result["pr_number"] == 42
        self.review_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_pr_synchronize(self):
        payload = {
            "action": "synchronize",
            "pull_request": {
                "number": 42,
                "title": "Fix bug",
                "user": {"login": "developer"},
                "head": {"sha": "def456"},
                "body": "",
            },
            "repository": {"full_name": "org/repo"},
        }

        self.github_app.get_pr_diff = AsyncMock(return_value="updated diff")

        result = await self.handler.handle_event("pull_request", payload)
        assert result["status"] == "review_triggered"

    @pytest.mark.asyncio
    async def test_handle_pr_ignored_action(self):
        payload = {
            "action": "labeled",
            "pull_request": {"number": 1},
            "repository": {"full_name": "org/repo"},
        }
        result = await self.handler.handle_event("pull_request", payload)
        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_handle_unknown_event(self):
        result = await self.handler.handle_event("push", {})
        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_handle_pr_review_submitted(self):
        payload = {
            "action": "submitted",
            "review": {"user": {"login": "reviewer"}},
            "pull_request": {"number": 42},
            "repository": {"full_name": "org/repo"},
        }
        result = await self.handler.handle_event("pull_request_review", payload)
        assert result["status"] == "review_noted"

    @pytest.mark.asyncio
    async def test_handle_diff_fetch_failure(self):
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 1, "title": "t", "user": {"login": "u"},
                "head": {"sha": "s"}, "body": "",
            },
            "repository": {"full_name": "org/repo"},
        }
        self.github_app.get_pr_diff = AsyncMock(side_effect=Exception("API error"))

        result = await self.handler.handle_event("pull_request", payload)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_review_callback_data_structure(self):
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "title": "Fix bug",
                "user": {"login": "dev"},
                "head": {"sha": "abc"},
                "body": "Description",
            },
            "repository": {"full_name": "org/repo"},
        }
        self.github_app.get_pr_diff = AsyncMock(return_value="diff")

        await self.handler.handle_event("pull_request", payload)

        call_args = self.review_callback.call_args[0][0]
        assert call_args["repo_full_name"] == "org/repo"
        assert call_args["pr_number"] == 42
        assert call_args["author"] == "dev"
        assert call_args["diff_content"] == "diff"
        assert call_args["is_incremental"] is False

    @pytest.mark.asyncio
    async def test_incremental_review_flag(self):
        payload = {
            "action": "synchronize",
            "pull_request": {
                "number": 1, "title": "t", "user": {"login": "u"},
                "head": {"sha": "s"}, "body": "",
            },
            "repository": {"full_name": "org/repo"},
        }
        self.github_app.get_pr_diff = AsyncMock(return_value="diff")

        await self.handler.handle_event("pull_request", payload)
        call_args = self.review_callback.call_args[0][0]
        assert call_args["is_incremental"] is True


class TestNotificationService:
    """Tests for the notification service."""

    def test_disabled_notification(self):
        service = NotificationService(enabled=False)
        # Should not raise, just return
        import asyncio
        asyncio.run(service.send_review_notification(
            "org/repo", 1, "PR", "user", 0, {}, True, 1.0,
        ))

    def test_format_message(self):
        service = NotificationService()
        msg = service._format_message(
            "org/repo", 42, "Fix bug", "developer",
            3, {"critical": 1, "major": 2}, False, 15.5,
        )
        assert "org/repo" in msg
        assert "#42" in msg
        assert "developer" in msg
        assert "Changes Requested" in msg
        assert "3" in msg

    def test_format_message_approved(self):
        service = NotificationService()
        msg = service._format_message(
            "org/repo", 1, "t", "u", 0, {}, True, 5.0,
        )
        assert "Approved" in msg

    @pytest.mark.asyncio
    async def test_unsupported_channel(self):
        service = NotificationService(enabled=True, channel="discord")
        # Should not raise, just log warning
        await service.send_review_notification(
            "org/repo", 1, "PR", "user", 0, {}, True, 1.0,
        )
