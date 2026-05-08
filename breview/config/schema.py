"""Configuration schema for breview."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(default="openai", description="LLM provider: openai, anthropic, local")
    model: str = Field(default="gpt-4", description="Model name")
    api_key: Optional[str] = Field(default=None, description="API key (from env or config)")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=100)
    max_cost_per_review: float = Field(default=1.0, description="Max USD cost per review")


class RoleMapping(BaseModel):
    """Maps GitHub usernames/teams to author roles."""

    interns: list[str] = Field(default_factory=list, description="GitHub usernames of interns")
    seniors: list[str] = Field(default_factory=list, description="GitHub usernames of senior engineers")
    # Everyone else is treated as full_time by default


class AgentScheduleConfig(BaseModel):
    """Controls which agents run for which roles."""

    intern_agents: list[str] = Field(
        default_factory=lambda: ["style", "code_review", "safety"],
        description="Agents to run for interns",
    )
    full_time_agents: list[str] = Field(
        default_factory=lambda: ["style", "code_review", "safety"],
        description="Agents to run for full-time employees",
    )
    senior_agents: list[str] = Field(
        default_factory=lambda: ["code_review", "safety"],
        description="Agents to run for senior engineers (skip style)",
    )


class ThresholdConfig(BaseModel):
    """Severity thresholds for blocking."""

    block_on_critical: int = Field(default=1, description="Block merge if >= N critical issues")
    block_on_major: int = Field(default=5, description="Block merge if >= N major issues")
    advisory_only: bool = Field(default=False, description="Never block, only advise")


class KnowledgeConfig(BaseModel):
    """Knowledge extraction settings."""

    auto_generate_threshold: int = Field(default=3, description="Auto-create knowledge after N same-pattern issues")
    human_comment_weight: float = Field(default=2.0, description="Weight for human comments")
    agent_comment_weight: float = Field(default=1.0, description="Weight for agent comments")
    enable_feedback: bool = Field(default=True, description="Enable helpful/not-helpful feedback")


class NotificationConfig(BaseModel):
    """Notification settings."""

    enabled: bool = Field(default=False)
    channel: str = Field(default="slack", description="Notification channel: slack, email, feishu")
    webhook_url: Optional[str] = Field(default=None)


class ExemptionConfig(BaseModel):
    """Review exemption rules."""

    file_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.pb.cc", "*.pb.h",  # Protobuf generated
            "*.generated.*",  # Generated files
            "vendor/**", "third_party/**",  # Vendored deps
        ],
        description="Glob patterns for files to skip",
    )
    inline_marker: str = Field(default="breview: ignore", description="Inline comment to skip a line")


class BreviewConfig(BaseModel):
    """Top-level configuration for breview."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    roles: RoleMapping = Field(default_factory=RoleMapping)
    agents: AgentScheduleConfig = Field(default_factory=AgentScheduleConfig)
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    exemptions: ExemptionConfig = Field(default_factory=ExemptionConfig)

    # Repo-level settings
    repo_name: Optional[str] = Field(default=None)
    default_branch: str = Field(default="main")
    language: list[str] = Field(default_factory=lambda: ["python", "cpp"])
