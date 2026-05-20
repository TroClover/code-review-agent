"""False positive filter - removes known false positives from issue list."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models.issue import Issue

if TYPE_CHECKING:
    from .store import FalsePositiveStore

logger = logging.getLogger(__name__)


def filter_false_positives(issues: list[Issue], store: FalsePositiveStore) -> list[Issue]:
    """Filter out issues that are known false positives.

    Args:
        issues: List of issues to filter
        store: False positive store

    Returns:
        Filtered list with false positives removed
    """
    if not issues:
        return issues

    filtered = []
    removed_count = 0

    for issue in issues:
        if store.is_false_positive(
            issue_title=issue.title,
            file_path=issue.location.file_path,
            category=issue.category,
        ):
            removed_count += 1
            logger.debug(f"Filtered false positive: {issue.title} in {issue.location.file_path}")
        else:
            filtered.append(issue)

    if removed_count > 0:
        logger.info(f"Filtered {removed_count} false positives from {len(issues)} issues")

    return filtered
