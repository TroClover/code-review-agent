"""Tests for profile system (TC-6.1~6.3, TC-10.3)."""

import pytest

from breview.config.schema import ProfileConfig, ProfileThresholds, ProfileChecks
from breview.profiles.manager import ProfileManager


@pytest.fixture
def default_profiles():
    """Create default profiles for testing."""
    return [
        ProfileConfig(
            name="strict",
            description="Main/release branches",
            branch_patterns=["main", "master", "release/*"],
            thresholds=ProfileThresholds(
                block_on_critical=1,
                block_on_major=3,
                advisory_only=False,
            ),
            checks=ProfileChecks(
                enable_style=True,
                enable_logic=True,
                enable_security=True,
                enable_performance=True,
                enable_safety=True,
            ),
        ),
        ProfileConfig(
            name="standard",
            description="Feature branches",
            branch_patterns=["*"],
            thresholds=ProfileThresholds(
                block_on_critical=3,
                block_on_major=5,
                advisory_only=False,
            ),
            checks=ProfileChecks(),
        ),
        ProfileConfig(
            name="relaxed",
            description="WIP branches",
            branch_patterns=["wip/*", "draft/*"],
            thresholds=ProfileThresholds(
                block_on_critical=10,
                block_on_major=20,
                advisory_only=True,
            ),
            checks=ProfileChecks(
                enable_style=False,
                enable_performance=False,
            ),
        ),
    ]


class TestProfileManager:
    """TC-6.1~6.3: Profile selection based on branch name."""

    def test_strict_profile_for_main(self, default_profiles):
        """TC-6.1: main branch should get strict profile."""
        manager = ProfileManager(default_profiles, default_branch="main")
        profile = manager.get_profile("main")
        assert profile.name == "strict"

    def test_strict_profile_for_release(self, default_profiles):
        """release/* branches should get strict profile."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("release/v1.0")
        assert profile.name == "strict"

    def test_standard_profile_for_feature(self, default_profiles):
        """TC-6.2: feature branches should get standard profile."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("feature/my-feature")
        assert profile.name == "standard"

    def test_relaxed_profile_for_wip(self, default_profiles):
        """TC-6.3: wip/* branches should get relaxed profile."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("wip/experiment")
        assert profile.name == "relaxed"

    def test_relaxed_profile_for_draft(self, default_profiles):
        """draft/* branches should get relaxed profile."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("draft/new-feature")
        assert profile.name == "relaxed"

    def test_standard_profile_as_fallback(self, default_profiles):
        """Unknown branch patterns should fall back to standard."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("unknown-branch")
        assert profile.name == "standard"


class TestProfileThresholds:
    """Test profile threshold retrieval."""

    def test_strict_thresholds(self, default_profiles):
        """Strict profile should have low thresholds."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("main")
        thresholds = manager.get_thresholds(profile)
        assert thresholds.block_on_critical == 1
        assert thresholds.block_on_major == 3
        assert thresholds.advisory_only is False

    def test_relaxed_thresholds(self, default_profiles):
        """Relaxed profile should have high thresholds and advisory only."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("wip/test")
        thresholds = manager.get_thresholds(profile)
        assert thresholds.block_on_critical == 10
        assert thresholds.advisory_only is True


class TestProfileChecks:
    """Test profile check configuration."""

    def test_strict_all_checks_enabled(self, default_profiles):
        """Strict profile should have all checks enabled."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("main")
        checks = manager.get_enabled_checks(profile)
        assert all(checks.values())

    def test_relaxed_style_disabled(self, default_profiles):
        """Relaxed profile should have style checks disabled."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("wip/test")
        checks = manager.get_enabled_checks(profile)
        assert checks["style"] is False
        assert checks["logic"] is True

    def test_should_run_agent_code_review(self, default_profiles):
        """Code review agent should run for all profiles."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("main")
        assert manager.should_run_agent(profile, "code_review") is True

    def test_should_run_agent_safety(self, default_profiles):
        """Safety agent should run for all profiles."""
        manager = ProfileManager(default_profiles)
        profile = manager.get_profile("main")
        assert manager.should_run_agent(profile, "safety") is True
