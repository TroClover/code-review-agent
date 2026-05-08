"""Tests for data models."""

import pytest

from breview.models.issue import Issue, IssueLocation, Severity
from breview.models.review import AuthorRole, PRInfo, ReviewRequest, ReviewResult


class TestIssue:
    def test_create_issue(self):
        issue = Issue(
            id="TEST-001",
            title="Test issue",
            description="This is a test issue",
            severity=Severity.MAJOR,
            category="logic",
            location=IssueLocation(file_path="test.py", line_start=10),
            source_agent="code_review",
        )
        assert issue.severity == Severity.MAJOR
        assert issue.location.file_path == "test.py"

    def test_to_comment_body(self):
        issue = Issue(
            id="TEST-001",
            title="Unused variable",
            description="Variable 'x' is assigned but never used",
            severity=Severity.MINOR,
            category="style",
            location=IssueLocation(file_path="test.py", line_start=5),
            suggestion="Remove the unused variable",
            source_agent="style",
        )
        body = issue.to_comment_body()
        assert "MINOR" in body
        assert "Unused variable" in body
        assert "Suggested fix" in body


class TestReviewResult:
    def test_severity_counts(self):
        issues = [
            Issue(id="1", title="t", description="d", severity=Severity.CRITICAL, category="c",
                  location=IssueLocation(file_path="a", line_start=1), source_agent="a"),
            Issue(id="2", title="t", description="d", severity=Severity.CRITICAL, category="c",
                  location=IssueLocation(file_path="a", line_start=2), source_agent="a"),
            Issue(id="3", title="t", description="d", severity=Severity.MAJOR, category="c",
                  location=IssueLocation(file_path="a", line_start=3), source_agent="a"),
        ]
        result = ReviewResult(
            request=ReviewRequest(
                pr_info=PRInfo(repo_full_name="test/repo", pr_number=1, title="test", author="user",
                              head_branch="feature"),
                diff_content="",
            ),
            issues=issues,
        )
        assert result.severity_counts == {"critical": 2, "major": 1}
        assert len(result.critical_issues) == 2


class TestPRInfo:
    def test_default_role(self):
        pr = PRInfo(
            repo_full_name="test/repo",
            pr_number=1,
            title="Test PR",
            author="testuser",
            head_branch="feature",
        )
        assert pr.author_role == AuthorRole.FULL_TIME
