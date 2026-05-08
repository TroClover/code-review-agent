"""Git diff parser - extracts structured change information from unified diffs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ChangeType(str, Enum):
    """Type of file change."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class ChangedLine:
    """A single changed line in a diff."""

    line_number: int
    content: str
    is_addition: bool  # True = added line, False = removed line


@dataclass
class Hunk:
    """A hunk in a diff - a contiguous block of changes."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str = ""
    changed_lines: list[ChangedLine] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)


@dataclass
class FileChange:
    """A single file's changes in a diff."""

    old_path: Optional[str]
    new_path: str
    change_type: ChangeType
    hunks: list[Hunk] = field(default_factory=list)
    is_binary: bool = False

    @property
    def changed_line_numbers(self) -> list[int]:
        """All changed line numbers in the new version."""
        lines = []
        for hunk in self.hunks:
            for cl in hunk.changed_lines:
                if cl.is_addition:
                    lines.append(cl.line_number)
        return sorted(set(lines))

    @property
    def total_additions(self) -> int:
        return sum(1 for h in self.hunks for cl in h.changed_lines if cl.is_addition)

    @property
    def total_deletions(self) -> int:
        return sum(1 for h in self.hunks for cl in h.changed_lines if not cl.is_addition)


@dataclass
class ParsedDiff:
    """Complete parsed diff result."""

    files: list[FileChange] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_additions(self) -> int:
        return sum(f.total_additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.total_deletions for f in self.files)


class DiffParser:
    """Parses unified diff format into structured data."""

    # Regex patterns for unified diff
    _FILE_HEADER = re.compile(r"^diff --git (?:a/)?(.+?) (?:b/)?(.+?)$")
    _HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
    _BINARY_FILE = re.compile(r"^Binary files .+ and .+ differ$")

    def parse(self, diff_text: str) -> ParsedDiff:
        """Parse a unified diff string into structured data.

        Args:
            diff_text: Raw unified diff output from git

        Returns:
            ParsedDiff with all file changes structured
        """
        result = ParsedDiff()
        if not diff_text.strip():
            return result

        lines = diff_text.split("\n")
        current_file: Optional[FileChange] = None
        current_hunk: Optional[Hunk] = None

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for file header
            file_match = self._FILE_HEADER.match(line)
            if file_match:
                if current_file:
                    result.files.append(current_file)
                old_path = file_match.group(1)
                new_path = file_match.group(2)
                change_type = self._detect_change_type(old_path, new_path, lines, i)
                current_file = FileChange(
                    old_path=old_path,
                    new_path=new_path,
                    change_type=change_type,
                )
                current_hunk = None
                i += 1
                continue

            # Check for binary file
            if self._BINARY_FILE.match(line):
                if current_file:
                    current_file.is_binary = True
                i += 1
                continue

            # Check for hunk header
            hunk_match = self._HUNK_HEADER.match(line)
            if hunk_match and current_file:
                if current_hunk:
                    current_file.hunks.append(current_hunk)
                current_hunk = Hunk(
                    old_start=int(hunk_match.group(1)),
                    old_count=int(hunk_match.group(2) or "1"),
                    new_start=int(hunk_match.group(3)),
                    new_count=int(hunk_match.group(4) or "1"),
                    header=hunk_match.group(5).strip(),
                )
                i += 1
                continue

            # Process hunk content
            if current_hunk and current_file:
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk.changed_lines.append(
                        ChangedLine(
                            line_number=current_hunk.new_start + len(current_hunk.context_lines) + len(
                                [cl for cl in current_hunk.changed_lines if cl.is_addition]
                            ),
                            content=line[1:],
                            is_addition=True,
                        )
                    )
                elif line.startswith("-") and not line.startswith("---"):
                    current_hunk.changed_lines.append(
                        ChangedLine(
                            line_number=current_hunk.old_start + len(current_hunk.context_lines),
                            content=line[1:],
                            is_addition=False,
                        )
                    )
                elif line.startswith(" ") or line == "":
                    current_hunk.context_lines.append(line[1:] if line.startswith(" ") else "")

            i += 1

        # Don't forget the last file/hunk
        if current_hunk and current_file:
            current_file.hunks.append(current_hunk)
        if current_file:
            result.files.append(current_file)

        return result

    def _detect_change_type(self, old_path: str, new_path: str, lines: list[str], start_idx: int) -> ChangeType:
        """Detect the type of change from diff headers."""
        # Look ahead for rename/delete markers
        for j in range(start_idx + 1, min(start_idx + 5, len(lines))):
            if lines[j].startswith("new file"):
                return ChangeType.ADDED
            if lines[j].startswith("deleted file"):
                return ChangeType.DELETED
            if lines[j].startswith("rename from"):
                return ChangeType.RENAMED
        if old_path != new_path:
            return ChangeType.RENAMED
        return ChangeType.MODIFIED
