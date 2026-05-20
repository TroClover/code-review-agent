"""Profile manager - manages review profiles based on branch names."""

from __future__ import annotations

import fnmatch
import logging
from typing import Optional

from ..config.schema import ProfileConfig, ProfileThresholds

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages review profiles based on branch names.

    Profiles determine:
    - Which checks are enabled
    - Severity thresholds for blocking
    - Review depth
    """

    def __init__(self, profiles: list[ProfileConfig], default_branch: str = "main"):
        self.profiles = profiles
        self.default_branch = default_branch
        self._default_profile = self._get_or_create_default()

    def get_profile(self, branch_name: str) -> ProfileConfig:
        """Get the review profile for a branch.

        Args:
            branch_name: Name of the branch

        Returns:
            The matching ProfileConfig, or default if no match
        """
        # First, try to match against specific (non-wildcard) patterns
        # This ensures "main" matches "strict" before "*" matches "standard"
        for profile in self.profiles:
            for pattern in profile.branch_patterns:
                # Skip wildcard-only patterns on first pass
                if pattern == "*":
                    continue
                if fnmatch.fnmatch(branch_name, pattern):
                    logger.info(f"Branch '{branch_name}' matched profile '{profile.name}' (pattern: {pattern})")
                    return profile

        # Second pass: try wildcard patterns
        for profile in self.profiles:
            for pattern in profile.branch_patterns:
                if pattern == "*" and fnmatch.fnmatch(branch_name, pattern):
                    logger.info(f"Branch '{branch_name}' matched profile '{profile.name}' (pattern: {pattern})")
                    return profile

        # Default branch gets strict profile
        if branch_name == self.default_branch:
            strict = self._find_profile_by_name("strict")
            if strict:
                return strict

        # Fallback to standard
        standard = self._find_profile_by_name("standard")
        if standard:
            return standard

        return self._default_profile

    def get_thresholds(self, profile: ProfileConfig) -> ProfileThresholds:
        """Get thresholds for a profile."""
        return profile.thresholds

    def get_enabled_checks(self, profile: ProfileConfig) -> dict[str, bool]:
        """Get enabled checks for a profile."""
        return {
            "style": profile.checks.enable_style,
            "logic": profile.checks.enable_logic,
            "security": profile.checks.enable_security,
            "performance": profile.checks.enable_performance,
            "safety": profile.checks.enable_safety,
        }

    def should_run_agent(self, profile: ProfileConfig, agent_type: str) -> bool:
        """Check if an agent should run for a given profile.

        Args:
            profile: The review profile
            agent_type: Agent type string (code_review, safety)

        Returns:
            True if the agent should run
        """
        checks = self.get_enabled_checks(profile)

        if agent_type == "code_review":
            # Code review agent runs if any of its checks are enabled
            return checks.get("logic", True) or checks.get("security", True) or checks.get("performance", True)
        elif agent_type == "safety":
            return checks.get("safety", True)

        return True

    def _find_profile_by_name(self, name: str) -> Optional[ProfileConfig]:
        """Find a profile by name."""
        for profile in self.profiles:
            if profile.name == name:
                return profile
        return None

    def _get_or_create_default(self) -> ProfileConfig:
        """Get or create a default profile."""
        standard = self._find_profile_by_name("standard")
        if standard:
            return standard

        return ProfileConfig(
            name="standard",
            description="Default profile",
            thresholds=ProfileThresholds(),
        )
