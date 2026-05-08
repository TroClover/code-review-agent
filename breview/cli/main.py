"""CLI entry point for breview command."""

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
@click.version_option(version="0.1.0")
def cli() -> None:
    """BRT Code Review Agent - LLM-driven code review for your PRs."""
    pass


@cli.command()
@click.option("--branch", "-b", default=None, help="Branch to compare against (default: main)")
@click.option("--staged", "-s", is_flag=True, help="Review staged changes only")
@click.option("--config", "-c", default=None, help="Path to config file")
@click.option("--role", "-r", default=None, type=click.Choice(["intern", "full_time", "senior"]), help="Author role override")
@click.option("--no-llm", is_flag=True, help="Skip LLM review, use static checks only")
def review(branch: Optional[str], staged: bool, config: Optional[str], role: Optional[str], no_llm: bool) -> None:
    """Review code changes in the current branch."""
    console.print(Panel("[bold blue]BRT Code Review Agent[/bold blue]", subtitle="Analyzing your code..."))

    try:
        repo_path = Path.cwd()
        config_path = Path(config) if config else None

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
            author_role=role or "full_time",
            head_branch=current_branch,
            base_branch=target_branch,
            use_llm=not no_llm,
        ))

        # Display results
        _display_results(result)

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

    default_config = """# BRT Code Review Agent Configuration

llm:
  provider: openai
  model: gpt-4
  # api_key: set via BREVIEW_LLM_API_KEY env var
  temperature: 0.1
  max_tokens: 4096
  max_cost_per_review: 1.0

roles:
  interns: []
  seniors: []

agents:
  intern_agents: [style, code_review, safety]
  full_time_agents: [style, code_review, safety]
  senior_agents: [code_review, safety]

thresholds:
  block_on_critical: 1
  block_on_major: 5
  advisory_only: true

knowledge:
  auto_generate_threshold: 3
  human_comment_weight: 2.0
  agent_comment_weight: 1.0
  enable_feedback: true

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
    author_role: str,
    head_branch: str,
    base_branch: str,
    use_llm: bool,
) -> dict:
    """Run the full review pipeline."""
    from ..config.loader import load_config
    from ..diff.parser import DiffParser
    from ..models.review import AuthorRole, PRInfo, ReviewRequest

    config = load_config(repo_path=config_path, global_path=None)
    parser = DiffParser()
    parsed_diff = parser.parse(diff_content)

    # Map role string to enum
    role_map = {
        "intern": AuthorRole.INTERN,
        "full_time": AuthorRole.FULL_TIME,
        "senior": AuthorRole.SENIOR,
    }
    role_enum = role_map.get(author_role, AuthorRole.FULL_TIME)

    # Build review request
    request = ReviewRequest(
        pr_info=PRInfo(
            repo_full_name=str(repo_path),
            pr_number=0,  # Local review, no PR number
            title=f"Local review: {head_branch} vs {base_branch}",
            author=author,
            author_role=role_enum,
            base_branch=base_branch,
            head_branch=head_branch,
        ),
        diff_content=diff_content,
    )

    if use_llm:
        # Run full agent pipeline
        result = await _run_agent_pipeline(config, request, repo_path)
    else:
        # Run static checks only
        result = await _run_static_only(config, parsed_diff, request)

    return result


async def _run_agent_pipeline(config, request, repo_path: Path) -> dict:
    """Run the full multi-agent pipeline."""
    from ..agents import (
        CodeReviewAgent, ContextAgent, KnowledgeAgent,
        OrchestratorAgent, ReportAgent, SafetyAgent, StyleAgent,
    )
    from ..agents.base import AgentType
    from ..knowledge.index import KnowledgeIndex
    from ..llm.client import create_llm_client

    try:
        llm_client = create_llm_client(config)
    except ValueError as e:
        console.print(f"[yellow]LLM not configured ({e}), falling back to static checks.[/yellow]")
        from ..diff.parser import DiffParser
        parsed_diff = DiffParser().parse(request.diff_content)
        return await _run_static_only(config, parsed_diff, request)

    knowledge_index = KnowledgeIndex()

    agents = {
        AgentType.CONTEXT: ContextAgent(config, repo_path=str(repo_path)),
        AgentType.STYLE: StyleAgent(config, llm_client),
        AgentType.CODE_REVIEW: CodeReviewAgent(config, llm_client),
        AgentType.SAFETY: SafetyAgent(config, llm_client),
        AgentType.KNOWLEDGE: KnowledgeAgent(config, knowledge_index, llm_client),
        AgentType.REPORT: ReportAgent(config),
    }

    orchestrator = OrchestratorAgent(config, agents)
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
    }


async def _run_static_only(config, parsed_diff, request) -> dict:
    """Run static checks only (no LLM)."""
    from ..agents.style_agent import StyleAgent

    style_agent = StyleAgent(config, llm_client=None)

    from ..models.agent_message import AgentMessage, AgentType

    message = AgentMessage.create_task(
        AgentType.ORCHESTRATOR,
        AgentType.STYLE,
        {"request": request.model_dump(), "context": {}},
    )

    result = await style_agent.execute(message)

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
            for i in result.issues
        ],
        "summary": f"Static review: {parsed_diff.total_files} files, +{parsed_diff.total_additions}/-{parsed_diff.total_deletions}",
        "is_approved": not any(i["severity"] == "critical" for i in result.issues),
        "duration": 0.0,
        "agents_executed": ["style"],
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

    if is_approved:
        console.print(Panel(
            f"[green]{summary}[/green]\n\nAgents: {', '.join(agents)} | Duration: {duration:.1f}s",
            title="[green]Review Passed[/green]",
        ))
    else:
        console.print(Panel(
            f"[red]{summary}[/red]\n\nAgents: {', '.join(agents)} | Duration: {duration:.1f}s",
            title="[red]Review Failed[/red]",
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


if __name__ == "__main__":
    cli()
