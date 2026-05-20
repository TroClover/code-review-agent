"""Tests for configuration system (TC-10.1~10.6)."""

import pytest
import tempfile
import os
from pathlib import Path

from breview.config.schema import (
    BreviewConfig,
    CostConfig,
    ExemptionConfig,
    LinterConfig,
    ProfileConfig,
    ProfileThresholds,
    ProfileChecks,
    SafetyDomainConfig,
)
from breview.config.loader import load_config


class TestDefaultConfig:
    """TC-10.1: Default configuration."""

    def test_default_config_creation(self):
        """Default config should be created with sensible defaults."""
        config = BreviewConfig()
        assert config.default_branch == "main"
        assert "python" in config.language
        assert config.llm.temperature == 0.1
        assert config.cost.max_cost_per_review == 1.0

    def test_default_profiles(self):
        """Default config should have 3 profiles."""
        config = BreviewConfig()
        assert len(config.profiles) == 3
        profile_names = [p.name for p in config.profiles]
        assert "strict" in profile_names
        assert "standard" in profile_names
        assert "relaxed" in profile_names

    def test_default_linter_config(self):
        """Default config should have linter enabled."""
        config = BreviewConfig()
        assert config.linter.enabled is True
        assert len(config.linter.tools) > 0

    def test_default_exemptions(self):
        """Default config should have exemption patterns."""
        config = BreviewConfig()
        assert len(config.exemptions.file_patterns) > 0
        assert "*.pb.cc" in config.exemptions.file_patterns


class TestProfileConfig:
    """TC-10.3: Profile configuration."""

    def test_profile_thresholds(self):
        """Profile thresholds should be configurable."""
        profile = ProfileConfig(
            name="custom",
            thresholds=ProfileThresholds(
                block_on_critical=2,
                block_on_major=10,
                advisory_only=True,
            ),
        )
        assert profile.thresholds.block_on_critical == 2
        assert profile.thresholds.advisory_only is True

    def test_profile_checks(self):
        """Profile checks should be configurable."""
        profile = ProfileConfig(
            name="custom",
            checks=ProfileChecks(
                enable_style=False,
                enable_logic=True,
                enable_security=True,
                enable_performance=False,
                enable_safety=True,
            ),
        )
        assert profile.checks.enable_style is False
        assert profile.checks.enable_logic is True

    def test_branch_patterns(self):
        """Profile should support branch patterns."""
        profile = ProfileConfig(
            name="custom",
            branch_patterns=["main", "release/*"],
        )
        assert "main" in profile.branch_patterns
        assert "release/*" in profile.branch_patterns


class TestCostConfig:
    """TC-10.4: Cost configuration."""

    def test_cost_config(self):
        """Cost config should be configurable."""
        config = CostConfig(
            max_cost_per_review=2.0,
            enable_cache=False,
            cache_ttl_hours=48,
        )
        assert config.max_cost_per_review == 2.0
        assert config.enable_cache is False
        assert config.cache_ttl_hours == 48


class TestLinterConfig:
    """TC-10.5: Linter configuration."""

    def test_linter_config(self):
        """Linter config should be configurable."""
        config = LinterConfig(
            enabled=True,
            tools=[
                {"name": "ruff", "enabled": True},
                {"name": "flake8", "enabled": False},
            ],
        )
        assert config.enabled is True
        assert len(config.tools) == 2


class TestSafetyDomainConfig:
    """TC-10.6: Safety domain configuration."""

    def test_safety_domain_disabled(self):
        """Safety domain should be disabled by default."""
        config = SafetyDomainConfig()
        assert config.enabled is False

    def test_safety_domain_enabled(self):
        """Safety domain can be enabled."""
        config = SafetyDomainConfig(
            enabled=True,
            sensor_validation=True,
            simulation_config=True,
        )
        assert config.enabled is True
        assert config.sensor_validation is True
