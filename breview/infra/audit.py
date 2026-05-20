"""Audit logging for all review operations."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs all review operations for traceability.

    Every review action is logged with:
    - Who triggered it (user/bot)
    - What was reviewed (repo, PR, files)
    - What was found (issues, severity counts)
    - Outcome (approved/blocked)
    """

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path.home() / ".breview" / "audit"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._setup_file_logger()

    def _setup_file_logger(self) -> None:
        """Set up file-based audit logger."""
        self._logger = logging.getLogger("breview.audit")
        self._logger.setLevel(logging.INFO)

        log_file = self.log_dir / "audit.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    def log_review_start(
        self,
        review_id: str,
        repo: str,
        pr_number: int,
        author: str,
        trigger: str,
    ) -> None:
        """Log the start of a review."""
        self._log("REVIEW_START", review_id, {
            "repo": repo,
            "pr_number": pr_number,
            "author": author,
            "trigger": trigger,
        })

    def log_review_complete(
        self,
        review_id: str,
        repo: str,
        pr_number: int,
        issue_count: int,
        severity_counts: dict[str, int],
        is_approved: bool,
        agents_executed: list[str],
        agents_failed: list[str],
        duration_seconds: float,
    ) -> None:
        """Log the completion of a review."""
        self._log("REVIEW_COMPLETE", review_id, {
            "repo": repo,
            "pr_number": pr_number,
            "issue_count": issue_count,
            "severity_counts": severity_counts,
            "is_approved": is_approved,
            "agents_executed": agents_executed,
            "agents_failed": agents_failed,
            "duration_seconds": round(duration_seconds, 2),
        })

    def log_agent_result(
        self,
        review_id: str,
        agent_name: str,
        issue_count: int,
        duration_seconds: float,
        error: Optional[str] = None,
    ) -> None:
        """Log the result of a single agent."""
        self._log("AGENT_RESULT", review_id, {
            "agent": agent_name,
            "issue_count": issue_count,
            "duration_seconds": round(duration_seconds, 2),
            "error": error,
        })

    def log_feedback(
        self,
        review_id: str,
        issue_id: str,
        is_helpful: bool,
        user: str,
    ) -> None:
        """Log developer feedback on a review comment."""
        self._log("FEEDBACK", review_id, {
            "issue_id": issue_id,
            "is_helpful": is_helpful,
            "user": user,
        })

    def _log(self, event_type: str, review_id: str, data: dict[str, Any]) -> None:
        """Write an audit log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event_type,
            "review_id": review_id,
            **data,
        }
        self._logger.info(json.dumps(entry, default=str))
