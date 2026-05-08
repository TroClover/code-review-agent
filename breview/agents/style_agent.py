"""Style Agent - reviews code for style and convention issues."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..context.builder import ContextBuilder, FileContext
from ..diff.parser import ParsedDiff
from ..llm.client import LLMClient
from ..llm.parser import parse_llm_issues
from ..llm.prompts import build_style_review_prompt
from ..models.agent_message import AgentMessage, AgentType
from ..models.issue import Issue
from .base import BaseAgent

logger = logging.getLogger(__name__)


class StyleAgent(BaseAgent):
    """Style Agent - checks code style, naming conventions, and formatting.

    Uses a combination of static rules and lightweight LLM review.
    Focuses on: naming, formatting, imports, comments, docstrings.
    """

    agent_type = AgentType.STYLE
    name = "StyleAgent"

    def __init__(self, config: Any, llm_client: Optional[LLMClient] = None):
        super().__init__(config)
        self.llm_client = llm_client
        self.context_builder = ContextBuilder()

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Execute style review on the diff."""
        request_data = message.payload.get("request", {})
        context_data = message.payload.get("context", {})

        diff_content = request_data.get("diff_content", "")
        author_role = request_data.get("pr_info", {}).get("author_role", "full_time")

        # Parse diff
        from ..diff.parser import DiffParser
        parser = DiffParser()
        parsed_diff = parser.parse(diff_content)

        # Run static style checks first (no LLM needed)
        static_issues = self._run_static_checks(parsed_diff)

        # Run LLM review for each file
        llm_issues: list[Issue] = []
        if self.llm_client:
            llm_issues = await self._run_llm_review(parsed_diff, author_role)

        all_issues = static_issues + llm_issues
        return AgentMessage.create_result(self.agent_type, all_issues)

    def _run_static_checks(self, parsed_diff: ParsedDiff) -> list[Issue]:
        """Run static style checks without LLM."""
        import re
        issues: list[Issue] = []

        for file_change in parsed_diff.files:
            if file_change.is_binary:
                continue

            for hunk in file_change.hunks:
                for line in hunk.changed_lines:
                    if not line.is_addition:
                        continue

                    content = line.content
                    line_no = line.line_number

                    # Check: line length (Python: 120, C++: 100)
                    max_len = 100 if file_change.new_path.endswith((".cpp", ".cc", ".h", ".hpp")) else 120
                    if len(content) > max_len:
                        issues.append(self._make_issue(
                            title="Line too long",
                            description=f"Line has {len(content)} characters (max {max_len})",
                            severity="minor",
                            category="formatting",
                            file_path=file_change.new_path,
                            line=line_no,
                        ))

                    # Check: trailing whitespace
                    if content != content.rstrip():
                        issues.append(self._make_issue(
                            title="Trailing whitespace",
                            description="Line has trailing whitespace",
                            severity="info",
                            category="formatting",
                            file_path=file_change.new_path,
                            line=line_no,
                        ))

                    # Check: bare except (Python)
                    if file_change.new_path.endswith(".py"):
                        if re.match(r"\s*except\s*:", content):
                            issues.append(self._make_issue(
                                title="Bare except clause",
                                description="Bare 'except:' catches all exceptions including SystemExit and KeyboardInterrupt. Catch specific exceptions instead.",
                                severity="major",
                                category="error_handling",
                                file_path=file_change.new_path,
                                line=line_no,
                                suggestion="except (ValueError, TypeError) as e:",
                            ))

                        # Check: wildcard import
                        if "import *" in content:
                            issues.append(self._make_issue(
                                title="Wildcard import",
                                description="Wildcard imports ('from X import *') pollute namespace and make dependencies unclear.",
                                severity="minor",
                                category="imports",
                                file_path=file_change.new_path,
                                line=line_no,
                            ))

                        # Check: mutable default argument
                        if re.search(r"def \w+\(.*=\s*(\[\]|\{\})\)", content):
                            issues.append(self._make_issue(
                                title="Mutable default argument",
                                description="Mutable default arguments are shared across calls, leading to unexpected behavior.",
                                severity="major",
                                category="logic",
                                file_path=file_change.new_path,
                                line=line_no,
                                suggestion="Use None as default and initialize inside the function.",
                            ))

                    # Check: TODO/FIXME/HACK comments
                    if re.search(r"#\s*(TODO|FIXME|HACK|XXX)\b", content, re.IGNORECASE):
                        issues.append(self._make_issue(
                            title="TODO/FIXME comment",
                            description="Code contains a TODO/FIXME comment. Consider addressing it or creating a ticket.",
                            severity="info",
                            category="documentation",
                            file_path=file_change.new_path,
                            line=line_no,
                        ))

        return issues

    async def _run_llm_review(self, parsed_diff: ParsedDiff, author_role: str) -> list[Issue]:
        """Run LLM-based style review for each file."""
        issues: list[Issue] = []

        for file_change in parsed_diff.files:
            if file_change.is_binary:
                continue

            file_ctx = {
                "file_path": file_change.new_path,
                "change_type": file_change.change_type.value,
                "diff_content": self._format_diff(file_change),
                "surrounding_code": "",
                "file_header": "",
                "author_role": author_role,
            }

            # Build context if repo path available
            if self.context_builder.repo_path:
                full_ctx = self.context_builder._build_file_context(file_change)
                file_ctx["surrounding_code"] = full_ctx.surrounding_code
                file_ctx["file_header"] = full_ctx.file_header

            messages = build_style_review_prompt(file_ctx)
            try:
                response = await self.llm_client.complete(
                    messages=messages,
                    model=self.config.llm.model if hasattr(self.config, "llm") else "gpt-4o-mini",
                    temperature=0.1,
                    max_tokens=2048,
                )
                file_issues = parse_llm_issues(response.content, "style", file_change.new_path)
                issues.extend(file_issues)
            except Exception as e:
                logger.warning(f"LLM style review failed for {file_change.new_path}: {e}")

        return issues

    def _format_diff(self, file_change) -> str:
        """Format a FileChange back to diff text."""
        lines = []
        for hunk in file_change.hunks:
            lines.append(f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@")
            for ctx in hunk.context_lines:
                lines.append(f" {ctx}")
            for cl in hunk.changed_lines:
                prefix = "+" if cl.is_addition else "-"
                lines.append(f"{prefix}{cl.content}")
        return "\n".join(lines)

    def _make_issue(
        self,
        title: str,
        description: str,
        severity: str,
        category: str,
        file_path: str,
        line: int,
        suggestion: Optional[str] = None,
    ) -> Issue:
        """Create an Issue object."""
        import uuid
        from ..models.issue import Issue, IssueLocation, Severity

        return Issue(
            id=f"STYLE-{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            severity=Severity(severity),
            category=category,
            location=IssueLocation(file_path=file_path, line_start=line),
            suggestion=suggestion,
            source_agent="style",
        )
