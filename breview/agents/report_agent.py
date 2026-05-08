"""Report Agent - generates review reports and handles feedback."""

from __future__ import annotations

import logging
from typing import Any

from ..models.agent_message import AgentMessage, AgentType
from ..models.issue import Issue
from ..report.generator import ReportGenerator
from .base import BaseAgent

logger = logging.getLogger(__name__)


class ReportAgent(BaseAgent):
    """Report Agent - generates review reports and manages feedback.

    Responsibilities:
    1. Generate Markdown/HTML reports
    2. Format PR comments
    3. Collect developer feedback (helpful/not helpful)
    """

    agent_type = AgentType.REPORT
    name = "ReportAgent"

    def __init__(self, config: Any):
        super().__init__(config)
        self.report_generator = ReportGenerator()

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Generate report from review results."""
        # Report agent doesn't produce issues, it produces output
        result = AgentMessage.create_result(self.agent_type, [])
        result.payload = {"status": "report_generated"}
        return result

    def format_pr_comment(self, issues: list[Issue], summary: str) -> str:
        """Format issues and summary into a PR comment."""
        lines = [summary, ""]

        if not issues:
            return "\n".join(lines)

        # Group issues by severity
        by_severity: dict[str, list[Issue]] = {}
        for issue in issues:
            sev = issue.severity.value
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(issue)

        # Add feedback hint
        lines.append("> :+1: Was this review helpful? React with :thumbsup: or :thumbsdown:")
        lines.append("")

        return "\n".join(lines)

    def format_inline_comment(self, issue: Issue) -> dict[str, Any]:
        """Format an issue as a GitHub inline review comment."""
        return {
            "path": issue.location.file_path,
            "line": issue.location.line_start,
            "body": issue.to_comment_body(),
        }
