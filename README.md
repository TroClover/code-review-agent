# Code Review Agent

LLM-driven code review system with linter integration and profile-based review strategies.

## Features

- **LLM-Powered Review**: Detects logic errors, security vulnerabilities, and performance issues that linters miss
- **Linter Integration**: Runs ruff/flake8/clang-tidy alongside LLM review
- **Profile System**: Configure review strictness per branch (strict/standard/relaxed)
- **Cost Control**: Token budget, review cache, cost monitoring
- **Graceful Degradation**: Falls back to linter-only when LLM is unavailable
- **False Positive Handling**: Mark and filter known false positives

## Architecture

```
Orchestrator Agent
  ├── Build context
  ├── Run linters
  └── Select agents based on profile
        │
        ▼ (parallel)
        ├── Code Review Agent (logic + security + performance)
        └── Safety Agent (general security + optional domain rules)
              │
              ▼
        Aggregate → Deduplicate → Filter → Report
```

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .breview.yml.example .breview.yml
# Edit .breview.yml with your settings

# Set API key
export BREVIEW_LLM_API_KEY="your-api-key"

# Review current branch vs main
breview review

# Review with specific profile
breview review --profile strict

# Linter-only mode (no LLM)
breview review --no-llm

# Show cost report
breview review --cost-report
```

## Configuration

The `.breview.yml` file configures the review behavior:

```yaml
llm:
  provider: openai
  model: deepseek-v4-flash
  base_url: https://api.deepseek.com
  # api_key: set via BREVIEW_LLM_API_KEY env var

cost:
  max_cost_per_review: 1.0

profiles:
  - name: strict
    branch_patterns: ["main", "release/*"]
    thresholds:
      block_on_critical: 1

  - name: standard
    branch_patterns: ["*"]
    thresholds:
      block_on_critical: 3

linter:
  enabled: true
  tools:
    - name: ruff
    - name: clang-tidy
```

## CLI Options

```
breview review [OPTIONS]

Options:
  -b, --branch TEXT     Branch to compare against (default: main)
  -s, --staged          Review staged changes only
  -c, --config TEXT     Path to config file
  -p, --profile TEXT    Review profile: strict/standard/relaxed
  --no-llm              Skip LLM review, use linter only
  --no-linter           Skip linter integration
  --cost-report         Show cost report after review
```

## Testing

```bash
# Run all tests
conda activate breview
pytest tests/ -v

# Run specific test
pytest tests/test_orchestrator.py -v
```

## Documentation

- [Requirements](REQUIREMENTS.md) - Detailed requirements document
- [Task Board](TASKBOARD.md) - Development task tracking
- [Test Plan](TEST_PLAN.md) - Test case specifications
- [Coding Standard](CODING_STANDARD.md) - Code style guidelines

## License

Internal use only - BRT Department
