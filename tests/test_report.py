"""Tests for the report generator."""

import json
import tempfile
from pathlib import Path

import pytest

from breview.models.issue import Issue, IssueLocation, Severity
from breview.models.review import AuthorRole, PRInfo, ReviewRequest, ReviewResult
from breview.report.generator import ReportGenerator


def make_result(issues=None, is_approved=True):
    return ReviewResult(
        request=ReviewRequest(
            pr_info=PRInfo(
                repo_full_name="org/repo",
                pr_number=42,
                title="Fix bug",
                author="developer",
                author_role=AuthorRole.FULL_TIME,
                head_branch="fix/bug",
            ),
            diff_content="",
        ),
        issues=issues or [],
        summary="Review complete",
        agents_executed=["style", "code_review"],
        duration_seconds=15.5,
        is_approved=is_approved,
    )


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def setup_method(self):
        self.gen = ReportGenerator()

    def test_markdown_report_no_issues(self):
        result = make_result()
        md = self.gen.generate_markdown(result)
        assert "org/repo" in md
        assert "#42" in md
        assert "developer" in md
        assert "Total issues: 0" in md

    def test_markdown_report_with_issues(self):
        issues = [
            Issue(id="T1", title="Null pointer", description="Possible null dereference",
                  severity=Severity.CRITICAL, category="logic",
                  location=IssueLocation(file_path="main.py", line_start=42),
                  suggestion="Add null check", source_agent="code_review"),
            Issue(id="T2", title="Style issue", description="Bad naming",
                  severity=Severity.MINOR, category="style",
                  location=IssueLocation(file_path="utils.py", line_start=10),
                  source_agent="style"),
        ]
        result = make_result(issues)
        md = self.gen.generate_markdown(result)
        assert "CRITICAL" in md
        assert "Null pointer" in md
        assert "main.py" in md
        assert "MINOR" in md

    def test_json_report_no_issues(self):
        result = make_result()
        report_json = self.gen.generate_json(result)
        data = json.loads(report_json)
        assert data["pr"]["repo"] == "org/repo"
        assert data["pr"]["number"] == 42
        assert len(data["issues"]) == 0
        assert data["is_approved"] is True

    def test_json_report_with_issues(self):
        issues = [
            Issue(id="T1", title="t", description="d", severity=Severity.MAJOR, category="perf",
                  location=IssueLocation(file_path="a.py", line_start=5),
                  source_agent="code_review"),
        ]
        result = make_result(issues)
        report_json = self.gen.generate_json(result)
        data = json.loads(report_json)
        assert len(data["issues"]) == 1
        assert data["issues"][0]["severity"] == "major"
        assert data["statistics"]["severity_counts"]["major"] == 1

    def test_save_markdown_report(self):
        result = make_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.gen.save_report(result, Path(tmpdir), format="markdown")
            assert path.exists()
            assert path.suffix == ".md"
            content = path.read_text()
            assert "org/repo" in content

    def test_save_json_report(self):
        result = make_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.gen.save_report(result, Path(tmpdir), format="json")
            assert path.exists()
            assert path.suffix == ".json"
            data = json.loads(path.read_text())
            assert data["pr"]["repo"] == "org/repo"
