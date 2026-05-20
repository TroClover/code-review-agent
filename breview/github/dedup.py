"""Result deduplication - prevents duplicate review comments."""

from __future__ import annotations

import logging
from typing import Any

from ..models.issue import Issue

logger = logging.getLogger(__name__)


def deduplicate_issues(
    new_issues: list[Issue],
    existing_comments: list[dict[str, Any]],
) -> list[Issue]:
    """Remove issues that already have corresponding comments on the PR.

    Args:
        new_issues: List of new issues from review
        existing_comments: List of existing PR comments (dicts with 'path', 'line', 'body')

    Returns:
        Filtered list with duplicates removed
    """
    if not existing_comments:
        return new_issues

    # Build a set of existing issue signatures
    existing_signatures: set[str] = set()
    for comment in existing_comments:
        path = comment.get("path", "")
        line = comment.get("line", 0)
        body = comment.get("body", "")

        # Extract title from comment body (first line after emoji)
        title = _extract_title_from_body(body)
        if title:
            sig = f"{path}:{line}:{title}"
            existing_signatures.add(sig)

    # Filter out duplicates
    filtered = []
    removed_count = 0

    for issue in new_issues:
        sig = f"{issue.location.file_path}:{issue.location.line_start}:{issue.title}"
        if sig in existing_signatures:
            removed_count += 1
            logger.debug(f"Skipping duplicate issue: {issue.title}")
        else:
            filtered.append(issue)

    if removed_count > 0:
        logger.info(f"Removed {removed_count} duplicate issues")

    return filtered


def _extract_title_from_body(body: str) -> str:
    """Extract issue title from a PR comment body."""
    if not body:
        return ""

    # Look for pattern like: :rotating_light: **[CRITICAL]** Title here
    import re
    match = re.search(r"\*\*\[(?:CRITICAL|MAJOR|MINOR|INFO)\]\*\*\s*(.+?)(?:\n|$)", body)
    if match:
        return match.group(1).strip()

    # Fallback: use first line
    first_line = body.split("\n")[0].strip()
    # Remove common prefixes
    for prefix in [":rotating_light:", ":warning:", ":bulb:", ":information_source:"]:
        first_line = first_line.replace(prefix, "").strip()
    return first_line[:100]
