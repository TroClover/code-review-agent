"""Configuration system with layered defaults: global → repo → user."""

from .loader import ConfigLoader, load_config
from .schema import BreviewConfig

__all__ = ["BreviewConfig", "ConfigLoader", "load_config"]
