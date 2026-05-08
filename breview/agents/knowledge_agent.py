"""Knowledge Agent - extracts knowledge from reviews and links to issues."""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..knowledge.index import KnowledgeIndex
from ..llm.client import LLMClient
from ..llm.prompts import build_knowledge_extraction_prompt
from ..models.agent_message import AgentMessage, AgentType
from ..models.issue import Issue
from .base import BaseAgent

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    """Knowledge Agent - extracts knowledge patterns and links them to issues.

    Responsibilities:
    1. Match issues to existing knowledge entries
    2. Extract new knowledge patterns from repeated issues
    3. Update knowledge base
    """

    agent_type = AgentType.KNOWLEDGE
    name = "KnowledgeAgent"

    def __init__(self, config: Any, knowledge_index: KnowledgeIndex, llm_client: Optional[LLMClient] = None):
        super().__init__(config)
        self.knowledge_index = knowledge_index
        self.llm_client = llm_client

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Execute knowledge extraction and linking."""
        issues_data = message.payload.get("issues", [])
        request_data = message.payload.get("request", {})

        issues = [Issue.model_validate(i) for i in issues_data]

        # Step 1: Link existing knowledge to issues
        linked_issues = self._link_knowledge(issues)

        # Step 2: Check for patterns worth extracting as new knowledge
        if self.llm_client:
            await self._extract_new_knowledge(linked_issues)

        return AgentMessage.create_result(self.agent_type, linked_issues)

    def _link_knowledge(self, issues: list[Issue]) -> list[Issue]:
        """Link existing knowledge entries to issues."""
        for issue in issues:
            # Search for matching knowledge by category and keywords
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

    async def _extract_new_knowledge(self, issues: list[Issue]) -> None:
        """Extract new knowledge patterns from issues using LLM."""
        if not issues:
            return

        # Get existing knowledge for deduplication
        existing = self.knowledge_index.search()
        existing_dicts = [
            {"id": e.id, "title": e.title, "category": e.category}
            for e in existing[:20]
        ]

        issues_dicts = [i.model_dump() for i in issues]

        messages = build_knowledge_extraction_prompt(issues_dicts, existing_dicts)

        try:
            response = await self.llm_client.complete(
                messages=messages,
                model=self.config.llm.model if hasattr(self.config, "llm") else "gpt-4o-mini",
                temperature=0.1,
                max_tokens=2048,
            )
            self._save_extracted_knowledge(response.content)
        except Exception as e:
            logger.warning(f"Knowledge extraction failed: {e}")

    def _save_extracted_knowledge(self, llm_output: str) -> None:
        """Parse and save extracted knowledge entries."""
        import json
        import re
        import uuid

        # Extract JSON from response
        json_match = re.search(r"\[.*\]", llm_output, re.DOTALL)
        if not json_match:
            return

        try:
            entries = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return

        from ..models.knowledge import KnowledgeEntry, KnowledgeGranularity, KnowledgeType

        threshold = getattr(self.config.knowledge, "auto_generate_threshold", 3) if hasattr(self.config, "knowledge") else 3

        for entry_data in entries:
            related_count = len(entry_data.get("related_issue_ids", []))
            if related_count < threshold:
                continue  # Not enough occurrences yet

            entry = KnowledgeEntry(
                id=f"KB-{uuid.uuid4().hex[:8]}",
                title=entry_data.get("title", "Extracted knowledge"),
                description=entry_data.get("description", ""),
                knowledge_type=KnowledgeType.ISSUE_PATTERN,
                granularity=KnowledgeGranularity.TEAM,
                category=entry_data.get("category", "general"),
                source="agent_review",
                source_weight=1.0,
                trigger_count=related_count,
            )
            self.knowledge_index.add(entry)
            logger.info(f"Extracted new knowledge: {entry.id} - {entry.title}")
