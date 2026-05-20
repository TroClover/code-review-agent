"""Linter runner - executes external linters and collects results."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..models.issue import Issue

logger = logging.getLogger(__name__)

# Mapping of file extensions to applicable linters
PYTHON_EXTENSIONS = {".py"}
CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"}

LINTER_COMMANDS = {
    "ruff": ["ruff", "check", "--output-format=json"],
    "flake8": ["flake8", "--format=json"],
    "clang-tidy": ["clang-tidy", "--checks=*", "-p", "."],
}


class LinterRunner:
    """Runs external linters on files and returns structured issues."""

    def __init__(self, linter_configs: Optional[list[dict]] = None):
        """Initialize with linter configurations.

        Args:
            linter_configs: List of linter config dicts with 'name', 'enabled', 'config_file', 'extra_args'
        """
        self.linter_configs = linter_configs or [
            {"name": "ruff", "enabled": True},
            {"name": "clang-tidy", "enabled": True},
        ]

    def run_linters(self, file_path: str, file_content: Optional[str] = None) -> list[Issue]:
        """Run all applicable linters on a file.

        Args:
            file_path: Path to the file to lint
            file_content: Optional file content (for in-memory files)

        Returns:
            List of issues found by linters
        """
        all_issues: list[Issue] = []
        applicable_linters = self._get_applicable_linters(file_path)

        for linter_config in applicable_linters:
            if not linter_config.get("enabled", True):
                continue

            linter_name = linter_config["name"]
            if not self._is_linter_available(linter_name):
                logger.warning(f"Linter '{linter_name}' not found in PATH, skipping")
                continue

            try:
                issues = self._run_single_linter(linter_name, file_path, linter_config)
                all_issues.extend(issues)
                logger.info(f"Linter '{linter_name}' found {len(issues)} issues in {file_path}")
            except Exception as e:
                logger.warning(f"Linter '{linter_name}' failed on {file_path}: {e}")

        return all_issues

    def _get_applicable_linters(self, file_path: str) -> list[dict]:
        """Get linters applicable to the given file type."""
        ext = Path(file_path).suffix.lower()
        applicable = []

        for config in self.linter_configs:
            linter_name = config.get("name", "")
            if ext in PYTHON_EXTENSIONS and linter_name in ("ruff", "flake8"):
                applicable.append(config)
            elif ext in CPP_EXTENSIONS and linter_name == "clang-tidy":
                applicable.append(config)

        return applicable

    def _is_linter_available(self, linter_name: str) -> bool:
        """Check if a linter is available in PATH."""
        return shutil.which(linter_name) is not None

    def _run_single_linter(
        self, linter_name: str, file_path: str, config: dict
    ) -> list[Issue]:
        """Run a single linter on a file."""
        from .parsers import parse_clang_tidy_output, parse_flake8_output, parse_ruff_output

        cmd = self._build_command(linter_name, file_path, config)
        if not cmd:
            return []

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(file_path).parent) if Path(file_path).is_absolute() else None,
        )

        # Linters often return non-zero when issues are found
        output = result.stdout or result.stderr

        if linter_name == "ruff":
            return parse_ruff_output(output, file_path)
        elif linter_name == "flake8":
            return parse_flake8_output(output, file_path)
        elif linter_name == "clang-tidy":
            return parse_clang_tidy_output(output, file_path)

        return []

    def _build_command(
        self, linter_name: str, file_path: str, config: dict
    ) -> Optional[list[str]]:
        """Build the linter command."""
        base_cmd = LINTER_COMMANDS.get(linter_name)
        if not base_cmd:
            return None

        cmd = list(base_cmd)

        # Add config file if specified
        config_file = config.get("config_file")
        if config_file:
            if linter_name == "ruff":
                cmd.extend(["--config", config_file])
            elif linter_name == "flake8":
                cmd.extend(["--config", config_file])
            elif linter_name == "clang-tidy":
                cmd.extend(["-p", config_file])

        # Add extra args
        extra_args = config.get("extra_args", [])
        cmd.extend(extra_args)

        # Add file path
        cmd.append(file_path)

        return cmd
