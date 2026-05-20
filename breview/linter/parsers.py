"""Parsers for linter output formats."""

from __future__ import annotations

import json
import logging
import re
import uuid

from ..models.issue import Issue, IssueLocation, Severity

logger = logging.getLogger(__name__)

# Mapping of linter severity to our severity
RUFF_SEVERITY_MAP = {
    "E": Severity.MINOR,  # pycodestyle errors
    "W": Severity.MINOR,  # pycodestyle warnings
    "F": Severity.MAJOR,  # pyflakes
    "B": Severity.MAJOR,  # flake8-bugbear
    "S": Severity.CRITICAL,  # flake8-bandit (security)
    "C": Severity.MINOR,  # conventions
    "I": Severity.INFO,  # isort
    "N": Severity.MINOR,  # naming
    "D": Severity.INFO,  # docstring
}

FLAKE8_SEVERITY_MAP = {
    "E": Severity.MINOR,
    "W": Severity.MINOR,
    "F": Severity.MAJOR,
    "B": Severity.MAJOR,
    "S": Severity.CRITICAL,
    "C": Severity.MINOR,
}


def parse_ruff_output(output: str, file_path: str) -> list[Issue]:
    """Parse ruff JSON output format.

    Ruff output format (JSON):
    [
      {
        "code": "F401",
        "message": "'os' imported but unused",
        "fix": { ... },
        "location": { "row": 1, "column": 0 },
        "end_location": { "row": 1, "column": 2 },
        "filename": "example.py"
      }
    ]
    """
    issues: list[Issue] = []

    if not output.strip():
        return issues

    try:
        # Try JSON format first
        data = json.loads(output)
        if isinstance(data, list):
            for item in data:
                issue = _parse_ruff_json_item(item, file_path)
                if issue:
                    issues.append(issue)
            return issues
    except json.JSONDecodeError:
        pass

    # Fall back to text format parsing
    # ruff text format: file.py:1:1: F401 'os' imported but unused
    pattern = re.compile(r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$")
    for line in output.strip().split("\n"):
        match = pattern.match(line.strip())
        if match:
            _, row, col, code, message = match.groups()
            severity = _get_ruff_severity(code)
            issues.append(Issue(
                id=f"LINT-{uuid.uuid4().hex[:8]}",
                title=f"{code}: {message[:50]}",
                description=message,
                severity=severity,
                category="style",
                location=IssueLocation(
                    file_path=file_path,
                    line_start=int(row),
                ),
                source_agent="linter",
                confidence=1.0,
            ))

    return issues


def _parse_ruff_json_item(item: dict, file_path: str) -> Issue | None:
    """Parse a single ruff JSON item."""
    code = item.get("code", "")
    message = item.get("message", "")
    location = item.get("location", {})
    row = location.get("row", 0)

    severity = _get_ruff_severity(code)

    return Issue(
        id=f"LINT-{uuid.uuid4().hex[:8]}",
        title=f"{code}: {message[:50]}",
        description=message,
        severity=severity,
        category="style",
        location=IssueLocation(
            file_path=file_path,
            line_start=row,
        ),
        source_agent="linter",
        confidence=1.0,
    )


def _get_ruff_severity(code: str) -> Severity:
    """Map ruff error code to severity."""
    prefix = code[0] if code else ""
    return RUFF_SEVERITY_MAP.get(prefix, Severity.MINOR)


def parse_flake8_output(output: str, file_path: str) -> list[Issue]:
    """Parse flake8 output format.

    flake8 text format: ./path/file.py:1:1: F401 'os' imported but unused
    """
    issues: list[Issue] = []

    if not output.strip():
        return issues

    pattern = re.compile(r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$")
    for line in output.strip().split("\n"):
        match = pattern.match(line.strip())
        if match:
            _, row, col, code, message = match.groups()
            severity = _get_flake8_severity(code)
            issues.append(Issue(
                id=f"LINT-{uuid.uuid4().hex[:8]}",
                title=f"{code}: {message[:50]}",
                description=message,
                severity=severity,
                category="style",
                location=IssueLocation(
                    file_path=file_path,
                    line_start=int(row),
                ),
                source_agent="linter",
                confidence=1.0,
            ))

    return issues


def _get_flake8_severity(code: str) -> Severity:
    """Map flake8 error code to severity."""
    prefix = code[0] if code else ""
    return FLAKE8_SEVERITY_MAP.get(prefix, Severity.MINOR)


def parse_clang_tidy_output(output: str, file_path: str) -> list[Issue]:
    """Parse clang-tidy output format.

    clang-tidy text format:
    /path/file.cpp:1:10: warning: message [check-name]
    /path/file.cpp:5:3: error: message [check-name]
    """
    issues: list[Issue] = []

    if not output.strip():
        return issues

    # Pattern: file:line:col: severity: message [check-name]
    pattern = re.compile(r"^(.+?):(\d+):(\d+):\s+(warning|error|note):\s+(.+?)(?:\s+\[([^\]]+)\])?$")
    for line in output.strip().split("\n"):
        match = pattern.match(line.strip())
        if match:
            _, row, col, severity_str, message, check_name = match.groups()

            if severity_str == "error":
                severity = Severity.MAJOR
            elif severity_str == "warning":
                severity = Severity.MINOR
            else:
                severity = Severity.INFO

            title = f"{check_name}: {message[:50]}" if check_name else message[:60]

            issues.append(Issue(
                id=f"LINT-{uuid.uuid4().hex[:8]}",
                title=title,
                description=message,
                severity=severity,
                category="style",
                location=IssueLocation(
                    file_path=file_path,
                    line_start=int(row),
                ),
                source_agent="linter",
                confidence=1.0,
            ))

    return issues
