"""Context builder - assembles LLM prompts from diff and surrounding code."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from ..diff.parser import FileChange, ParsedDiff

logger = logging.getLogger(__name__)

# Max lines of surrounding context to include
CONTEXT_LINES_BEFORE = 20
CONTEXT_LINES_AFTER = 10
MAX_FILE_LINES_FOR_FULL_REVIEW = 500


@dataclass
class FileContext:
    """Context for a single file to be reviewed."""

    file_path: str
    change_type: str
    diff_content: str
    surrounding_code: str = ""
    file_header: str = ""  # imports, top-level definitions
    function_signatures: list[str] = field(default_factory=list)
    total_lines: int = 0


@dataclass
class ReviewContext:
    """Complete context assembled for a review."""

    file_contexts: list[FileContext] = field(default_factory=list)
    pr_description: str = ""
    author_role: str = ""
    repo_info: str = ""


class ContextBuilder:
    """Builds review context from parsed diffs and repository information.

    This agent (Context Agent in the pipeline) is responsible for:
    1. Extracting changed code from diff
    2. Gathering surrounding context (function bodies, class definitions)
    3. Including file headers (imports)
    4. Building function signature lists
    5. Managing context window size
    """

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path

    def build_context(
        self,
        parsed_diff: ParsedDiff,
        pr_description: str = "",
        author_role: str = "",
    ) -> ReviewContext:
        """Build review context from parsed diff.

        Args:
            parsed_diff: Structured diff data
            pr_description: PR description text
            author_role: Author's role for context customization

        Returns:
            Assembled review context
        """
        context = ReviewContext(
            pr_description=pr_description,
            author_role=author_role,
        )

        for file_change in parsed_diff.files:
            if file_change.is_binary:
                continue

            file_ctx = self._build_file_context(file_change)
            context.file_contexts.append(file_ctx)

        return context

    def build_file_context_for_full_review(self, file_path: str, content: str) -> FileContext:
        """Build context for full file review (new files or explicit request).

        Args:
            file_path: Path to the file
            content: Full file content

        Returns:
            File context with full content
        """
        lines = content.split("\n")
        return FileContext(
            file_path=file_path,
            change_type="added",
            diff_content=content,
            surrounding_code="",
            file_header=self._extract_header(lines),
            function_signatures=self._extract_function_signatures(lines, file_path),
            total_lines=len(lines),
        )

    def _build_file_context(self, file_change: FileChange) -> FileContext:
        """Build context for a single file change."""
        diff_content = self._format_diff_hunks(file_change)

        # Try to read the actual file for surrounding context
        surrounding_code = ""
        file_header = ""
        function_signatures: list[str] = []
        total_lines = 0

        if self.repo_path and file_change.new_path:
            try:
                import os
                full_path = os.path.join(self.repo_path, file_change.new_path)
                if os.path.exists(full_path):
                    with open(full_path, encoding="utf-8", errors="replace") as f:
                        lines = f.read().split("\n")
                    total_lines = len(lines)
                    surrounding_code = self._extract_surrounding_context(
                        lines, file_change.changed_line_numbers
                    )
                    file_header = self._extract_header(lines)
                    function_signatures = self._extract_function_signatures(
                        lines, file_change.new_path
                    )
            except Exception as e:
                logger.warning(f"Could not read file {file_change.new_path}: {e}")

        return FileContext(
            file_path=file_change.new_path,
            change_type=file_change.change_type.value,
            diff_content=diff_content,
            surrounding_code=surrounding_code,
            file_header=file_header,
            function_signatures=function_signatures,
            total_lines=total_lines,
        )

    def _format_diff_hunks(self, file_change: FileChange) -> str:
        """Format diff hunks into readable text."""
        lines = [f"--- a/{file_change.old_path or '/dev/null'}"]
        lines.append(f"+++ b/{file_change.new_path}")

        for hunk in file_change.hunks:
            lines.append(
                f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@ {hunk.header}"
            )
            for ctx_line in hunk.context_lines:
                lines.append(f" {ctx_line}")
            for changed in hunk.changed_lines:
                prefix = "+" if changed.is_addition else "-"
                lines.append(f"{prefix}{changed.content}")

        return "\n".join(lines)

    def _extract_surrounding_context(
        self, lines: list[str], changed_line_numbers: list[int]
    ) -> str:
        """Extract surrounding code context for changed lines."""
        if not changed_line_numbers:
            return ""

        # Find ranges of changed lines with context
        context_ranges: list[tuple[int, int]] = []
        for line_no in changed_line_numbers:
            start = max(0, line_no - CONTEXT_LINES_BEFORE - 1)
            end = min(len(lines), line_no + CONTEXT_LINES_AFTER)
            context_ranges.append((start, end))

        # Merge overlapping ranges
        merged = self._merge_ranges(context_ranges)

        # Extract lines
        result_parts: list[str] = []
        for start, end in merged:
            result_parts.append(f"--- Lines {start + 1}-{end} ---")
            for i in range(start, end):
                marker = ">>>" if (i + 1) in changed_line_numbers else "   "
                result_parts.append(f"{marker} {i + 1:4d} | {lines[i]}")

        return "\n".join(result_parts)

    def _merge_ranges(self, ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Merge overlapping ranges."""
        if not ranges:
            return []
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]
        for start, end in sorted_ranges[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def _extract_header(self, lines: list[str]) -> str:
        """Extract file header (imports, module-level definitions)."""
        header_lines: list[str] = []
        for line in lines[:50]:  # Look at first 50 lines
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("import ", "from ", "#include", "#pragma", "using ")):
                header_lines.append(line)
            elif stripped.startswith(("#!", '"""', "'''", "# -*-")):
                header_lines.append(line)
            elif header_lines and not stripped.startswith(("#", "//")):
                break  # Stop at first non-import, non-comment line
        return "\n".join(header_lines[:30])

    def _extract_function_signatures(self, lines: list[str], file_path: str) -> list[str]:
        """Extract function/method signatures from the file."""
        import re

        signatures: list[str] = []
        is_python = file_path.endswith(".py")
        is_cpp = file_path.endswith((".cpp", ".cc", ".h", ".hpp"))

        if is_python:
            pattern = re.compile(r"^(\s*)(def|class)\s+(\w+)\s*\(")
            for line in lines:
                match = pattern.match(line)
                if match:
                    signatures.append(line.strip())
        elif is_cpp:
            # Simple C++ function signature detection
            pattern = re.compile(r"^\s*(?:[\w:]+\s+)*(\w+)\s*\([^)]*\)\s*(?:const)?\s*\{?")
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(("if", "for", "while", "switch", "return", "//", "/*", "*")):
                    continue
                match = pattern.match(stripped)
                if match and "(" in stripped:
                    signatures.append(stripped)

        return signatures[:50]  # Limit to 50 signatures
