"""Configuration loader with layered defaults: global → repo → user."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from .schema import BreviewConfig

# Default config search paths
_GLOBAL_CONFIG_PATH = Path.home() / ".breview" / "config.yml"
_REPO_CONFIG_NAME = ".breview.yml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if not found."""
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


class ConfigLoader:
    """Loads and merges configuration from multiple sources."""

    def __init__(
        self,
        global_path: Optional[Path] = None,
        repo_path: Optional[Path] = None,
        env_prefix: str = "BREVIEW_",
    ):
        self.global_path = global_path or _GLOBAL_CONFIG_PATH
        self.repo_path = repo_path
        self.env_prefix = env_prefix

    def load(self) -> BreviewConfig:
        """Load configuration with layering: global → repo → env overrides."""
        merged: dict = {}

        # Layer 1: Global config
        global_cfg = _load_yaml(self.global_path)
        merged = _deep_merge(merged, global_cfg)

        # Layer 2: Repo config
        if self.repo_path:
            repo_cfg = _load_yaml(self.repo_path)
            merged = _deep_merge(merged, repo_cfg)

        # Layer 3: Environment variable overrides
        env_overrides = self._load_env_overrides()
        merged = _deep_merge(merged, env_overrides)

        return BreviewConfig.model_validate(merged)

    def _load_env_overrides(self) -> dict:
        """Load configuration overrides from environment variables."""
        overrides: dict = {}
        prefix = self.env_prefix

        # Map env vars to config paths
        env_map = {
            f"{prefix}LLM_PROVIDER": ("llm", "provider"),
            f"{prefix}LLM_MODEL": ("llm", "model"),
            f"{prefix}LLM_API_KEY": ("llm", "api_key"),
            f"{prefix}LLM_BASE_URL": ("llm", "base_url"),
            f"{prefix}ADVISORY_ONLY": ("thresholds", "advisory_only"),
        }

        for env_var, config_path in env_map.items():
            value = os.environ.get(env_var)
            if value is not None:
                current = overrides
                for key in config_path[:-1]:
                    current = current.setdefault(key, {})
                # Type coercion for boolean
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"  # type: ignore
                current[config_path[-1]] = value

        return overrides


def load_config(
    repo_path: Optional[Path] = None,
    global_path: Optional[Path] = None,
) -> BreviewConfig:
    """Convenience function to load config."""
    loader = ConfigLoader(global_path=global_path, repo_path=repo_path)
    return loader.load()
