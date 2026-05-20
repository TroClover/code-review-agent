"""Tests for agents (with mocked LLM calls)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from breview.agents.orchestrator import OrchestratorAgent
from breview.agents.style_agent import StyleAgent
from breview.agents.context_agent import ContextAgent
from breview.agents.report_agent import ReportAgent
from breview.agents.base import AgentType
from breview.config.schema import BreviewConfig
from breview.diff.parser import DiffParser
from breview.models.agent_message import AgentMessage, MessageType
from breview.models.issue import Issue, IssueLocation, Severity
from breview.models.review import AuthorRole, PRInfo, ReviewRequest


SAMPLE_DIFF = """\
diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,5 @@
 import os
+import sys

-def main():
-    print("hello")
+def main(args=None):
+    if args is None:
+        args = sys.argv[1:]
+    print(f"hello {args}")
"""


def make_request(role: AuthorRole = AuthorRole.FULL_TIME) -> ReviewRequest:
    return ReviewRequest(
        pr_info=PRInfo(
            repo_full_name="test/repo",
            pr_number=1,
            title="Test PR",
            author="testuser",
            author_role=role,
            head_branch="feature",
        ),
        diff_content=SAMPLE_DIFF,
    )


def make_config() -> BreviewConfig:
    return BreviewConfig()


class TestStyleAgentStatic:
    """Test Style Agent static checks (no LLM)."""

    def setup_method(self):
        self.config = make_config()
        self.agent = StyleAgent(self.config, llm_client=None)

    @pytest.mark.asyncio
    async def test_static_checks_find_issues(self):
        # Line with trailing whitespace + long line
        long_line = "x = " + "a" * 150
        diff = f"""\
diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
 pass
+{long_line}
"""
        request = ReviewRequest(
            pr_info=PRInfo(repo_full_name="r", pr_number=1, title="t", author="u", head_branch="f"),
            diff_content=diff,
        )
        message = AgentMessage.create_task(
            AgentType.ORCHESTRATOR, AgentType.STYLE,
            {"request": request.model_dump(), "context": {}},
        )
        result = await self.agent.execute(message)
        assert result.message_type == MessageType.RESULT
        assert len(result.issues) >= 1

    @pytest.mark.asyncio
    async def test_static_checks_bare_except(self):
        diff = """\
diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1,3 @@
 pass
+try:
+    x = 1
+except:
+    pass
"""
        request = ReviewRequest(
            pr_info=PRInfo(repo_full_name="r", pr_number=1, title="t", author="u", head_branch="f"),
            diff_content=diff,
        )
        message = AgentMessage.create_task(
            AgentType.ORCHESTRATOR, AgentType.STYLE,
            {"request": request.model_dump(), "context": {}},
        )
        result = await self.agent.execute(message)
        titles = [i.title for i in result.issues]
        assert any("bare except" in t.lower() for t in titles)

    @pytest.mark.asyncio
    async def test_static_checks_wildcard_import(self):
        diff = """\
diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
 pass
+from os import *
"""
        request = ReviewRequest(
            pr_info=PRInfo(repo_full_name="r", pr_number=1, title="t", author="u", head_branch="f"),
            diff_content=diff,
        )
        message = AgentMessage.create_task(
            AgentType.ORCHESTRATOR, AgentType.STYLE,
            {"request": request.model_dump(), "context": {}},
        )
        result = await self.agent.execute(message)
        titles = [i.title for i in result.issues]
        assert any("wildcard" in t.lower() for t in titles)


class TestContextAgent:
    """Test Context Agent."""

    def setup_method(self):
        self.config = make_config()
        self.agent = ContextAgent(self.config)

    @pytest.mark.asyncio
    async def test_context_from_diff(self):
        request = make_request()
        message = AgentMessage.create_task(
            AgentType.ORCHESTRATOR, AgentType.CONTEXT,
            {"request": request.model_dump()},
        )
        result = await self.agent.execute(message)
        assert result.payload["total_files"] == 1
        assert result.payload["file_contexts"][0]["file_path"] == "test.py"


class TestReportAgent:
    """Test Report Agent."""

    def setup_method(self):
        self.config = make_config()
        self.agent = ReportAgent(self.config)

    def test_format_inline_comment(self):
        issue = Issue(
            id="T1", title="Test", description="Desc",
            severity=Severity.MAJOR, category="logic",
            location=IssueLocation(file_path="test.py", line_start=10),
            source_agent="code_review",
        )
        comment = self.agent.format_inline_comment(issue)
        assert comment["path"] == "test.py"
        assert comment["line"] == 10
        assert "MAJOR" in comment["body"]

    def test_format_pr_comment(self):
        issues = [
            Issue(id="T1", title="t", description="d", severity=Severity.CRITICAL, category="c",
                  location=IssueLocation(file_path="a", line_start=1), source_agent="a"),
        ]
        comment = self.agent.format_pr_comment(issues, "Found 1 issue")
        assert "Found 1 issue" in comment


class TestOrchestrator:
    """Test Orchestrator Agent."""

    def test_select_agents_intern(self):
        config = make_config()
        config.agents.intern_agents = ["style", "code_review", "safety"]
        orch = OrchestratorAgent(config, agents={})
        request = make_request(AuthorRole.INTERN)
        agents = orch._select_agents(request)
        agent_names = [a.value for a in agents]
        assert "style" in agent_names
        assert "code_review" in agent_names
        assert "safety" in agent_names

    def test_select_agents_senior(self):
        config = make_config()
        config.agents.senior_agents = ["code_review", "safety"]
        orch = OrchestratorAgent(config, agents={})
        request = make_request(AuthorRole.SENIOR)
        agents = orch._select_agents(request)
        agent_names = [a.value for a in agents]
        assert "style" not in agent_names
        assert "code_review" in agent_names

    def test_deduplicate_issues(self):
        config = make_config()
        orch = OrchestratorAgent(config, agents={})
        issues = [
            Issue(id="1", title="Same", description="d", severity=Severity.MINOR, category="c",
                  location=IssueLocation(file_path="a.py", line_start=10), source_agent="style"),
            Issue(id="2", title="Same", description="d", severity=Severity.MINOR, category="c",
                  location=IssueLocation(file_path="a.py", line_start=10), source_agent="code_review"),
        ]
        deduped = orch._deduplicate_issues(issues)
        assert len(deduped) == 1

    def test_filter_by_threshold_senior(self):
        config = make_config()
        orch = OrchestratorAgent(config, agents={})
        issues = [
            Issue(id="1", title="Critical", description="d", severity=Severity.CRITICAL, category="c",
                  location=IssueLocation(file_path="a", line_start=1), source_agent="a"),
            Issue(id="2", title="Minor", description="d", severity=Severity.MINOR, category="c",
                  location=IssueLocation(file_path="a", line_start=2), source_agent="a"),
            Issue(id="3", title="Info", description="d", severity=Severity.INFO, category="c",
                  location=IssueLocation(file_path="a", line_start=3), source_agent="a"),
        ]
        filtered = orch._filter_by_threshold(issues, AuthorRole.SENIOR)
        assert len(filtered) == 1  # Only critical
        assert filtered[0].severity == Severity.CRITICAL

    def test_filter_by_threshold_intern(self):
        config = make_config()
        orch = OrchestratorAgent(config, agents={})
        issues = [
            Issue(id="1", title="Critical", description="d", severity=Severity.CRITICAL, category="c",
                  location=IssueLocation(file_path="a", line_start=1), source_agent="a"),
            Issue(id="2", title="Minor", description="d", severity=Severity.MINOR, category="c",
                  location=IssueLocation(file_path="a", line_start=2), source_agent="a"),
        ]
        filtered = orch._filter_by_threshold(issues, AuthorRole.INTERN)
        assert len(filtered) == 2  # Interns see everything

    def test_generate_summary_no_issues(self):
        config = make_config()
        orch = OrchestratorAgent(config, agents={})
        summary = orch._generate_summary([], ["style"], [])
        assert "No issues" in summary or "LGTM" in summary

    def test_generate_summary_with_issues(self):
        config = make_config()
        orch = OrchestratorAgent(config, agents={})
        issues = [
            Issue(id="1", title="t", description="d", severity=Severity.CRITICAL, category="c",
                  location=IssueLocation(file_path="a", line_start=1), source_agent="a"),
            Issue(id="2", title="t", description="d", severity=Severity.MAJOR, category="c",
                  location=IssueLocation(file_path="a", line_start=2), source_agent="a"),
        ]
        summary = orch._generate_summary(issues, ["style", "code_review"], [])
        assert "2" in summary
        assert "critical" in summary.lower()
