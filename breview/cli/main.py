"""CLI entry point for breview command (v2)."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


@click.group()
@click.version_option(version="0.2.0")
def cli() -> None:
    """BRT Code Review Agent - LLM-driven code review for your PRs."""
    pass


@cli.command()
@click.option("--branch", "-b", default=None, help="Branch to compare against (default: main)")
@click.option("--staged", "-s", is_flag=True, help="Review staged changes only")
@click.option("--config", "-c", default=None, help="Path to config file")
@click.option("--profile", "-p", default=None, type=click.Choice(["strict", "standard", "relaxed"]), help="Review profile override")
@click.option("--no-llm", is_flag=True, help="Skip LLM review, use linter + static checks only")
@click.option("--no-linter", is_flag=True, help="Skip linter integration")
@click.option("--cost-report", is_flag=True, help="Show cost report after review")
@click.option("--github", is_flag=True, help="GitHub Actions mode: publish review to PR")
def review(
    branch: Optional[str],
    staged: bool,
    config: Optional[str],
    profile: Optional[str],
    no_llm: bool,
    no_linter: bool,
    cost_report: bool,
    github: bool,
) -> None:
    """Review code changes in the current branch."""
    console.print(Panel("[bold blue]BRT Code Review Agent v2[/bold blue]", subtitle="Analyzing your code..."))

    try:
        repo_path = Path.cwd()
        config_path = Path(config) if config else None

        # GitHub Actions mode
        if github:
            asyncio.run(_run_github_review(config_path, use_llm=not no_llm, use_linter=not no_linter))
            return

        # Local mode
        # Get diff
        diff_content = _get_diff(repo_path, branch, staged)
        if not diff_content.strip():
            console.print("[yellow]No changes found to review.[/yellow]")
            return

        # Detect branch info
        target_branch = branch or "main"
        current_branch = _get_current_branch(repo_path)
        author = _get_git_user(repo_path)

        # Run review
        result = asyncio.run(_run_review(
            repo_path=repo_path,
            diff_content=diff_content,
            config_path=config_path,
            author=author,
            profile_name=profile,
            head_branch=current_branch,
            base_branch=target_branch,
            use_llm=not no_llm,
            use_linter=not no_linter,
        ))

        # Display results
        _display_results(result)

        # Show cost report if requested
        if cost_report and "cost_summary" in result:
            _display_cost_report(result["cost_summary"])

    except Exception as e:
        console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
def init(repo_path: str) -> None:
    """Initialize breview configuration in a repository."""
    config_path = Path(repo_path) / ".breview.yml"

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not click.confirm("Overwrite?"):
            return

    default_config = """# BRT Code Review Agent Configuration (v2)

llm:
  provider: openai
  model: gpt-4
  # api_key: set via BREVIEW_LLM_API_KEY env var
  temperature: 0.1
  max_tokens: 4096

cost:
  max_cost_per_review: 1.0
  enable_cache: true
  cache_ttl_hours: 24

profiles:
  - name: strict
    description: "Main/release branches: all checks, low thresholds"
    branch_patterns: ["main", "master", "release/*"]
    thresholds:
      block_on_critical: 1
      block_on_major: 3
      advisory_only: false
    checks:
      enable_style: true
      enable_logic: true
      enable_security: true
      enable_performance: true
      enable_safety: true

  - name: standard
    description: "Feature branches: core checks, medium thresholds"
    branch_patterns: ["*"]
    thresholds:
      block_on_critical: 3
      block_on_major: 5
      advisory_only: false
    checks:
      enable_style: true
      enable_logic: true
      enable_security: true
      enable_performance: true
      enable_safety: true

  - name: relaxed
    description: "Experimental/WIP branches: high-priority only"
    branch_patterns: ["wip/*", "experiment/*", "draft/*"]
    thresholds:
      block_on_critical: 10
      block_on_major: 20
      advisory_only: true
    checks:
      enable_style: false
      enable_logic: true
      enable_security: true
      enable_performance: false
      enable_safety: true

linter:
  enabled: true
  tools:
    - name: ruff
      enabled: true
    - name: clang-tidy
      enabled: true

safety_domain:
  enabled: false  # Set to true for autonomous driving code
  sensor_validation: true
  simulation_config: true
  safety_critical_paths: true
  realtime_constraints: true

exemptions:
  file_patterns:
    - "*.pb.cc"
    - "*.pb.h"
    - "*.generated.*"
    - "vendor/**"
    - "third_party/**"
  inline_marker: "breview: ignore"

default_branch: main
language: [python, cpp]
"""

    with open(config_path, "w") as f:
        f.write(default_config)

    console.print(f"[green]Created config at {config_path}[/green]")
    console.print("Edit the file to customize your review settings.")


def _get_diff(repo_path: Path, branch: Optional[str], staged: bool) -> str:
    """Get git diff from the repository."""
    if staged:
        cmd = ["git", "diff", "--cached"]
    else:
        target = branch or "main"
        cmd = ["git", "diff", f"{target}...HEAD"]

    result = subprocess.run(cmd, cwd=str(repo_path), capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[yellow]Warning: git diff failed[/yellow]")
        console.print(result.stderr, markup=False)
        return ""
    return result.stdout


def _get_current_branch(repo_path: Path) -> str:
    """Get current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_path), capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _get_git_user(repo_path: Path) -> str:
    """Get current git user name."""
    result = subprocess.run(
        ["git", "config", "user.name"],
        cwd=str(repo_path), capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


async def _run_review(
    repo_path: Path,
    diff_content: str,
    config_path: Optional[Path],
    author: str,
    profile_name: Optional[str],
    head_branch: str,
    base_branch: str,
    use_llm: bool,
    use_linter: bool,
) -> dict:
    """Run the full review pipeline."""
    from ..config.loader import load_config
    from ..diff.parser import DiffParser
    from ..models.review import PRInfo, ReviewProfile, ReviewRequest

    config = load_config(repo_path=config_path, global_path=None)
    parser = DiffParser()
    parsed_diff = parser.parse(diff_content)

    # Determine profile
    if profile_name:
        profile = ReviewProfile(profile_name)
    else:
        from ..profiles.manager import ProfileManager
        profile_manager = ProfileManager(
            profiles=config.profiles if hasattr(config, "profiles") else [],
            default_branch=getattr(config, "default_branch", "main"),
        )
        profile_config = profile_manager.get_profile(head_branch)
        profile = ReviewProfile(profile_config.name)

    # Build review request
    request = ReviewRequest(
        pr_info=PRInfo(
            repo_full_name=str(repo_path),
            pr_number=0,  # Local review, no PR number
            title=f"Local review: {head_branch} vs {base_branch}",
            author=author,
            profile=profile,
            base_branch=base_branch,
            head_branch=head_branch,
        ),
        diff_content=diff_content,
        skip_linter=not use_linter,
    )

    if use_llm:
        # Run full agent pipeline
        result = await _run_agent_pipeline(config, request, repo_path)
    else:
        # Run linter + static checks only
        result = await _run_linter_only(config, parsed_diff, request)

    return result


async def _run_agent_pipeline(config, request, repo_path: Path) -> dict:
    """Run the full multi-agent pipeline."""
    from ..agents import CodeReviewAgent, KnowledgeAgent, OrchestratorAgent, SafetyAgent
    from ..agents.base import AgentType
    from ..cost.monitor import CostMonitor
    from ..degradation.manager import DegradationManager
    from ..false_positive.store import FalsePositiveStore
    from ..knowledge.index import KnowledgeIndex
    from ..llm.client import create_llm_client
    from ..profiles.manager import ProfileManager

    try:
        llm_client = create_llm_client(config)
    except ValueError as e:
        console.print(f"[yellow]LLM not configured ({e}), falling back to linter-only.[/yellow]")
        from ..diff.parser import DiffParser
        parsed_diff = DiffParser().parse(request.diff_content)
        return await _run_linter_only(config, parsed_diff, request)

    # Create components
    cost_monitor = CostMonitor(
        max_cost_per_review=getattr(config.cost, "max_cost_per_review", 1.0) if hasattr(config, "cost") else 1.0,
        enable_cache=getattr(config.cost, "enable_cache", True) if hasattr(config, "cost") else True,
    )

    degradation_manager = DegradationManager()

    knowledge_index = KnowledgeIndex()
    fp_store = None
    if hasattr(config, "false_positive"):
        fp_store = FalsePositiveStore(
            storage_path=getattr(config.false_positive, "storage_path", ".breview/false_positives.json")
        )

    profile_manager = ProfileManager(
        profiles=config.profiles if hasattr(config, "profiles") else [],
        default_branch=getattr(config, "default_branch", "main"),
    )

    # Create agents
    code_review_agent = CodeReviewAgent(config, llm_client)
    code_review_agent.set_cost_monitor(cost_monitor)

    safety_agent = SafetyAgent(config, llm_client)
    safety_agent.set_cost_monitor(cost_monitor)

    # Enable domain rules if configured
    if hasattr(config, "safety_domain") and config.safety_domain.enabled:
        safety_agent.enable_domain_rules(True)

    agents = {
        AgentType.CODE_REVIEW: code_review_agent,
        AgentType.SAFETY: safety_agent,
        AgentType.KNOWLEDGE: KnowledgeAgent(config, knowledge_index),
    }

    orchestrator = OrchestratorAgent(
        config=config,
        agents=agents,
        profile_manager=profile_manager,
        cost_monitor=cost_monitor,
        degradation_manager=degradation_manager,
        false_positive_store=fp_store,
    )

    result = await orchestrator.run_pipeline(request)

    return {
        "issues": [
            {
                "id": i.id,
                "title": i.title,
                "description": i.description,
                "severity": i.severity.value,
                "category": i.category,
                "file_path": i.location.file_path,
                "line": i.location.line_start,
                "suggestion": i.suggestion,
                "agent": i.source_agent,
                "knowledge_ids": i.knowledge_ids,
            }
            for i in result.issues
        ],
        "summary": result.summary,
        "is_approved": result.is_approved,
        "duration": result.duration_seconds,
        "agents_executed": result.agents_executed,
        "agents_failed": result.agents_failed,
        "cost_summary": cost_monitor.get_cost_summary(),
        "degraded": degradation_manager.is_degraded,
    }


async def _run_linter_only(config, parsed_diff, request) -> dict:
    """Run linter + static checks only (no LLM)."""
    from ..linter.runner import LinterRunner

    linter_runner = None
    if hasattr(config, "linter") and config.linter.enabled:
        linter_configs = [
            {"name": t.name, "enabled": t.enabled}
            for t in config.linter.tools
        ]
        linter_runner = LinterRunner(linter_configs=linter_configs)

    all_issues = []
    if linter_runner:
        for file_change in parsed_diff.files:
            if file_change.is_binary:
                continue
            try:
                file_issues = linter_runner.run_linters(file_change.new_path)
                all_issues.extend(file_issues)
            except Exception as e:
                console.print(f"[yellow]Linter failed for {file_change.new_path}: {e}[/yellow]")

    return {
        "issues": [
            {
                "id": i.id,
                "title": i.title,
                "description": i.description,
                "severity": i.severity.value,
                "category": i.category,
                "file_path": i.location.file_path,
                "line": i.location.line_start,
                "suggestion": i.suggestion,
                "agent": i.source_agent,
            }
            for i in all_issues
        ],
        "summary": f"Linter-only review: {parsed_diff.total_files} files, +{parsed_diff.total_additions}/-{parsed_diff.total_deletions}",
        "is_approved": not any(i["severity"] == "critical" for i in all_issues),
        "duration": 0.0,
        "agents_executed": ["linter"],
        "agents_failed": [],
    }


def _display_results(result: dict) -> None:
    """Display review results in the terminal."""
    console.print()

    # Summary panel
    summary = result.get("summary", "No summary")
    is_approved = result.get("is_approved", True)
    duration = result.get("duration", 0)
    agents = result.get("agents_executed", [])
    degraded = result.get("degraded", False)

    status_title = "[green]Review Passed[/green]" if is_approved else "[red]Review Failed[/red]"
    if degraded:
        status_title += " [yellow](degraded mode)[/yellow]"

    console.print(Panel(
        f"{summary}\n\nAgents: {', '.join(agents)} | Duration: {duration:.1f}s",
        title=status_title,
    ))

    issues = result.get("issues", [])
    if not issues:
        console.print("[green]No issues found. LGTM![/green]")
        return

    # Issues table
    severity_styles = {
        "critical": "bold red",
        "major": "bold yellow",
        "minor": "blue",
        "info": "dim",
    }

    table = Table(title=f"Issues Found ({len(issues)})")
    table.add_column("Severity", style="bold", width=10)
    table.add_column("File", width=30)
    table.add_column("Line", width=6, justify="right")
    table.add_column("Title", width=40)
    table.add_column("Agent", width=12)

    for issue in issues:
        severity = issue.get("severity", "info")
        style = severity_styles.get(severity, "white")
        table.add_row(
            Text(severity.upper(), style=style),
            issue.get("file_path", ""),
            str(issue.get("line", "")),
            issue.get("title", ""),
            issue.get("agent", ""),
        )

    console.print(table)

    # Show details for critical/major issues
    critical_major = [i for i in issues if i["severity"] in ("critical", "major")]
    if critical_major:
        console.print()
        console.print("[bold]Details:[/bold]")
        for issue in critical_major:
            console.print(f"\n  [{issue['severity'].upper()}] {issue['title']}")
            console.print(f"  {issue.get('description', '')}")
            if issue.get("suggestion"):
                console.print(f"  [green]Suggestion: {issue['suggestion']}[/green]")


def _display_cost_report(cost_summary: dict) -> None:
    """Display cost report."""
    console.print()
    console.print(Panel(
        f"Current Review: ${cost_summary.get('current_review_cost_usd', 0):.4f}\n"
        f"Budget: ${cost_summary.get('max_cost_per_review_usd', 0):.2f}\n"
        f"Remaining: ${cost_summary.get('remaining_budget_usd', 0):.4f}\n"
        f"Tokens Used: {cost_summary.get('current_review_tokens', 0)}",
        title="[bold]Cost Report[/bold]",
    ))


async def _run_github_review(config_path: Optional[Path], use_llm: bool, use_linter: bool) -> None:
    """Run review in GitHub Actions mode and publish results to PR."""
    import os

    from ..github.publisher import ReviewPublisher

    # Get PR info from environment variables
    pr_number = int(os.environ.get("PR_NUMBER", "0"))
    repo_name = os.environ.get("REPO_NAME", "")
    head_sha = os.environ.get("HEAD_SHA", "")
    base_branch = os.environ.get("BASE_BRANCH", "main")
    github_token = os.environ.get("GITHUB_TOKEN")

    if not pr_number or not repo_name or not head_sha:
        console.print("[red]Error: Missing PR_NUMBER, REPO_NAME, or HEAD_SHA environment variables[/red]")
        sys.exit(1)

    console.print(f"Reviewing PR #{pr_number} in {repo_name}")
    console.print(f"Commit: {head_sha[:8]}")
    console.print(f"Base: {base_branch}")

    # Set pending status
    publisher = ReviewPublisher(token=github_token)
    await publisher.set_status(repo_name, head_sha, "pending", "Code review in progress...")

    try:
        # Get diff from git
        repo_path = Path.cwd()
        diff_content = _get_diff(repo_path, base_branch, False)

        if not diff_content.strip():
            console.print("[yellow]No changes found to review.[/yellow]")
            await publisher.set_status(repo_name, head_sha, "success", "No changes to review")
            return

        # Run review
        result = await _run_review(
            repo_path=repo_path,
            diff_content=diff_content,
            config_path=config_path,
            author="github-actions",
            profile_name=None,
            head_branch="HEAD",
            base_branch=base_branch,
            use_llm=use_llm,
            use_linter=use_linter,
        )

        # Display results locally
        _display_results(result)

        # Publish to GitHub
        issues = result.get("issues", [])
        summary = result.get("summary", "Review completed")
        is_approved = result.get("is_approved", True)

        success = await publisher.publish_review(
            repo=repo_name,
            pr_number=pr_number,
            sha=head_sha,
            summary=summary,
            issues=issues,
            is_approved=is_approved,
        )

        if success:
            console.print("[green]Review published to GitHub[/green]")
        else:
            console.print("[red]Failed to publish review to GitHub[/red]")

        # Set final status
        if is_approved:
            await publisher.set_status(repo_name, head_sha, "success", f"Review passed ({len(issues)} issue(s))")
        else:
            critical_count = len([i for i in issues if i.get("severity") == "critical"])
            await publisher.set_status(repo_name, head_sha, "failure", f"Review failed ({critical_count} critical issue(s))")

    except Exception as e:
        console.print_exception()
        await publisher.set_status(repo_name, head_sha, "error", f"Review failed: {str(e)[:100]}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
