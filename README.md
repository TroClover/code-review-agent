# BRT Code Review Agent

LLM-driven multi-agent code review system for autonomous driving teams.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .breview.yml.example .breview.yml
# Edit .breview.yml with your settings

# Review current branch vs main
breview review
```

## Architecture

7-agent pipeline: Orchestrator → Context → (Style | CodeReview | Safety) → Knowledge → Report

## Documentation

- [Requirements](REQUIREMENTS.md)
- [Task Board](TASKBOARD.md)
- [Coding Standard](CODING_STANDARD.md)
