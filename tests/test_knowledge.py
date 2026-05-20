"""Tests for the knowledge system."""

import tempfile
from pathlib import Path

import pytest

from breview.knowledge.index import KnowledgeIndex
from breview.models.knowledge import KnowledgeEntry, KnowledgeGranularity, KnowledgeType


class TestKnowledgeIndex:
    """Tests for the knowledge index."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.index = KnowledgeIndex(storage_path=Path(self.tmp_dir))

    def test_add_and_get(self):
        entry = KnowledgeEntry(
            id="TEST-001",
            title="Test entry",
            description="A test knowledge entry",
            knowledge_type=KnowledgeType.CODING_STANDARD,
            granularity=KnowledgeGranularity.TEAM,
            category="naming",
            source="manual",
        )
        self.index.add(entry)
        result = self.index.get("TEST-001")
        assert result is not None
        assert result.title == "Test entry"

    def test_search_by_category(self):
        self.index.add(KnowledgeEntry(
            id="T1", title="Naming rule", description="d",
            knowledge_type=KnowledgeType.CODING_STANDARD,
            granularity=KnowledgeGranularity.TEAM,
            category="naming", source="manual",
        ))
        self.index.add(KnowledgeEntry(
            id="T2", title="Security rule", description="d",
            knowledge_type=KnowledgeType.CODING_STANDARD,
            granularity=KnowledgeGranularity.TEAM,
            category="security", source="manual",
        ))
        results = self.index.search(category="naming")
        assert len(results) == 1
        assert results[0].id == "T1"

    def test_search_by_developer(self):
        self.index.add(KnowledgeEntry(
            id="T3", title="Personal gap", description="d",
            knowledge_type=KnowledgeType.PERSONAL_GAP,
            granularity=KnowledgeGranularity.PERSONAL,
            category="error_handling", source="agent_review",
            target_developer="intern-001",
        ))
        results = self.index.search(developer="intern-001")
        assert len(results) == 1
        assert results[0].target_developer == "intern-001"

    def test_load_from_document(self):
        doc = """## Naming Conventions

Use snake_case for variables.

## Error Handling

Never use bare except.
"""
        count = self.index.load_from_document(doc, source="manual")
        assert count == 2
        team_standards = self.index.get_team_standards()
        assert len(team_standards) == 2

    def test_increment_trigger(self):
        entry = KnowledgeEntry(
            id="T4", title="Test", description="d",
            knowledge_type=KnowledgeType.ISSUE_PATTERN,
            granularity=KnowledgeGranularity.TEAM,
            category="general", source="manual",
        )
        self.index.add(entry)
        self.index.increment_trigger("T4")
        self.index.increment_trigger("T4")
        result = self.index.get("T4")
        assert result is not None
        assert result.trigger_count == 2

    def test_persistence(self):
        entry = KnowledgeEntry(
            id="T5", title="Persistent", description="d",
            knowledge_type=KnowledgeType.CODING_STANDARD,
            granularity=KnowledgeGranularity.TEAM,
            category="general", source="manual",
        )
        self.index.add(entry)

        # Create a new index from the same storage
        index2 = KnowledgeIndex(storage_path=Path(self.tmp_dir))
        result = index2.get("T5")
        assert result is not None
        assert result.title == "Persistent"
