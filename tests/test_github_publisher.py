"""Tests for GitHub review publisher (TC-GH-2, TC-GH-3)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from breview.github.publisher import ReviewPublisher


@pytest.fixture
def publisher():
    """Create a publisher with mock token."""
    return ReviewPublisher(token="test-token")


@pytest.fixture
def sample_issues():
    """Create sample issues for testing."""
    return [
        {
            "id": "CR-1",
            "title": "Hardcoded API key",
            "description": "API key is hardcoded in source code",
            "severity": "critical",
            "category": "security",
            "file_path": "config.py",
            "line": 10,
            "suggestion": "Use environment variables",
            "agent": "code_review",
        },
        {
            "id": "SAF-1",
            "title": "Missing error handling",
            "description": "No try-except block",
            "severity": "major",
            "category": "safety",
            "file_path": "app.py",
            "line": 25,
            "suggestion": "Add try-except block",
            "agent": "safety",
        },
    ]


class TestReviewPublisher:
    """TC-GH-2: PR Comment publishing."""

    def test_format_issue_comment(self, publisher):
        """Test issue comment formatting."""
        issue = {
            "title": "Test issue",
            "description": "Test description",
            "severity": "critical",
            "suggestion": "Fix it",
            "agent": "code_review",
        }
        comment = publisher._format_issue_comment(issue)

        assert "**[CRITICAL]**" in comment
        assert "Test issue" in comment
        assert "Test description" in comment
        assert "Fix it" in comment
        assert "code_review" in comment

    def test_build_comments(self, publisher, sample_issues):
        """Test building inline comments."""
        comments = publisher._build_comments(sample_issues)

        assert len(comments) == 2
        assert comments[0]["path"] == "config.py"
        assert comments[0]["line"] == 10
        assert comments[1]["path"] == "app.py"
        assert comments[1]["line"] == 25

    def test_build_comments_skips_empty_path(self, publisher):
        """Test that comments with empty file path are skipped."""
        issues = [{"file_path": "", "line": 1, "severity": "info", "title": "test", "description": "test", "agent": "test"}]
        comments = publisher._build_comments(issues)
        assert len(comments) == 0

    def test_build_review_body_approved(self, publisher, sample_issues):
        """Test review body for approved review."""
        summary = "## Review Summary"
        body = publisher._build_review_body(summary, [])

        assert "LGTM" in body
        assert "Code Review Agent" in body

    def test_build_review_body_with_issues(self, publisher, sample_issues):
        """Test review body with issues."""
        summary = "## Review Summary"
        body = publisher._build_review_body(summary, sample_issues)

        assert "2" in body
        assert "critical" in body
        assert "major" in body

    @patch("httpx.AsyncClient.post")
    @pytest.mark.asyncio
    async def test_publish_review_success(self, mock_post, publisher, sample_issues):
        """TC-GH-2: Test successful review publishing."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await publisher.publish_review(
            repo="owner/repo",
            pr_number=42,
            sha="abc123",
            summary="## Review Summary",
            issues=sample_issues,
            is_approved=False,
        )

        assert result is True
        mock_post.assert_called_once()

        # Verify the call arguments
        call_args = mock_post.call_args
        assert "owner/repo/pulls/42/reviews" in call_args[0][0]

    @patch("httpx.AsyncClient.post")
    @pytest.mark.asyncio
    async def test_publish_review_no_token(self, mock_post, sample_issues):
        """Test review publishing without token."""
        publisher = ReviewPublisher(token=None)

        result = await publisher.publish_review(
            repo="owner/repo",
            pr_number=42,
            sha="abc123",
            summary="## Review Summary",
            issues=sample_issues,
            is_approved=False,
        )

        assert result is False
        mock_post.assert_not_called()


class TestCommitStatus:
    """TC-GH-3: Commit status management."""

    @patch("httpx.AsyncClient.post")
    @pytest.mark.asyncio
    async def test_set_status_pending(self, mock_post, publisher):
        """Test setting pending status."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await publisher.set_status(
            repo="owner/repo",
            sha="abc123",
            state="pending",
            description="Review in progress",
        )

        assert result is True
        mock_post.assert_called_once()

    @patch("httpx.AsyncClient.post")
    @pytest.mark.asyncio
    async def test_set_status_success(self, mock_post, publisher):
        """Test setting success status."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await publisher.set_status(
            repo="owner/repo",
            sha="abc123",
            state="success",
            description="Review passed",
        )

        assert result is True

    @patch("httpx.AsyncClient.post")
    @pytest.mark.asyncio
    async def test_set_status_failure(self, mock_post, publisher):
        """Test setting failure status."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await publisher.set_status(
            repo="owner/repo",
            sha="abc123",
            state="failure",
            description="Review failed",
        )

        assert result is True

    @patch("httpx.AsyncClient.post")
    @pytest.mark.asyncio
    async def test_set_status_no_token(self, mock_post):
        """Test setting status without token."""
        publisher = ReviewPublisher(token=None)

        result = await publisher.set_status(
            repo="owner/repo",
            sha="abc123",
            state="success",
        )

        assert result is False
        mock_post.assert_not_called()
