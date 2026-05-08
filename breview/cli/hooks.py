"""Git hook integration for automatic pre-push review."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PRE_PUSH_HOOK = """#!/bin/sh
# BRT Code Review Agent - pre-push hook
# Runs breview review before pushing

echo "Running BRT code review..."
breview review --branch {default_branch}
exit $?
"""

PRE_PUSH_HOOK_PS1 = """# BRT Code Review Agent - pre-push hook (PowerShell)
# Add this to your PowerShell profile or run before pushing

breview review --branch {default_branch}
"""


def install_hook(repo_path: Path, default_branch: str = "main") -> bool:
    """Install the pre-push Git hook.

    Args:
        repo_path: Path to the git repository
        default_branch: Default branch to compare against

    Returns:
        True if hook was installed successfully
    """
    hooks_dir = repo_path / ".git" / "hooks"
    if not hooks_dir.exists():
        print(f"Error: {hooks_dir} does not exist. Is this a git repository?")
        return False

    hook_path = hooks_dir / "pre-push"

    if hook_path.exists():
        content = hook_path.read_text()
        if "breview" in content:
            print("Breview hook already installed.")
            return True
        print(f"Warning: Existing pre-push hook found at {hook_path}")
        print("Appending breview hook...")
        hook_content = content + "\n" + PRE_PUSH_HOOK.format(default_branch=default_branch)
    else:
        hook_content = PRE_PUSH_HOOK.format(default_branch=default_branch)

    hook_path.write_text(hook_content)
    hook_path.chmod(0o755)
    print(f"Installed pre-push hook at {hook_path}")
    return True


def uninstall_hook(repo_path: Path) -> bool:
    """Remove the breview pre-push hook.

    Args:
        repo_path: Path to the git repository

    Returns:
        True if hook was removed successfully
    """
    hook_path = repo_path / ".git" / "hooks" / "pre-push"
    if not hook_path.exists():
        print("No pre-push hook found.")
        return True

    content = hook_path.read_text()
    if "breview" not in content:
        print("Pre-push hook exists but doesn't contain breview hook.")
        return True

    # Remove breview section
    lines = content.split("\n")
    filtered = [line for line in lines if "breview" not in line.lower()]
    new_content = "\n".join(filtered).strip()

    if new_content:
        hook_path.write_text(new_content + "\n")
    else:
        hook_path.unlink()
        print("Removed empty pre-push hook.")

    print("Breview hook uninstalled.")
    return True
