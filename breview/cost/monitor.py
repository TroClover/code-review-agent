"""Cost monitor - tracks and reports LLM usage costs."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ReviewCostRecord:
    """Cost record for a single review."""

    review_id: str
    timestamp: float
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    files_reviewed: int
    duration_seconds: float


@dataclass
class DiffCacheEntry:
    """Cache entry for a reviewed diff."""

    diff_hash: str
    file_path: str
    issues_json: str
    timestamp: float
    cost_usd: float


class CostMonitor:
    """Monitors and controls LLM review costs."""

    def __init__(
        self,
        max_cost_per_review: float = 1.0,
        enable_cache: bool = True,
        cache_ttl_hours: int = 24,
        cache_dir: Optional[str] = None,
    ):
        self.max_cost_per_review = max_cost_per_review
        self.enable_cache = enable_cache
        self.cache_ttl_seconds = cache_ttl_hours * 3600
        self.cache_dir = Path(cache_dir) if cache_dir else None

        self._current_cost: float = 0.0
        self._current_tokens: int = 0
        self._records: list[ReviewCostRecord] = []
        self._cache: dict[str, DiffCacheEntry] = {}

        if self.cache_dir:
            self._load_cache()

    def check_budget(self) -> bool:
        """Check if we're still within budget."""
        return self._current_cost < self.max_cost_per_review

    def record_usage(self, input_tokens: int, output_tokens: int, cost_usd: float, model: str) -> None:
        """Record LLM usage."""
        self._current_cost += cost_usd
        self._current_tokens += input_tokens + output_tokens

        if self._current_cost >= self.max_cost_per_review:
            logger.warning(
                f"Cost limit reached: ${self._current_cost:.4f} >= ${self.max_cost_per_review:.4f}"
            )

    def record_review(
        self,
        review_id: str,
        total_tokens: int,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        model: str,
        files_reviewed: int,
        duration_seconds: float,
    ) -> None:
        """Record a complete review's cost."""
        record = ReviewCostRecord(
            review_id=review_id,
            timestamp=time.time(),
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            model=model,
            files_reviewed=files_reviewed,
            duration_seconds=duration_seconds,
        )
        self._records.append(record)

    def get_cost_summary(self) -> dict:
        """Get current cost summary."""
        return {
            "current_review_cost_usd": round(self._current_cost, 4),
            "current_review_tokens": self._current_tokens,
            "max_cost_per_review_usd": self.max_cost_per_review,
            "remaining_budget_usd": round(max(0, self.max_cost_per_review - self._current_cost), 4),
            "budget_exceeded": self._current_cost >= self.max_cost_per_review,
        }

    def get_historical_report(self) -> dict:
        """Get historical cost report."""
        if not self._records:
            return {"total_reviews": 0, "total_cost_usd": 0, "total_tokens": 0}

        total_cost = sum(r.cost_usd for r in self._records)
        total_tokens = sum(r.total_tokens for r in self._records)

        return {
            "total_reviews": len(self._records),
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "avg_cost_per_review_usd": round(total_cost / len(self._records), 4),
            "avg_tokens_per_review": total_tokens // len(self._records),
        }

    # Cache methods

    def get_cached_result(self, diff_content: str, file_path: str) -> Optional[str]:
        """Get cached review result for a diff."""
        if not self.enable_cache:
            return None

        diff_hash = self._hash_diff(diff_content)
        entry = self._cache.get(f"{file_path}:{diff_hash}")

        if entry is None:
            return None

        # Check TTL
        if time.time() - entry.timestamp > self.cache_ttl_seconds:
            del self._cache[f"{file_path}:{diff_hash}"]
            return None

        logger.info(f"Cache hit for {file_path}")
        return entry.issues_json

    def cache_result(self, diff_content: str, file_path: str, issues_json: str, cost_usd: float = 0.0) -> None:
        """Cache a review result."""
        if not self.enable_cache:
            return

        diff_hash = self._hash_diff(diff_content)
        entry = DiffCacheEntry(
            diff_hash=diff_hash,
            file_path=file_path,
            issues_json=issues_json,
            timestamp=time.time(),
            cost_usd=cost_usd,
        )
        self._cache[f"{file_path}:{diff_hash}"] = entry

        if self.cache_dir:
            self._save_cache()

    def _hash_diff(self, diff_content: str) -> str:
        """Hash diff content for cache key."""
        return hashlib.sha256(diff_content.encode()).hexdigest()[:16]

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / "review_cache.json"
        if not cache_file.exists():
            return

        try:
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
            for key, entry_data in data.items():
                self._cache[key] = DiffCacheEntry(**entry_data)
            logger.info(f"Loaded {len(self._cache)} cache entries")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")

    def _save_cache(self) -> None:
        """Save cache to disk."""
        if not self.cache_dir:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / "review_cache.json"

        try:
            data = {k: vars(v) for k, v in self._cache.items()}
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
