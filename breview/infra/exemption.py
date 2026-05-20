"""Review exemption system - skip certain files, lines, or PRs from review."""

from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExemptionConfig:
    """Configuration for review exemptions."""

    file_patterns: list[str] = field(default_factory=lambda: [
        "*.pb.cc", "*.pb.h",
        "*.generated.*",
        "vendor/**", "third_party/**",
        "*.min.js", "*.min.css",
        "*.lock",
    ])
    inline_marker: str = "breview: ignore"
    pr_marker: str = "breview: skip"


class ExemptionChecker:
    """Checks whether files, lines, or PRs should be exempt from review."""

    def __init__(self, config: Optional[ExemptionConfig] = None):
        self.config = config or ExemptionConfig()

    def is_file_exempt(self, file_path: str) -> bool:
        """Check if a file should be entirely skipped.

        Args:
            file_path: Relative path to the file

        Returns:
            True if the file should be skipped
        """
        for pattern in self.config.file_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                logger.debug(f"File exempt: {file_path} matches pattern {pattern}")
                return True
            # Also check with ** glob
            if "**" in pattern:
                prefix = pattern.replace("**", "")
                if file_path.startswith(prefix):
                    return True
        return False

    def is_line_exempt(self, line_content: str) -> bool:
        """Check if a specific line is exempt from review.

        Looks for inline markers like `# breview: ignore`.

        Args:
            line_content: Content of the line

        Returns:
            True if the line should be skipped
        """
        return self.config.inline_marker in line_content.lower()

    def is_pr_exempt(self, pr_description: str) -> bool:
        """Check if an entire PR is exempt from review.

        Looks for markers in the PR description like `breview: skip`.

        Args:
            pr_description: PR description/body text

        Returns:
            True if the PR should be skipped
        """
        return self.config.pr_marker in pr_description.lower()

    def filter_diff_lines(
        self,
        lines: list[dict],
    ) -> list[dict]:
        """Filter out exempt lines from a list of changed lines.

        Args:
            lines: List of changed line dicts with 'content' key

        Returns:
            Filtered list with exempt lines removed
        """
        return [
            line for line in lines
            if not self.is_line_exempt(line.get("content", ""))
        ]
