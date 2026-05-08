"""Code Review Agent - core review for logic, security, and performance."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..diff.parser import DiffParser, ParsedDiff
from ..llm.client import LLMClient
from ..llm.parser import parse_llm_issues
from ..llm.prompts import build_code_review_prompt
from ..models.agent_message import AgentMessage, AgentType
from ..models.issue import Issue
from .base import BaseAgent

logger = logging.getLogger(__name__)


class CodeReviewAgent(BaseAgent):
    """Code Review Agent - the core review agent with 3 sub-prompts.

    Sub-prompts run in parallel:
    1. Logic correctness
    2. Security vulnerabilities
    3. Performance issues
    """

    agent_type = AgentType.CODE_REVIEW
    name = "CodeReviewAgent"

    def __init__(self, config: Any, llm_client: LLMClient):
        super().__init__(config)
        self.llm_client = llm_client
        from ..context.builder import ContextBuilder
        self.context_builder = ContextBuilder()

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Execute code review on the diff."""
        request_data = message.payload.get("request", {})
        context_data = message.payload.get("context", {})

        diff_content = request_data.get("diff_content", "")
        author_role = request_data.get("pr_info", {}).get("author_role", "full_time")

        parser = DiffParser()
        parsed_diff = parser.parse(diff_content)

        # Review all files in parallel
        tasks = []
        for file_change in parsed_diff.files:
            if file_change.is_binary:
                continue
            tasks.append(self._review_file(file_change, author_role))

        file_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_issues: list[Issue] = []
        for result in file_results:
            if isinstance(result, Exception):
                logger.warning(f"File review failed: {result}")
            elif isinstance(result, list):
                all_issues.extend(result)

        return AgentMessage.create_result(self.agent_type, all_issues)

    async def _review_file(self, file_change, author_role: str) -> list[Issue]:
        """Review a single file for logic, security, and performance issues."""
        # Detect language
        language = self._detect_language(file_change.new_path)

        # Build file context
        file_ctx = {
            "file_path": file_change.new_path,
            "change_type": file_change.change_type.value,
            "diff_content": self._format_diff(file_change),
            "surrounding_code": "",
            "file_header": "",
            "function_signatures": [],
            "language": language,
            "author_role": author_role,
        }

        if self.context_builder.repo_path:
            full_ctx = self.context_builder._build_file_context(file_change)
            file_ctx["surrounding_code"] = full_ctx.surrounding_code
            file_ctx["file_header"] = full_ctx.file_header
            file_ctx["function_signatures"] = full_ctx.function_signatures

        messages = build_code_review_prompt(file_ctx, author_role)

        try:
            response = await self.llm_client.complete(
                messages=messages,
                model=self.config.llm.model if hasattr(self.config, "llm") else "gpt-4",
                temperature=0.1,
                max_tokens=4096,
            )
            return parse_llm_issues(response.content, "code_review", file_change.new_path)
        except Exception as e:
            logger.warning(f"Code review failed for {file_change.new_path}: {e}")
            return []

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
            ".h": "cpp", ".hpp": "cpp", ".hxx": "cpp",
            ".c": "c",
            ".java": "java",
            ".js": "javascript", ".ts": "typescript",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return "unknown"

    def _format_diff(self, file_change) -> str:
        """Format a FileChange to diff text."""
        lines = []
        for hunk in file_change.hunks:
            lines.append(f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@")
            for ctx in hunk.context_lines:
                lines.append(f" {ctx}")
            for cl in hunk.changed_lines:
                prefix = "+" if cl.is_addition else "-"
                lines.append(f"{prefix}{cl.content}")
        return "\n".join(lines)
