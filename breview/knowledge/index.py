"""Knowledge index for storing and retrieving knowledge entries."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.knowledge import KnowledgeEntry, KnowledgeGranularity, KnowledgeType

logger = logging.getLogger(__name__)


class KnowledgeIndex:
    """Knowledge base with indexed storage and retrieval.

    Supports two granularity levels:
    - Team-wide coding standards (coarse-grained)
    - Per-person/per-issue-type entries (fine-grained)
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".breview" / "knowledge"
        self._entries: dict[str, KnowledgeEntry] = {}
        self._category_index: dict[str, list[str]] = {}  # category → entry IDs
        self._developer_index: dict[str, list[str]] = {}  # developer → entry IDs
        self._load()

    def _load(self) -> None:
        """Load knowledge entries from storage."""
        index_file = self.storage_path / "index.json"
        if not index_file.exists():
            return
        try:
            with open(index_file) as f:
                data = json.load(f)
            for entry_data in data.get("entries", []):
                entry = KnowledgeEntry.model_validate(entry_data)
                self._entries[entry.id] = entry
                self._index_entry(entry)
            logger.info(f"Loaded {len(self._entries)} knowledge entries")
        except Exception as e:
            logger.error(f"Failed to load knowledge index: {e}")

    def _save(self) -> None:
        """Persist knowledge entries to storage."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        index_file = self.storage_path / "index.json"
        data = {
            "entries": [e.model_dump() for e in self._entries.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }
        with open(index_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _index_entry(self, entry: KnowledgeEntry) -> None:
        """Add entry to category and developer indexes."""
        if entry.category not in self._category_index:
            self._category_index[entry.category] = []
        self._category_index[entry.category].append(entry.id)

        if entry.target_developer:
            if entry.target_developer not in self._developer_index:
                self._developer_index[entry.target_developer] = []
            self._developer_index[entry.target_developer].append(entry.id)

    def add(self, entry: KnowledgeEntry) -> None:
        """Add or update a knowledge entry."""
        self._entries[entry.id] = entry
        self._index_entry(entry)
        self._save()
        logger.info(f"Added knowledge entry: {entry.id} - {entry.title}")

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get a knowledge entry by ID."""
        return self._entries.get(entry_id)

    def search(
        self,
        category: Optional[str] = None,
        developer: Optional[str] = None,
        granularity: Optional[KnowledgeGranularity] = None,
        knowledge_type: Optional[KnowledgeType] = None,
    ) -> list[KnowledgeEntry]:
        """Search knowledge entries by criteria."""
        results = list(self._entries.values())

        if category:
            results = [e for e in results if e.category == category]
        if developer:
            results = [e for e in results if e.target_developer == developer or e.granularity == KnowledgeGranularity.TEAM]
        if granularity:
            results = [e for e in results if e.granularity == granularity]
        if knowledge_type:
            results = [e for e in results if e.knowledge_type == knowledge_type]

        # Sort by weight * trigger_count (most relevant first)
        results.sort(key=lambda e: e.source_weight * e.trigger_count, reverse=True)
        return results

    def get_team_standards(self) -> list[KnowledgeEntry]:
        """Get all team-wide coding standards."""
        return self.search(granularity=KnowledgeGranularity.TEAM, knowledge_type=KnowledgeType.CODING_STANDARD)

    def get_developer_gaps(self, developer: str) -> list[KnowledgeEntry]:
        """Get knowledge gaps for a specific developer."""
        return self.search(developer=developer, granularity=KnowledgeGranularity.PERSONAL)

    def increment_trigger(self, entry_id: str) -> None:
        """Increment the trigger count for a knowledge entry."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.trigger_count += 1
            entry.updated_at = datetime.utcnow()
            self._save()

    def load_from_document(self, content: str, source: str = "manual") -> int:
        """Load knowledge entries from a markdown coding standard document.

        Parses structured markdown into individual knowledge entries.

        Returns:
            Number of entries loaded
        """
        import re
        import uuid

        sections = re.split(r"^## ", content, flags=re.MULTILINE)
        count = 0

        for section in sections:
            if not section.strip():
                continue
            lines = section.strip().split("\n")
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()

            if not body:
                continue

            # Detect category from title or section content
            category = self._detect_category(title, body)

            entry = KnowledgeEntry(
                id=f"KS-{uuid.uuid4().hex[:8]}",
                title=title,
                description=body,
                knowledge_type=KnowledgeType.CODING_STANDARD,
                granularity=KnowledgeGranularity.TEAM,
                category=category,
                source=source,
                source_weight=2.0 if source == "human" else 1.0,
            )
            self.add(entry)
            count += 1

        return count

    def _detect_category(self, title: str, body: str) -> str:
        """Detect category from title and body text."""
        title_lower = title.lower()
        body_lower = body.lower()
        combined = f"{title_lower} {body_lower}"

        if any(kw in combined for kw in ["naming", "命名", "convention"]):
            return "naming"
        if any(kw in combined for kw in ["format", "indent", "style", "格式"]):
            return "formatting"
        if any(kw in combined for kw in ["error", "exception", "错误", "异常"]):
            return "error_handling"
        if any(kw in combined for kw in ["security", "安全", "secret", "key"]):
            return "security"
        if any(kw in combined for kw in ["performance", "性能", "memory", "optimize"]):
            return "performance"
        if any(kw in combined for kw in ["safety", "sensor", "传感器", "仿真", "simulation"]):
            return "safety"
        if any(kw in combined for kw in ["import", "include", "依赖"]):
            return "imports"
        if any(kw in combined for kw in ["comment", "doc", "注释", "文档"]):
            return "documentation"
        return "general"
