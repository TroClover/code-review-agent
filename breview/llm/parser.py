"""Parser for LLM review output into structured Issue objects."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

from ..models.issue import Issue, IssueLocation, Severity

logger = logging.getLogger(__name__)


def parse_llm_issues(
    llm_output: str,
    source_agent: str,
    file_path: str,
    base_line: int = 1,
) -> list[Issue]:
    """Parse LLM JSON output into structured Issue objects.

    Args:
        llm_output: Raw LLM response (should be JSON array)
        source_agent: Which agent produced this output
        file_path: File being reviewed
        base_line: Base line number offset

    Returns:
        List of parsed Issue objects
    """
    # Extract JSON from response (handle markdown code blocks)
    json_str = _extract_json(llm_output)

    try:
        raw_issues = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM output as JSON: {e}")
        logger.debug(f"Raw output: {llm_output[:500]}")
        return []

    if not isinstance(raw_issues, list):
        logger.warning(f"Expected JSON array, got {type(raw_issues).__name__}")
        return []

    issues: list[Issue] = []
    for raw in raw_issues:
        issue = _convert_to_issue(raw, source_agent, file_path, base_line)
        if issue:
            issues.append(issue)

    return issues


def _extract_json(text: str) -> str:
    """Extract JSON from text, handling markdown code blocks and truncated responses."""
    # Try to find JSON in code blocks
    json_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_block:
        return json_block.group(1).strip()

    # Try to find raw JSON array
    json_match = re.search(r"\[.*\]", text, re.DOTALL)
    if json_match:
        return json_match.group(0)

    # Try to fix truncated JSON (missing closing brackets)
    text = text.strip()
    if text.startswith("[") and not text.endswith("]"):
        # Try to close the JSON array
        # Count open/close braces
        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")

        # Remove trailing incomplete object
        last_complete = text.rfind("}")
        if last_complete > 0:
            text = text[:last_complete + 1]

        # Add closing brackets
        text += "]" * max(1, open_brackets)
        if open_braces > 0:
            text = text.rstrip("]") + "}" * open_braces + "]"

        logger.warning("Attempted to fix truncated JSON response")
        return text

    # Return as-is and hope for the best
    return text.strip()


def _convert_to_issue(
    raw: dict[str, Any],
    source_agent: str,
    file_path: str,
    base_line: int,
) -> Optional[Issue]:
    """Convert a raw dict from LLM output to an Issue object."""
    try:
        title = raw.get("title", "Untitled issue")
        description = raw.get("description", "")
        if not description:
            description = title

        # Parse severity with fallback
        severity_str = raw.get("severity", "minor").lower()
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.MINOR

        # Parse location
        line_number = raw.get("line_number", raw.get("line", base_line))
        if isinstance(line_number, str):
            line_number = int(re.search(r"\d+", line_number).group()) if re.search(r"\d+", line_number) else base_line

        location = IssueLocation(
            file_path=file_path,
            line_start=line_number + base_line - 1 if base_line > 1 else line_number,
            function_name=raw.get("function_name"),
        )

        # Parse category
        category = raw.get("category", _infer_category(source_agent, severity))

        # Suggestion
        suggestion = raw.get("suggestion", raw.get("fix"))

        # Code snippet
        code_snippet = raw.get("code_snippet", raw.get("code"))

        return Issue(
            id=f"{source_agent.upper()}-{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            severity=severity,
            category=category,
            location=location,
            suggestion=suggestion,
            code_snippet=code_snippet,
            source_agent=source_agent,
        )
    except Exception as e:
        logger.warning(f"Failed to convert raw issue to Issue: {e}")
        return None


def _infer_category(source_agent: str, severity: Severity) -> str:
    """Infer issue category from source agent."""
    category_map = {
        "style": "style",
        "code_review": "logic",
        "safety": "safety",
    }
    return category_map.get(source_agent, "general")
