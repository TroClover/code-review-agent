"""CLI tool for local pre-PR code review."""

from .hooks import install_hook, uninstall_hook
from .main import cli

__all__ = ["cli", "install_hook", "uninstall_hook"]
