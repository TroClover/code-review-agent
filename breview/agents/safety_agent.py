"""Safety Agent - reviews safety-critical code for autonomous driving."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

from ..diff.parser import DiffParser, ParsedDiff
from ..llm.client import LLMClient
from ..llm.parser import parse_llm_issues
from ..llm.prompts import build_safety_review_prompt
from ..models.agent_message import AgentMessage, AgentType
from ..models.issue import Issue, IssueLocation, Severity
from .base import BaseAgent

logger = logging.getLogger(__name__)

# Patterns that indicate safety-critical code
SAFETY_CRITICAL_PATTERNS = [
    # Sensor-related
    r"sensor", r"lidar", r"radar", r"camera", r"imu", r"gnss", r"gps",
    # Vehicle control
    r"trajectory", r"planning", r"control", r"steering", r"brake", r"throttle",
    # Safety systems
    r"safety", r"collision", r"emergency", r"fallback", r"degradation",
    # Simulation
    r"simulation", r"scenario", r"sim_config", r"world_model",
    # Data pipeline
    r"point_cloud", r"perception", r"detection", r"tracking", r"fusion",
]

SAFETY_CRITICAL_EXTENSIONS = (".py", ".cpp", ".cc", ".h", ".hpp")


class SafetyAgent(BaseAgent):
    """Safety Agent - reviews safety-critical code patterns.

    Focuses on:
    - Sensor data validation
    - Simulation configuration correctness
    - Safety-critical path error handling
    - Resource management
    - Concurrency safety
    """

    agent_type = AgentType.SAFETY
    name = "SafetyAgent"

    def __init__(self, config: Any, llm_client: LLMClient):
        super().__init__(config)
        self.llm_client = llm_client
        from ..context.builder import ContextBuilder
        self.context_builder = ContextBuilder()
        self._cost_monitor = None
        self._domain_enabled = False

    def set_cost_monitor(self, cost_monitor) -> None:
        """Set cost monitor for budget checking."""
        self._cost_monitor = cost_monitor

    def enable_domain_rules(self, enabled: bool = True) -> None:
        """Enable/disable autonomous driving domain rules."""
        self._domain_enabled = enabled

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Execute safety review on the diff."""
        request_data = message.payload.get("request", {})
        diff_content = request_data.get("diff_content", "")
        author_role = request_data.get("pr_info", {}).get("author_role", "full_time")

        parser = DiffParser()
        parsed_diff = parser.parse(diff_content)

        # Filter to safety-relevant files
        relevant_files = self._filter_safety_relevant(parsed_diff)

        if not relevant_files:
            return AgentMessage.create_result(self.agent_type, [])

        # Run static safety checks
        static_issues = self._run_static_checks(relevant_files)

        # Run LLM review for safety-relevant files
        llm_tasks = [
            self._review_file(file_change, author_role)
            for file_change in relevant_files
        ]
        llm_results = await asyncio.gather(*llm_tasks, return_exceptions=True)

        llm_issues: list[Issue] = []
        for result in llm_results:
            if isinstance(result, list):
                llm_issues.extend(result)

        return AgentMessage.create_result(self.agent_type, static_issues + llm_issues)

    def _filter_safety_relevant(self, parsed_diff: ParsedDiff) -> list:
        """Filter files that are safety-relevant.

        All code files are considered for safety review (general security checks).
        Domain-specific patterns only apply when domain rules are enabled.
        """
        relevant = []
        for file_change in parsed_diff.files:
            if file_change.is_binary:
                continue
            # All code files are relevant for general security checks
            if file_change.new_path.endswith(SAFETY_CRITICAL_EXTENSIONS):
                relevant.append(file_change)
        return relevant

    def _is_safety_critical(self, file_path: str) -> bool:
        """Check if a file is safety-critical based on path and name."""
        path_lower = file_path.lower()

        # Always check for general security patterns
        general_patterns = [
            r"auth", r"password", r"secret", r"token", r"key",
            r"security", r"crypto", r"hash", r"encrypt",
            r"sql", r"database", r"db",
            r"config", r"settings",
        ]
        if any(re.search(p, path_lower) for p in general_patterns):
            return True

        # Domain-specific patterns (only if enabled)
        if self._domain_enabled:
            return any(re.search(pattern, path_lower) for pattern in SAFETY_CRITICAL_PATTERNS)

        return False

    def _run_static_checks(self, files: list) -> list[Issue]:
        """Run static safety checks without LLM."""
        issues: list[Issue] = []

        for file_change in files:
            for hunk in file_change.hunks:
                for line in hunk.changed_lines:
                    if not line.is_addition:
                        continue
                    content = line.content

                    # Check: hardcoded file paths (simulation configs)
                    if re.search(r'["\']/data/|["\']/home/|["\']/opt/', content):
                        issues.append(self._make_safety_issue(
                            title="Hardcoded file path",
                            description="Hardcoded absolute path detected. Use environment variables or config files for paths.",
                            severity="major",
                            file_path=file_change.new_path,
                            line=line.line_number,
                            suggestion="Use os.environ['BRT_DATA_DIR'] or config file for paths.",
                        ))

                    # Check: missing sensor data validation
                    if re.search(r"\.(points|data|frame)\s*\.", content) and "validat" not in content.lower():
                        if file_change.new_path.endswith(".py"):
                            issues.append(self._make_safety_issue(
                                title="Sensor data used without validation",
                                description="Sensor data is accessed without visible validation. Always validate before use.",
                                severity="major",
                                file_path=file_change.new_path,
                                line=line.line_number,
                            ))

                    # Check: sleep/delay in safety-critical path
                    if re.search(r"time\.sleep|std::this_thread::sleep", content):
                        issues.append(self._make_safety_issue(
                            title="Sleep in code path",
                            description="Sleep/delay detected in safety-related code. Ensure this doesn't affect real-time constraints.",
                            severity="minor",
                            file_path=file_change.new_path,
                            line=line.line_number,
                        ))

                    # Check: TODO/FIXME in safety code
                    if re.search(r"(TODO|FIXME|HACK|XXX)", content, re.IGNORECASE):
                        issues.append(self._make_safety_issue(
                            title="TODO/FIXME in safety-critical code",
                            description="TODO/FIXME in safety-critical code must be resolved before merge.",
                            severity="major",
                            file_path=file_change.new_path,
                            line=line.line_number,
                        ))

        return issues

    async def _review_file(self, file_change, author_role: str) -> list[Issue]:
        """Run LLM-based safety review on a file."""
        # Check budget
        if self._cost_monitor and not self._cost_monitor.check_budget():
            logger.warning("Budget exceeded, skipping LLM review")
            return []

        language = "cpp" if file_change.new_path.endswith((".cpp", ".cc", ".h", ".hpp")) else "python"

        file_ctx = {
            "file_path": file_change.new_path,
            "change_type": file_change.change_type.value,
            "diff_content": self._format_diff(file_change),
            "surrounding_code": "",
            "language": language,
            "author_role": author_role,
        }

        if self.context_builder.repo_path:
            full_ctx = self.context_builder._build_file_context(file_change)
            file_ctx["surrounding_code"] = full_ctx.surrounding_code

        safety_context = self._build_safety_context(file_change)
        messages = build_safety_review_prompt(file_ctx, safety_context, author_role)

        try:
            max_tokens = getattr(self.config.llm, "max_tokens", 16384) if hasattr(self.config, "llm") else 16384
            response = await self.llm_client.complete(
                messages=messages,
                model=self.config.llm.model if hasattr(self.config, "llm") else "gpt-4",
                temperature=0.1,
                max_tokens=max_tokens,
            )
            # Track cost
            if self._cost_monitor:
                self._cost_monitor.record_usage(
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=response.cost_usd,
                    model=response.model,
                )
            return parse_llm_issues(response.content, "safety", file_change.new_path)
        except Exception as e:
            logger.warning(f"Safety review failed for {file_change.new_path}: {e}")
            return []

    def _build_safety_context(self, file_change) -> str:
        """Build safety-specific context for the file."""
        context_parts = []
        path = file_change.new_path.lower()

        if "sensor" in path or "lidar" in path or "radar" in path:
            context_parts.append("This file handles sensor data. Validate timestamps, data integrity, and format.")
        if "simul" in path or "scenario" in path:
            context_parts.append("This file is related to simulation. Validate all configuration parameters.")
        if "config" in path:
            context_parts.append("This is a configuration file. Validate all parameters and provide safe defaults.")
        if "safety" in path or "emergency" in path:
            context_parts.append("This file is directly safety-related. Any error must have a safe fallback.")

        return "\n".join(context_parts) if context_parts else ""

    def _format_diff(self, file_change) -> str:
        lines = []
        for hunk in file_change.hunks:
            lines.append(f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@")
            for ctx in hunk.context_lines:
                lines.append(f" {ctx}")
            for cl in hunk.changed_lines:
                prefix = "+" if cl.is_addition else "-"
                lines.append(f"{prefix}{cl.content}")
        return "\n".join(lines)

    def _make_safety_issue(self, title: str, description: str, severity: str, file_path: str, line: int, suggestion: Optional[str] = None) -> Issue:
        import uuid
        return Issue(
            id=f"SAFETY-{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            severity=Severity(severity),
            category="safety",
            location=IssueLocation(file_path=file_path, line_start=line),
            suggestion=suggestion,
            source_agent="safety",
        )
