"""Profile configuration loader."""

from __future__ import annotations

import logging
from typing import Any

from ..config.schema import ProfileConfig, ProfileThresholds, ProfileChecks

logger = logging.getLogger(__name__)


def load_profiles_from_config(config: Any) -> list[ProfileConfig]:
    """Load profiles from a BreviewConfig object.

    Args:
        config: BreviewConfig or similar config object

    Returns:
        List of ProfileConfig
    """
    if hasattr(config, "profiles"):
        return config.profiles

    # Return default profiles if not configured
    return get_default_profiles()


def get_default_profiles() -> list[ProfileConfig]:
    """Get default profile configurations."""
    return [
        ProfileConfig(
            name="strict",
            description="Main/release branches: all checks, low thresholds",
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
            description="Feature branches: core checks, medium thresholds",
            branch_patterns=["*"],
            thresholds=ProfileThresholds(
                block_on_critical=3,
                block_on_major=5,
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
            name="relaxed",
            description="Experimental/WIP branches: high-priority only",
            branch_patterns=["wip/*", "experiment/*", "draft/*"],
            thresholds=ProfileThresholds(
                block_on_critical=10,
                block_on_major=20,
                advisory_only=True,
            ),
            checks=ProfileChecks(
                enable_style=False,
                enable_logic=True,
                enable_security=True,
                enable_performance=False,
                enable_safety=True,
            ),
        ),
    ]
