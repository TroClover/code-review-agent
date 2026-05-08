"""Report generator for review results."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.review import ReviewResult


class ReportGenerator:
    """Generates structured review reports in various formats."""

    def generate_markdown(self, result: ReviewResult) -> str:
        """Generate a Markdown review report."""
        lines = [
            "# Code Review Report",
            "",
            f"**Repository:** {result.request.pr_info.repo_full_name}",
            f"**PR:** #{result.request.pr_info.pr_number} - {result.request.pr_info.title}",
            f"**Author:** {result.request.pr_info.author} ({result.request.pr_info.author_role.value})",
            f"**Date:** {result.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Duration:** {result.duration_seconds:.1f}s",
            "",
            "---",
            "",
            "## Summary",
            "",
            result.summary,
            "",
        ]

        if result.issues:
            lines.extend(["## Issues", ""])
            for issue in result.issues:
                lines.extend([
                    f"### [{issue.severity.value.upper()}] {issue.title}",
                    "",
                    f"**File:** `{issue.location.file_path}` (line {issue.location.line_start})",
                    f"**Agent:** {issue.source_agent}",
                    f"**Category:** {issue.category}",
                    "",
                    issue.description,
                    "",
                ])
                if issue.suggestion:
                    lines.extend(["**Suggestion:**", "", issue.suggestion, ""])
                if issue.code_snippet:
                    lines.extend(["```", issue.code_snippet, "```", ""])
                lines.append("---")
                lines.append("")

        lines.extend([
            "## Statistics",
            "",
            f"- Total issues: {len(result.issues)}",
            f"- Agents executed: {', '.join(result.agents_executed)}",
            f"- Agents skipped: {', '.join(result.agents_failed) if result.agents_failed else 'None'}",
            f"- Total tokens used: {result.total_tokens_used}",
            "",
        ])

        return "\n".join(lines)

    def generate_json(self, result: ReviewResult) -> str:
        """Generate a JSON review report."""
        data = {
            "pr": {
                "repo": result.request.pr_info.repo_full_name,
                "number": result.request.pr_info.pr_number,
                "title": result.request.pr_info.title,
                "author": result.request.pr_info.author,
                "role": result.request.pr_info.author_role.value,
            },
            "summary": result.summary,
            "issues": [
                {
                    "id": issue.id,
                    "title": issue.title,
                    "severity": issue.severity.value,
                    "category": issue.category,
                    "file": issue.location.file_path,
                    "line": issue.location.line_start,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "agent": issue.source_agent,
                    "knowledge_ids": issue.knowledge_ids,
                }
                for issue in result.issues
            ],
            "statistics": {
                "total_issues": len(result.issues),
                "severity_counts": result.severity_counts,
                "agents_executed": result.agents_executed,
                "agents_failed": result.agents_failed,
                "duration_seconds": result.duration_seconds,
                "total_tokens": result.total_tokens_used,
            },
            "is_approved": result.is_approved,
            "created_at": result.created_at.isoformat(),
        }
        return json.dumps(data, indent=2)

    def save_report(
        self,
        result: ReviewResult,
        output_dir: Path,
        format: str = "markdown",
    ) -> Path:
        """Save report to file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        pr_num = result.request.pr_info.pr_number

        if format == "json":
            filename = f"review_{pr_num}_{timestamp}.json"
            content = self.generate_json(result)
        else:
            filename = f"review_{pr_num}_{timestamp}.md"
            content = self.generate_markdown(result)

        filepath = output_dir / filename
        with open(filepath, "w") as f:
            f.write(content)

        return filepath
