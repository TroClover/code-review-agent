"""Context Agent - builds review context from diff and repository."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..context.builder import ContextBuilder
from ..diff.parser import DiffParser
from ..models.agent_message import AgentMessage, AgentType
from .base import BaseAgent

logger = logging.getLogger(__name__)


class ContextAgent(BaseAgent):
    """Context Agent - builds context for other review agents.

    This agent runs first in the pipeline and produces context data
    that is shared with Style, Code Review, and Safety agents.

    Responsibilities:
    1. Parse diff into structured data
    2. Extract surrounding code context
    3. Build file headers and function signatures
    4. Analyze git history (if available)
    """

    agent_type = AgentType.CONTEXT
    name = "ContextAgent"

    def __init__(self, config: Any, repo_path: Optional[str] = None):
        super().__init__(config)
        self.context_builder = ContextBuilder(repo_path=repo_path)

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Build context from the review request."""
        request_data = message.payload.get("request", {})
        diff_content = request_data.get("diff_content", "")
        pr_info = request_data.get("pr_info", {})
        author_role = pr_info.get("author_role", "full_time")

        # Parse diff
        parser = DiffParser()
        parsed_diff = parser.parse(diff_content)

        # Build context
        context = self.context_builder.build_context(
            parsed_diff,
            pr_description=pr_info.get("description", ""),
            author_role=author_role,
        )

        # Serialize context for other agents
        context_data = {
            "file_contexts": [
                {
                    "file_path": fc.file_path,
                    "change_type": fc.change_type,
                    "diff_content": fc.diff_content,
                    "surrounding_code": fc.surrounding_code,
                    "file_header": fc.file_header,
                    "function_signatures": fc.function_signatures,
                    "total_lines": fc.total_lines,
                }
                for fc in context.file_contexts
            ],
            "pr_description": context.pr_description,
            "author_role": context.author_role,
            "total_files": len(context.file_contexts),
        }

        result = AgentMessage.create_result(self.agent_type, [])
        result.payload = context_data
        return result
