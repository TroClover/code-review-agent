"""Knowledge Agent - links issues to knowledge entries (simplified for MVP).

This agent only does static knowledge matching against CODING_STANDARD.md.
Dynamic knowledge extraction is a v2+ feature.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..knowledge.index import KnowledgeIndex
from ..models.agent_message import AgentMessage, AgentType
from ..models.issue import Issue
from .base import BaseAgent

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    """Knowledge Agent - links issues to existing knowledge entries.

    Simplified for MVP: only matches issues against static knowledge base.
    Dynamic knowledge extraction is deferred to v2+.
    """

    agent_type = AgentType.KNOWLEDGE
    name = "KnowledgeAgent"

    def __init__(self, config: Any, knowledge_index: KnowledgeIndex):
        super().__init__(config)
        self.knowledge_index = knowledge_index

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Execute knowledge linking."""
        issues_data = message.payload.get("issues", [])
        issues = [Issue.model_validate(i) for i in issues_data]

        # Link existing knowledge to issues
        linked_issues = self._link_knowledge(issues)

        return AgentMessage.create_result(self.agent_type, linked_issues)

    def _link_knowledge(self, issues: list[Issue]) -> list[Issue]:
        """Link existing knowledge entries to issues."""
        for issue in issues:
            # Search for matching knowledge by category
            matching_entries = self.knowledge_index.search(category=issue.category)

            # Match by title keywords
            issue_keywords = set(issue.title.lower().split())
            for entry in matching_entries:
                entry_keywords = set(entry.title.lower().split())
                overlap = issue_keywords & entry_keywords
                if len(overlap) >= 1:
                    if entry.id not in issue.knowledge_ids:
                        issue.knowledge_ids.append(entry.id)
                        self.knowledge_index.increment_trigger(entry.id)

        return issues
