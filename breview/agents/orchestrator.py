"""Orchestrator Agent - coordinates all other agents."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from ..models.agent_message import AgentMessage, AgentType, MessageType
from ..models.issue import Issue, Severity
from ..models.review import AuthorRole, ReviewRequest, ReviewResult
from .base import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Orchestrator Agent - the coordinator of the review pipeline.

    Responsibilities:
    1. Parse diff and identify author role
    2. Decide which agents to invoke based on role
    3. Invoke agents in parallel (style, code_review, safety)
    4. Aggregate results: deduplicate, sort, filter
    5. Invoke post-processing agents (knowledge, report)
    """

    agent_type = AgentType.ORCHESTRATOR
    name = "Orchestrator"

    def __init__(self, config: Any, agents: dict[AgentType, BaseAgent]):
        super().__init__(config)
        self.agents = agents

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

        # Step 1: Determine which agents to run
        agents_to_run = self._select_agents(request)
        logger.info(f"Agents to run: {[a.value for a in agents_to_run]}")

        # Step 2: Build context (always first)
        context_issues: list[Issue] = []
        context_data: dict[str, Any] = {}
        if AgentType.CONTEXT in self.agents:
            context_msg = AgentMessage.create_task(
                AgentType.ORCHESTRATOR, AgentType.CONTEXT, {"request": request.model_dump()}
            )
            context_result = await self.agents[AgentType.CONTEXT].run(context_msg)
            context_data = context_result.payload
            if context_result.message_type == MessageType.ERROR:
                logger.warning(f"Context agent failed: {context_result.error}")

        # Step 3: Run review agents in parallel
        review_agents = [
            agent_type for agent_type in agents_to_run
            if agent_type in (AgentType.STYLE, AgentType.CODE_REVIEW, AgentType.SAFETY)
        ]

        tasks = []
        for agent_type in review_agents:
            if agent_type not in self.agents:
                continue
            task_msg = AgentMessage.create_task(
                AgentType.ORCHESTRATOR,
                agent_type,
                {"request": request.model_dump(), "context": context_data},
            )
            tasks.append(self.agents[agent_type].run(task_msg))

        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Step 4: Collect issues from all agents
        all_issues: list[Issue] = []
        agents_executed: list[str] = []
        agents_failed: list[str] = []

        for agent_type, result in zip(review_agents, parallel_results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent_type.value} raised exception: {result}")
                agents_failed.append(agent_type.value)
            elif isinstance(result, AgentMessage):
                if result.message_type == MessageType.ERROR:
                    logger.warning(f"Agent {agent_type.value} failed: {result.error}")
                    agents_failed.append(agent_type.value)
                else:
                    all_issues.extend(result.issues)
                    agents_executed.append(agent_type.value)

        # Step 5: Aggregate results
        all_issues = self._deduplicate_issues(all_issues)
        all_issues = self._filter_by_threshold(all_issues, request.pr_info.author_role)
        all_issues.sort(key=lambda i: ({"critical": 0, "major": 1, "minor": 2, "info": 3}[i.severity.value],))

        # Step 6: Run post-processing agents
        if AgentType.KNOWLEDGE in self.agents:
            knowledge_msg = AgentMessage.create_task(
                AgentType.ORCHESTRATOR,
                AgentType.KNOWLEDGE,
                {"issues": [i.model_dump() for i in all_issues], "request": request.model_dump()},
            )
            await self.agents[AgentType.KNOWLEDGE].run(knowledge_msg)

        # Step 7: Generate summary
        summary = self._generate_summary(all_issues, agents_executed, agents_failed)

        duration = time.monotonic() - start_time
        critical_count = len([i for i in all_issues if i.severity == Severity.CRITICAL])
        block_on_critical = getattr(self.config.thresholds, "block_on_critical", 1) if hasattr(self.config, "thresholds") else 1

        return ReviewResult(
            request=request,
            issues=all_issues,
            summary=summary,
            agents_executed=agents_executed,
            agents_failed=agents_failed,
            duration_seconds=duration,
            is_approved=critical_count < block_on_critical,
            blocking_issues_count=critical_count,
        )

    def _select_agents(self, request: ReviewRequest) -> list[AgentType]:
        """Select which agents to run based on author role."""
        if request.agents_to_run:
            return [AgentType(a) for a in request.agents_to_run]

        role = request.pr_info.author_role
        if hasattr(self.config, "agents"):
            if role == AuthorRole.INTERN:
                agent_names = self.config.agents.intern_agents
            elif role == AuthorRole.SENIOR:
                agent_names = self.config.agents.senior_agents
            else:
                agent_names = self.config.agents.full_time_agents
        else:
            agent_names = ["style", "code_review", "safety"]

        # Always include context and knowledge
        agent_types = [AgentType(a) for a in agent_names]
        return agent_types

    def _deduplicate_issues(self, issues: list[Issue]) -> list[Issue]:
        """Remove duplicate issues found by multiple agents."""
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

    def _filter_by_threshold(self, issues: list[Issue], role: AuthorRole) -> list[Issue]:
        """Filter issues based on role thresholds (intern sees more, senior sees less)."""
        if role == AuthorRole.SENIOR:
            return [i for i in issues if i.severity in (Severity.CRITICAL, Severity.MAJOR)]
        return issues

    def _generate_summary(
        self, issues: list[Issue], executed: list[str], failed: list[str]
    ) -> str:
        """Generate a human-readable review summary."""
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
                    emoji = {"critical": ":rotating_light:", "major": ":warning:", "minor": ":bulb:", "info": ":information_source:"}[sev]
                    lines.append(f"- {emoji} {counts[sev]} {sev}")

        if failed:
            lines.extend(["", f":warning: Agents skipped due to errors: {', '.join(failed)}"])

        return "\n".join(lines)
