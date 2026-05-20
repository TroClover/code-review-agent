"""Tests for Orchestrator Agent (TC-6.1~6.7, TC-12.1~12.5)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from breview.agents.orchestrator import OrchestratorAgent
from breview.agents.base import BaseAgent
from breview.config.schema import ProfileConfig, ProfileThresholds, ProfileChecks
from breview.cost.monitor import CostMonitor
from breview.degradation.manager import DegradationManager
from breview.models.agent_message import AgentMessage, AgentType, MessageType
from breview.models.issue import Issue, IssueLocation, Severity
from breview.models.review import PRInfo, ReviewProfile, ReviewRequest
from breview.profiles.manager import ProfileManager


@pytest.fixture
def mock_config():
    """Create mock config."""
    config = MagicMock()
    config.llm.model = "gpt-4"
    config.cost.max_cost_per_review = 1.0
    config.cost.enable_cache = False
    config.linter.enabled = False
    config.exemptions.file_patterns = []
    config.profiles = [
        ProfileConfig(
            name="standard",
            branch_patterns=["*"],
            thresholds=ProfileThresholds(block_on_critical=1, block_on_major=5),
        ),
    ]
    return config


@pytest.fixture
def sample_request():
    """Create sample review request."""
    return ReviewRequest(
        pr_info=PRInfo(
            repo_full_name="test/repo",
            pr_number=1,
            title="Test PR",
            author="testuser",
            profile=ReviewProfile.STANDARD,
            head_branch="feature/test",
        ),
        diff_content="diff --git a/test.py b/test.py\n+def test():\n+    pass\n",
    )


@pytest.fixture
def mock_agents():
    """Create mock agents."""
    agents = {}

    # Mock code review agent
    code_review = MagicMock(spec=BaseAgent)
    code_review.agent_type = AgentType.CODE_REVIEW

    async def run_code_review(msg):
        result = AgentMessage.create_result(AgentType.CODE_REVIEW, [
            Issue(
                id="CR-1",
                title="Logic error",
                description="Test issue",
                severity=Severity.MAJOR,
                category="logic",
                location=IssueLocation(file_path="test.py", line_start=1),
                source_agent="code_review",
            )
        ])
        return result

    code_review.run = AsyncMock(side_effect=run_code_review)
    agents[AgentType.CODE_REVIEW] = code_review

    # Mock safety agent
    safety = MagicMock(spec=BaseAgent)
    safety.agent_type = AgentType.SAFETY

    async def run_safety(msg):
        return AgentMessage.create_result(AgentType.SAFETY, [])

    safety.run = AsyncMock(side_effect=run_safety)
    agents[AgentType.SAFETY] = safety

    return agents


class TestOrchestratorAgent:
    """TC-6.1~6.7: Orchestrator Agent tests."""

    @pytest.mark.asyncio
    async def test_run_pipeline_basic(self, mock_config, mock_agents, sample_request):
        """TC-12.1: Basic pipeline execution."""
        orchestrator = OrchestratorAgent(
            config=mock_config,
            agents=mock_agents,
            profile_manager=ProfileManager(mock_config.profiles),
        )

        result = await orchestrator.run_pipeline(sample_request)

        assert result is not None
        assert len(result.issues) > 0
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_agent_failure_isolation(self, mock_config, sample_request):
        """TC-6.5: Agent failure should not affect other agents."""
        agents = {}

        # Code review succeeds
        code_review = MagicMock(spec=BaseAgent)
        async def run_success(msg):
            return AgentMessage.create_result(AgentType.CODE_REVIEW, [
                Issue(
                    id="CR-1",
                    title="Test issue",
                    description="Test",
                    severity=Severity.MINOR,
                    category="logic",
                    location=IssueLocation(file_path="test.py", line_start=1),
                    source_agent="code_review",
                )
            ])
        code_review.run = AsyncMock(side_effect=run_success)
        agents[AgentType.CODE_REVIEW] = code_review

        # Safety fails
        safety = MagicMock(spec=BaseAgent)
        safety.run = AsyncMock(side_effect=Exception("LLM timeout"))
        agents[AgentType.SAFETY] = safety

        orchestrator = OrchestratorAgent(
            config=mock_config,
            agents=agents,
            profile_manager=ProfileManager(mock_config.profiles),
        )

        result = await orchestrator.run_pipeline(sample_request)

        # Should still get results from code review
        assert len(result.issues) > 0
        assert "safety" in result.agents_failed

    @pytest.mark.asyncio
    async def test_deduplication(self, mock_config, sample_request):
        """TC-6.6: Duplicate issues should be deduplicated."""
        agents = {}

        # Both agents report the same issue
        code_review = MagicMock(spec=BaseAgent)
        async def run_cr(msg):
            return AgentMessage.create_result(AgentType.CODE_REVIEW, [
                Issue(
                    id="CR-1",
                    title="Same issue",
                    description="Test",
                    severity=Severity.MAJOR,
                    category="logic",
                    location=IssueLocation(file_path="test.py", line_start=1),
                    source_agent="code_review",
                    confidence=0.8,
                )
            ])
        code_review.run = AsyncMock(side_effect=run_cr)
        agents[AgentType.CODE_REVIEW] = code_review

        safety = MagicMock(spec=BaseAgent)
        async def run_safety(msg):
            return AgentMessage.create_result(AgentType.SAFETY, [
                Issue(
                    id="SAF-1",
                    title="Same issue",
                    description="Test",
                    severity=Severity.MAJOR,
                    category="logic",
                    location=IssueLocation(file_path="test.py", line_start=1),
                    source_agent="safety",
                    confidence=0.9,
                )
            ])
        safety.run = AsyncMock(side_effect=run_safety)
        agents[AgentType.SAFETY] = safety

        orchestrator = OrchestratorAgent(
            config=mock_config,
            agents=agents,
            profile_manager=ProfileManager(mock_config.profiles),
        )

        result = await orchestrator.run_pipeline(sample_request)

        # Should be deduplicated to one issue
        assert len(result.issues) == 1

    @pytest.mark.asyncio
    async def test_sorting_by_severity(self, mock_config, sample_request):
        """TC-6.7: Issues should be sorted by severity."""
        agents = {}

        code_review = MagicMock(spec=BaseAgent)
        async def run_cr(msg):
            return AgentMessage.create_result(AgentType.CODE_REVIEW, [
                Issue(
                    id="CR-1",
                    title="Minor issue",
                    description="Test",
                    severity=Severity.MINOR,
                    category="style",
                    location=IssueLocation(file_path="test.py", line_start=1),
                    source_agent="code_review",
                ),
                Issue(
                    id="CR-2",
                    title="Critical issue",
                    description="Test",
                    severity=Severity.CRITICAL,
                    category="security",
                    location=IssueLocation(file_path="test.py", line_start=5),
                    source_agent="code_review",
                ),
            ])
        code_review.run = AsyncMock(side_effect=run_cr)
        agents[AgentType.CODE_REVIEW] = code_review

        safety = MagicMock(spec=BaseAgent)
        safety.run = AsyncMock(return_value=AgentMessage.create_result(AgentType.SAFETY, []))
        agents[AgentType.SAFETY] = safety

        orchestrator = OrchestratorAgent(
            config=mock_config,
            agents=agents,
            profile_manager=ProfileManager(mock_config.profiles),
        )

        result = await orchestrator.run_pipeline(sample_request)

        # Critical should be first
        assert result.issues[0].severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_summary_generation(self, mock_config, mock_agents, sample_request):
        """Summary should be generated correctly."""
        orchestrator = OrchestratorAgent(
            config=mock_config,
            agents=mock_agents,
            profile_manager=ProfileManager(mock_config.profiles),
        )

        result = await orchestrator.run_pipeline(sample_request)

        assert "Review Summary" in result.summary
