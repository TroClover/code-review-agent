"""Configuration schema for breview v2."""

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


class CostConfig(BaseModel):
    """Cost control configuration."""

    max_cost_per_review: float = Field(default=1.0, description="Max USD cost per review")
    enable_cache: bool = Field(default=True, description="Enable review cache to avoid re-reviewing same diff")
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")


class ProfileThresholds(BaseModel):
    """Severity thresholds for a review profile."""

    block_on_critical: int = Field(default=1, description="Block if >= N critical issues")
    block_on_major: int = Field(default=5, description="Block if >= N major issues")
    advisory_only: bool = Field(default=False, description="Never block, only advise")


class ProfileChecks(BaseModel):
    """Enabled checks for a review profile."""

    enable_style: bool = Field(default=True, description="Enable style/linter checks")
    enable_logic: bool = Field(default=True, description="Enable logic correctness checks")
    enable_security: bool = Field(default=True, description="Enable security checks")
    enable_performance: bool = Field(default=True, description="Enable performance checks")
    enable_safety: bool = Field(default=True, description="Enable safety checks")


class ProfileConfig(BaseModel):
    """A single review profile configuration."""

    name: str = Field(description="Profile name: strict, standard, relaxed")
    description: str = Field(default="", description="Profile description")
    branch_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for matching branches (e.g., 'main', 'release/*')",
    )
    thresholds: ProfileThresholds = Field(default_factory=ProfileThresholds)
    checks: ProfileChecks = Field(default_factory=ProfileChecks)


class LinterToolConfig(BaseModel):
    """Configuration for a single linter tool."""

    name: str = Field(description="Linter name: ruff, flake8, clang-tidy")
    enabled: bool = Field(default=True)
    config_file: Optional[str] = Field(default=None, description="Path to linter config file")
    extra_args: list[str] = Field(default_factory=list, description="Extra CLI arguments")


class LinterConfig(BaseModel):
    """Linter integration configuration."""

    enabled: bool = Field(default=True, description="Enable linter integration")
    tools: list[LinterToolConfig] = Field(
        default_factory=lambda: [
            LinterToolConfig(name="ruff"),
            LinterToolConfig(name="clang-tidy"),
        ],
        description="Linter tools to run",
    )


class SafetyDomainConfig(BaseModel):
    """Autonomous driving domain-specific safety rules."""

    enabled: bool = Field(default=False, description="Enable domain-specific safety rules")
    sensor_validation: bool = Field(default=True, description="Check sensor data validation")
    simulation_config: bool = Field(default=True, description="Check simulation configuration")
    safety_critical_paths: bool = Field(default=True, description="Check safety-critical code paths")
    realtime_constraints: bool = Field(default=True, description="Check realtime constraints (sleep/delay)")


class FalsePositiveConfig(BaseModel):
    """False positive handling configuration."""

    storage_path: str = Field(
        default=".breview/false_positives.json",
        description="Path to false positive storage file",
    )
    enable_auto_filter: bool = Field(default=True, description="Auto-filter known false positives")


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
    """Top-level configuration for breview v2."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    cost: CostConfig = Field(default_factory=CostConfig)

    # Profile system (replaces role-based strategy)
    profiles: list[ProfileConfig] = Field(
        default_factory=lambda: [
            ProfileConfig(
                name="strict",
                description="Main/release branches: all checks, low thresholds",
                branch_patterns=["main", "master", "release/*"],
                thresholds=ProfileThresholds(block_on_critical=1, block_on_major=3, advisory_only=False),
                checks=ProfileChecks(),
            ),
            ProfileConfig(
                name="standard",
                description="Feature branches: core checks, medium thresholds",
                branch_patterns=["*"],
                thresholds=ProfileThresholds(block_on_critical=3, block_on_major=5, advisory_only=False),
                checks=ProfileChecks(),
            ),
            ProfileConfig(
                name="relaxed",
                description="Experimental/WIP branches: high-priority only",
                branch_patterns=["wip/*", "experiment/*", "draft/*"],
                thresholds=ProfileThresholds(block_on_critical=10, block_on_major=20, advisory_only=True),
                checks=ProfileChecks(enable_style=False, enable_performance=False),
            ),
        ],
        description="Review profiles",
    )

    # Linter integration
    linter: LinterConfig = Field(default_factory=LinterConfig)

    # Safety domain rules
    safety_domain: SafetyDomainConfig = Field(default_factory=SafetyDomainConfig)

    # False positive handling
    false_positive: FalsePositiveConfig = Field(default_factory=FalsePositiveConfig)

    # Exemptions
    exemptions: ExemptionConfig = Field(default_factory=ExemptionConfig)

    # Repo-level settings
    repo_name: Optional[str] = Field(default=None)
    default_branch: str = Field(default="main")
    language: list[str] = Field(default_factory=lambda: ["python", "cpp"])

    # Custom prompt snippet (appended to LLM prompts)
    custom_prompt: Optional[str] = Field(default=None, description="Custom prompt snippet for team-specific review focus")
