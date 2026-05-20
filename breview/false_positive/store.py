"""False positive store - manages false positive records."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.false_positive import FalsePositiveEntry, FalsePositiveStore as FPStoreModel

logger = logging.getLogger(__name__)


class FalsePositiveStore:
    """Manages false positive records with persistence."""

    def __init__(self, storage_path: str = ".breview/false_positives.json"):
        self.storage_path = Path(storage_path)
        self._model = self._load()

    def add(
        self,
        issue_title: str,
        file_path: str = "",
        category: str = "",
        marked_by: str = "unknown",
        reason: Optional[str] = None,
    ) -> FalsePositiveEntry:
        """Add a false positive entry."""
        entry = self._model.add(
            issue_title=issue_title,
            file_path=file_path,
            category=category,
            marked_by=marked_by,
            reason=reason,
        )
        self._save()
        logger.info(f"Marked as false positive: {issue_title} (by {marked_by})")
        return entry

    def is_false_positive(self, issue_title: str, file_path: str = "", category: str = "") -> bool:
        """Check if an issue matches any false positive entry."""
        return self._model.is_false_positive(issue_title, file_path, category)

    def get_stats(self) -> dict:
        """Get false positive statistics."""
        return self._model.get_stats()

    def remove(self, issue_title: str, file_path: str = "") -> bool:
        """Remove a false positive entry."""
        original_count = len(self._model.entries)
        self._model.entries = [
            e for e in self._model.entries
            if not (e.issue_title == issue_title and (not file_path or e.file_path == file_path))
        ]
        if len(self._model.entries) < original_count:
            self._save()
            return True
        return False

    def list_all(self) -> list[FalsePositiveEntry]:
        """List all false positive entries."""
        return list(self._model.entries)

    def _load(self) -> FPStoreModel:
        """Load from file."""
        return FPStoreModel.load(str(self.storage_path))

    def _save(self) -> None:
        """Save to file."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._model.model_dump(), f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save false positives: {e}")
