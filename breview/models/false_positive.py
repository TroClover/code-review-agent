"""False positive models for tracking developer-marked false positives."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FalsePositiveEntry(BaseModel):
    """A single false positive record."""

    issue_title: str = Field(description="Title of the issue marked as false positive")
    file_path: str = Field(default="", description="File path (empty = applies to all files)")
    category: str = Field(default="", description="Issue category (empty = applies to all categories)")
    marked_by: str = Field(description="Username who marked it as false positive")
    marked_at: datetime = Field(default_factory=datetime.utcnow)
    reason: Optional[str] = Field(default=None, description="Optional reason for marking as false positive")


class FalsePositiveStore(BaseModel):
    """Store for false positive records, persisted as JSON."""

    entries: list[FalsePositiveEntry] = Field(default_factory=list)
    file_path: Optional[str] = Field(default=None, description="Path to persistence file")

    def add(
        self,
        issue_title: str,
        file_path: str = "",
        category: str = "",
        marked_by: str = "unknown",
        reason: Optional[str] = None,
    ) -> FalsePositiveEntry:
        """Add a false positive entry."""
        entry = FalsePositiveEntry(
            issue_title=issue_title,
            file_path=file_path,
            category=category,
            marked_by=marked_by,
            reason=reason,
        )
        self.entries.append(entry)
        self._save()
        return entry

    def is_false_positive(self, issue_title: str, file_path: str = "", category: str = "") -> bool:
        """Check if an issue matches any false positive entry."""
        for entry in self.entries:
            if entry.issue_title == issue_title:
                # If entry has no file_path filter, it applies to all files
                if not entry.file_path or entry.file_path == file_path:
                    # If entry has no category filter, it applies to all categories
                    if not entry.category or entry.category == category:
                        return True
        return False

    def get_stats(self) -> dict:
        """Get false positive statistics."""
        return {
            "total": len(self.entries),
            "by_category": self._count_by_field("category"),
            "by_file": self._count_by_field("file_path"),
        }

    def _count_by_field(self, field: str) -> dict[str, int]:
        """Count entries by a specific field."""
        counts: dict[str, int] = {}
        for entry in self.entries:
            value = getattr(entry, field, "") or "all"
            counts[value] = counts.get(value, 0) + 1
        return counts

    def _save(self) -> None:
        """Save to file if file_path is set."""
        if not self.file_path:
            return
        try:
            import json
            from pathlib import Path

            path = Path(self.file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, indent=2, default=str)
        except Exception:
            pass  # Best effort save

    @classmethod
    def load(cls, file_path: str) -> "FalsePositiveStore":
        """Load from a JSON file."""
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            return cls(file_path=file_path)

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            store = cls.model_validate(data)
            store.file_path = file_path
            return store
        except Exception:
            return cls(file_path=file_path)
