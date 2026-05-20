"""Orchestrator Agent - coordinates all review components.

This agent is the core of the review pipeline. It:
1. Parses diff and builds context (merged from Context Agent)
2. Runs linter integration (replaces Style Agent)
3. Selects and invokes review agents based on profile
4. Aggregates results: merge linter + LLM, deduplicate, filter
5. Generates reports (merged from Report Agent)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from ..context.builder import ContextBuilder
from ..cost.monitor import CostMonitor
from ..degradation.manager import DegradationManager, DegradationMode
from ..diff.parser import DiffParser
from ..false_positive.filter import filter_false_positives
from ..false_positive.store import FalsePositiveStore
from ..linter.runner import LinterRunner
from ..models.agent_message import AgentMessage, AgentType, MessageType
from ..models.issue import Issue, Severity
from ..models.review import PRInfo, ReviewProfile, ReviewRequest, ReviewResult
from ..profiles.manager import ProfileManager
from .base import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Orchestrator Agent - the coordinator of the review pipeline.

    Responsibilities:
    1. Parse diff and build context
    2. Run linter integration
    3. Select agents based on profile
    4. Invoke agents in parallel (code_review, safety)
    5. Aggregate results: merge, deduplicate, filter
    6. Generate reports and PR comments
    """

    agent_type = AgentType.ORCHESTRATOR
    name = "Orchestrator"

    def __init__(
        self,
        config: Any,
        agents: dict[AgentType, BaseAgent],
        profile_manager: Optional[ProfileManager] = None,
        cost_monitor: Optional[CostMonitor] = None,
        degradation_manager: Optional[DegradationManager] = None,
        false_positive_store: Optional[FalsePositiveStore] = None,
    ):
        super().__init__(config)
        self.agents = agents
        self.profile_manager = profile_manager
        self.cost_monitor = cost_monitor or CostMonitor(
            max_cost_per_review=getattr(config, "cost", type("C", (), {"max_cost_per_review": 1.0})()).max_cost_per_review
            if hasattr(config, "cost") else 1.0
        )
        self.degradation_manager = degradation_manager or DegradationManager()
        self.false_positive_store = false_positive_store
        self.context_builder = ContextBuilder()
        self.linter_runner = self._create_linter_runner()

    async def execute(self, message: AgentMessage) -> AgentMessage:
        """Not used directly - orchestrator has its own run_pipeline method."""
        raise NotImplementedError("Use run_pipeline() instead")

    async def run_pipeline(self, request: ReviewRequest) -> ReviewResult:
        """Run the full review pipeline for a PR.

        Args:
            request: Review request with PR info and diff

        Returns:
            Aggregated review result
        """
        start_time = time.monotonic()
        logger.info(f"Starting review pipeline for PR #{request.pr_info.pr_number}")

        # Step 1: Determine profile
        profile = self._get_profile(request.pr_info)
        logger.info(f"Using profile: {profile.name}")

        # Step 2: Build context
        context_data = self._build_context(request)

        # Step 3: Run linters
        linter_issues: list[Issue] = []
        if not request.skip_linter and self.linter_runner:
            linter_issues = self._run_linters(request)
            logger.info(f"Linter found {len(linter_issues)} issues")

        # Step 4: Select and run review agents
        agents_to_run = self._select_agents(profile, request)
        logger.info(f"Agents to run: {[a.value for a in agents_to_run]}")

        review_agents = [
            agent_type for agent_type in agents_to_run
            if agent_type in (AgentType.CODE_REVIEW, AgentType.SAFETY)
        ]

        llm_issues: list[Issue] = []
        agents_executed: list[str] = []
        agents_failed: list[str] = []

        if self.degradation_manager.mode != DegradationMode.LINTER_ONLY:
            parallel_results = await self._run_agents_parallel(
                review_agents, request, context_data
            )

            for agent_type, result in zip(review_agents, parallel_results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {agent_type.value} raised exception: {result}")
                    agents_failed.append(agent_type.value)
                elif isinstance(result, AgentMessage):
                    if result.message_type == MessageType.ERROR:
                        logger.warning(f"Agent {agent_type.value} failed: {result.error}")
                        agents_failed.append(agent_type.value)
                    else:
                        llm_issues.extend(result.issues)
                        agents_executed.append(agent_type.value)
        else:
            logger.info("In degraded mode, skipping LLM agents")
            agents_failed.extend([a.value for a in review_agents])

        # Step 5: Aggregate results
        all_issues = self._merge_results(linter_issues, llm_issues)
        all_issues = self._deduplicate_issues(all_issues)

        # Filter false positives
        if self.false_positive_store:
            all_issues = filter_false_positives(all_issues, self.false_positive_store)

        all_issues = self._filter_by_threshold(all_issues, profile)
        all_issues.sort(
            key=lambda i: ({"critical": 0, "major": 1, "minor": 2, "info": 3}[i.severity.value],)
        )

        # Step 6: Generate summary
        summary = self._generate_summary(
            all_issues, agents_executed, agents_failed, linter_issues
        )

        # Step 7: Determine approval
        thresholds = self.profile_manager.get_thresholds(profile) if self.profile_manager else None
        critical_count = len([i for i in all_issues if i.severity == Severity.CRITICAL])
        major_count = len([i for i in all_issues if i.severity == Severity.MAJOR])

        if thresholds:
            if thresholds.advisory_only:
                is_approved = True
            else:
                is_approved = (
                    critical_count < thresholds.block_on_critical
                    and major_count < thresholds.block_on_major
                )
        else:
            is_approved = critical_count < 1

        duration = time.monotonic() - start_time

        # Record cost
        if self.cost_monitor:
            self.cost_monitor.record_review(
                review_id=f"PR-{request.pr_info.pr_number}",
                total_tokens=self.cost_monitor._current_tokens,
                input_tokens=0,
                output_tokens=0,
                cost_usd=self.cost_monitor._current_cost,
                model="",
                files_reviewed=len(context_data.get("file_contexts", [])),
                duration_seconds=duration,
            )

        return ReviewResult(
            request=request,
            issues=all_issues,
            summary=summary,
            agents_executed=agents_executed,
            agents_failed=agents_failed,
            duration_seconds=duration,
            is_approved=is_approved,
            blocking_issues_count=critical_count,
        )

    def _get_profile(self, pr_info: PRInfo) -> Any:
        """Get review profile for the PR."""
        if self.profile_manager:
            return self.profile_manager.get_profile(pr_info.head_branch)
        # Return a default profile
        from ..config.schema import ProfileConfig, ProfileThresholds
        return ProfileConfig(
            name="standard",
            thresholds=ProfileThresholds(),
        )

    def _build_context(self, request: ReviewRequest) -> dict[str, Any]:
        """Build review context from diff (merged from Context Agent)."""
        parser = DiffParser()
        parsed_diff = parser.parse(request.diff_content)

        context = self.context_builder.build_context(
            parsed_diff,
            pr_description=request.pr_info.description,
        )

        return {
            "file_contexts": [
                {
                    "file_path": fc.file_path,
                    "change_type": fc.change_type,
                    "diff_content": fc.diff_content,
                    "surrounding_code": fc.surrounding_code,
                    "file_header": fc.file_header,
                    "function_signatures": fc.function_signatures,
                    "total_lines": fc.total_lines,
                }
                for fc in context.file_contexts
            ],
            "pr_description": context.pr_description,
            "total_files": len(context.file_contexts),
        }

    def _run_linters(self, request: ReviewRequest) -> list[Issue]:
        """Run linter integration."""
        parser = DiffParser()
        parsed_diff = parser.parse(request.diff_content)

        all_issues: list[Issue] = []
        for file_change in parsed_diff.files:
            if file_change.is_binary:
                continue

            # Check exemptions
            if self._is_exempt(file_change.new_path):
                continue

            try:
                file_issues = self.linter_runner.run_linters(file_change.new_path)
                all_issues.extend(file_issues)
            except Exception as e:
                logger.warning(f"Linter failed for {file_change.new_path}: {e}")

        return all_issues

    def _select_agents(self, profile: Any, request: ReviewRequest) -> list[AgentType]:
        """Select which agents to run based on profile."""
        if request.agents_to_run:
            return [AgentType(a) for a in request.agents_to_run]

        agents = []
        if self.profile_manager:
            if self.profile_manager.should_run_agent(profile, "code_review"):
                agents.append(AgentType.CODE_REVIEW)
            if self.profile_manager.should_run_agent(profile, "safety"):
                agents.append(AgentType.SAFETY)
        else:
            agents = [AgentType.CODE_REVIEW, AgentType.SAFETY]

        return agents

    async def _run_agents_parallel(
        self,
        agents: list[AgentType],
        request: ReviewRequest,
        context_data: dict[str, Any],
    ) -> list:
        """Run review agents in parallel."""
        tasks = []
        for agent_type in agents:
            if agent_type not in self.agents:
                continue
            task_msg = AgentMessage.create_task(
                AgentType.ORCHESTRATOR,
                agent_type,
                {"request": request.model_dump(), "context": context_data},
            )
            tasks.append(self.agents[agent_type].run(task_msg))

        return await asyncio.gather(*tasks, return_exceptions=True)

    def _merge_results(
        self, linter_issues: list[Issue], llm_issues: list[Issue]
    ) -> list[Issue]:
        """Merge linter and LLM results."""
        return linter_issues + llm_issues

    def _deduplicate_issues(self, issues: list[Issue]) -> list[Issue]:
        """Remove duplicate issues found by multiple sources."""
        seen: dict[str, Issue] = {}
        for issue in issues:
            key = f"{issue.location.file_path}:{issue.location.line_start}:{issue.title}"
            if key in seen:
                existing = seen[key]
                if issue.confidence > existing.confidence:
                    seen[key] = issue
            else:
                seen[key] = issue
        return list(seen.values())

    def _filter_by_threshold(self, issues: list[Issue], profile: Any) -> list[Issue]:
        """Filter issues based on profile thresholds."""
        # In relaxed mode, only show critical and major
        if hasattr(profile, "name") and profile.name == "relaxed":
            return [i for i in issues if i.severity in (Severity.CRITICAL, Severity.MAJOR)]
        return issues

    def _is_exempt(self, file_path: str) -> bool:
        """Check if a file is exempt from review."""
        import fnmatch

        if not hasattr(self.config, "exemptions"):
            return False

        for pattern in self.config.exemptions.file_patterns:
            if fnmatch.fnmatch(file_path, pattern):
                return True
        return False

    def _create_linter_runner(self) -> Optional[LinterRunner]:
        """Create linter runner from config."""
        if not hasattr(self.config, "linter"):
            return None
        if not self.config.linter.enabled:
            return None

        linter_configs = []
        for tool in self.config.linter.tools:
            linter_configs.append({
                "name": tool.name,
                "enabled": tool.enabled,
                "config_file": tool.config_file,
                "extra_args": tool.extra_args,
            })

        return LinterRunner(linter_configs=linter_configs)

    def _generate_summary(
        self,
        issues: list[Issue],
        executed: list[str],
        failed: list[str],
        linter_issues: list[Issue],
    ) -> str:
        """Generate a human-readable review summary (merged from Report Agent)."""
        counts: dict[str, int] = {}
        for issue in issues:
            counts[issue.severity.value] = counts.get(issue.severity.value, 0) + 1

        lines = ["## Review Summary", ""]

        if not issues:
            lines.append(":white_check_mark: No issues found. LGTM!")
        else:
            lines.append(f"Found **{len(issues)}** issue(s):")
            for sev in ["critical", "major", "minor", "info"]:
                if sev in counts:
                    emoji = {
                        "critical": ":rotating_light:",
                        "major": ":warning:",
                        "minor": ":bulb:",
                        "info": ":information_source:",
                    }[sev]
                    lines.append(f"- {emoji} {counts[sev]} {sev}")

        # Linter stats
        if linter_issues:
            lines.extend(["", f":wrench: Linter: {len(linter_issues)} issue(s)"])

        # Cost info
        if self.cost_monitor:
            cost_summary = self.cost_monitor.get_cost_summary()
            lines.extend([
                "",
                f":moneybag: Cost: ${cost_summary['current_review_cost_usd']:.4f} / ${cost_summary['max_cost_per_review_usd']:.2f}",
            ])

        if failed:
            lines.extend(["", f":warning: Agents skipped due to errors: {', '.join(failed)}"])

        return "\n".join(lines)

    def format_inline_comment(self, issue: Issue) -> dict[str, Any]:
        """Format an issue as a GitHub inline review comment (merged from Report Agent)."""
        return {
            "path": issue.location.file_path,
            "line": issue.location.line_start,
            "body": issue.to_comment_body(),
        }
