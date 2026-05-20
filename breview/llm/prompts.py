"""Prompt templates for all review agents.

v2: Uses profile-based instructions instead of role-based.
"""

from __future__ import annotations

from typing import Any


def build_system_prompt(profile: str, agent_type: str, custom_prompt: str = "") -> str:
    """Build system prompt based on review profile and agent type."""
    base = "You are an expert code reviewer for an autonomous driving BRT (Better Release Testing) team."
    profile_instruction = _get_profile_instruction(profile)

    if agent_type == "code_review":
        return f"{base}\n\nYou focus on logic correctness, security vulnerabilities, and performance issues.\n\n{profile_instruction}"
    elif agent_type == "safety":
        return f"{base}\n\nYou focus on safety-critical code patterns, sensor data handling, and simulation configuration.\n\n{profile_instruction}"
    return base


def _get_profile_instruction(profile: str) -> str:
    """Get profile-specific review instructions."""
    if profile == "strict":
        return (
            "Review profile: STRICT (main/release branches).\n"
            "- Review thoroughly, catch all issues including minor ones\n"
            "- Flag any deviation from best practices\n"
            "- Be strict about error handling and edge cases\n"
            "- All issues matter, even style suggestions"
        )
    elif profile == "relaxed":
        return (
            "Review profile: RELAXED (experimental/WIP branches).\n"
            "- Focus only on critical and major issues\n"
            "- Skip trivial style issues\n"
            "- Focus on security vulnerabilities and crash risks\n"
            "- Be concise and direct"
        )
    else:  # standard
        return (
            "Review profile: STANDARD (feature branches).\n"
            "- Catch significant issues (logic, security, performance)\n"
            "- Note style issues but don't be pedantic\n"
            "- Be professional and constructive\n"
            "- Provide actionable suggestions"
        )


def build_code_review_prompt(
    file_context: Any,
    profile: str = "standard",
    custom_prompt: str = "",
) -> list[dict[str, str]]:
    """Build prompt for Code Review Agent (logic + security + performance)."""
    system = build_system_prompt(profile, "code_review", custom_prompt)

    custom_section = ""
    if custom_prompt:
        custom_section = f"\n\n### Team-Specific Focus:\n{custom_prompt}"

    user_content = f"""Review the following code changes for logic correctness, security vulnerabilities, and performance issues.

## File: {file_context.get('file_path', 'unknown')}
## Change Type: {file_context.get('change_type', 'modified')}
## Language: {file_context.get('language', 'python')}

### Diff:
```
{file_context.get('diff_content', '')}
```

### Surrounding Context:
```
{file_context.get('surrounding_code', '')}
```

### File Header:
```
{file_context.get('file_header', '')}
```

### Function Signatures in File:
```
{chr(10).join(file_context.get('function_signatures', []))}
```
{custom_section}

Check for:
1. **Logic errors**: boundary conditions, off-by-one, null/None handling, type mismatches
2. **Security**: hardcoded secrets, injection, unsafe deserialization, path traversal
3. **Performance**: unnecessary copies, O(n²) in hot paths, memory leaks, blocking calls

Respond with a JSON array of issues. Each issue:
- "title": short title
- "description": detailed explanation
- "category": "logic", "security", or "performance"
- "severity": "critical", "major", "minor", or "info"
- "line_number": line number in new file
- "suggestion": how to fix (be specific, provide corrected code)

If no issues found, return [].
Only output the JSON array."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_safety_review_prompt(
    file_context: Any,
    safety_context: str = "",
    profile: str = "standard",
    custom_prompt: str = "",
) -> list[dict[str, str]]:
    """Build prompt for Safety Agent review."""
    system = build_system_prompt(profile, "safety", custom_prompt)

    custom_section = ""
    if custom_prompt:
        custom_section = f"\n\n### Team-Specific Focus:\n{custom_prompt}"

    user_content = f"""Review the following code for safety-critical issues.

## File: {file_context.get('file_path', 'unknown')}
## Change Type: {file_context.get('change_type', 'modified')}
## Language: {file_context.get('language', 'python')}

### Safety Context:
{safety_context if safety_context else "No additional safety context available."}

### Diff:
```
{file_context.get('diff_content', '')}
```

### Surrounding Context:
```
{file_context.get('surrounding_code', '')}
```
{custom_section}

Check for:
1. **Security vulnerabilities**: hardcoded credentials, SQL injection, path traversal, unsafe deserialization
2. **Resource management**: file handles not closed, connections not released, memory not freed
3. **Error handling**: swallowed exceptions, missing error handling in critical paths
4. **Concurrency**: race conditions, deadlocks, shared state without synchronization
5. **Safety-critical paths**: missing fallback behavior, unsafe defaults

Respond with a JSON array of issues. Each issue:
- "title": short title
- "description": detailed explanation with safety implications
- "category": "safety"
- "severity": "critical" (safety risk), "major" (potential issue), or "minor"
- "line_number": line number
- "suggestion": safe alternative with corrected code

If no issues found, return [].
Only output the JSON array."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_safety_domain_prompt(
    file_context: Any,
    domain_rules: dict[str, bool],
    profile: str = "standard",
) -> list[dict[str, str]]:
    """Build prompt for autonomous driving domain-specific safety checks."""
    system = build_system_prompt(profile, "safety")

    # Build domain-specific check list
    checks = []
    if domain_rules.get("sensor_validation", True):
        checks.append("- Sensor data validation: timestamp drift, empty data, format errors")
    if domain_rules.get("simulation_config", True):
        checks.append("- Simulation configuration: hardcoded paths, missing validation, unsafe defaults")
    if domain_rules.get("safety_critical_paths", True):
        checks.append("- Safety-critical paths: missing error handling in control/safety functions")
    if domain_rules.get("realtime_constraints", True):
        checks.append("- Realtime constraints: sleep/delay in critical paths, blocking calls")

    checks_text = "\n".join(checks) if checks else "- No domain-specific checks enabled"

    user_content = f"""Review the following code for autonomous driving domain-specific safety issues.

## File: {file_context.get('file_path', 'unknown')}
## Language: {file_context.get('language', 'python')}

### Diff:
```
{file_context.get('diff_content', '')}
```

### Domain-Specific Checks:
{checks_text}

Respond with a JSON array of issues. Each issue:
- "title": short title
- "description": detailed explanation with domain context
- "category": "safety"
- "severity": "critical" or "major"
- "line_number": line number
- "suggestion": safe alternative

If no issues found, return [].
Only output the JSON array."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
