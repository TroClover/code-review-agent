"""Prompt templates for all review agents."""

from __future__ import annotations

from typing import Any


def build_system_prompt(role: str, agent_type: str) -> str:
    """Build system prompt based on author role and agent type."""
    base = "You are an expert code reviewer for an autonomous driving BRT (Better Release Testing) team."
    role_instruction = _get_role_instruction(role)

    if agent_type == "style":
        return f"{base}\n\nYou focus on code style, naming conventions, and formatting.\n\n{role_instruction}"
    elif agent_type == "code_review":
        return f"{base}\n\nYou focus on logic correctness, security vulnerabilities, and performance issues.\n\n{role_instruction}"
    elif agent_type == "safety":
        return f"{base}\n\nYou focus on safety-critical code patterns, sensor data handling, and simulation configuration.\n\n{role_instruction}"
    return base


def _get_role_instruction(role: str) -> str:
    """Get role-specific review instructions."""
    if role == "intern":
        return (
            "The author is an INTERN. Be thorough and educational:\n"
            "- Review line by line, catch all issues including minor ones\n"
            "- Explain WHY each issue is a problem\n"
            "- Provide corrected code examples\n"
            "- Use a mentoring, patient tone\n"
            "- Reference coding standards when applicable"
        )
    elif role == "senior":
        return (
            "The author is a SENIOR engineer. Focus on high-impact issues:\n"
            "- Skip trivial style issues\n"
            "- Focus on architecture, security, performance, and safety\n"
            "- Be direct and concise\n"
            "- Assume the author understands the basics"
        )
    else:
        return (
            "The author is a full-time engineer. Balance thoroughness with efficiency:\n"
            "- Catch significant issues (logic, security, performance)\n"
            "- Note style issues but don't be pedantic\n"
            "- Be professional and constructive"
        )


def build_style_review_prompt(file_context: Any, coding_standard: str = "") -> list[dict[str, str]]:
    """Build prompt for Style Agent review."""
    system = build_system_prompt(file_context.get("author_role", "full_time"), "style")

    user_content = f"""Review the following code changes for style and convention issues.

## Coding Standard Reference
{coding_standard if coding_standard else "Apply standard Python/C++ conventions (PEP 8, Google C++ Style)."}

## File: {file_context.get('file_path', 'unknown')}
## Change Type: {file_context.get('change_type', 'modified')}

### Diff:
```
{file_context.get('diff_content', '')}
```

### Surrounding Context:
```
{file_context.get('surrounding_code', '')}
```

### File Header (imports):
```
{file_context.get('file_header', '')}
```

Respond with a JSON array of issues found. Each issue should have:
- "title": short title
- "description": what's wrong and why
- "severity": "minor" or "info"
- "line_number": line number in the new file
- "suggestion": corrected code

If no issues found, return an empty array [].
Only output the JSON array, no other text."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_code_review_prompt(file_context: Any, role: str = "full_time") -> list[dict[str, str]]:
    """Build prompt for Code Review Agent (logic + security + performance)."""
    system = build_system_prompt(role, "code_review")

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
- "suggestion": how to fix

If no issues found, return [].
Only output the JSON array."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_safety_review_prompt(
    file_context: Any,
    safety_context: str = "",
    role: str = "full_time",
) -> list[dict[str, str]]:
    """Build prompt for Safety Agent review."""
    system = build_system_prompt(role, "safety")

    user_content = f"""Review the following code for safety-critical issues in an autonomous driving context.

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

Check for:
1. **Sensor data handling**: missing validation, timestamp drift, empty data, format errors
2. **Simulation configuration**: hardcoded paths, missing validation, unsafe defaults
3. **Safety-critical paths**: missing error handling in control/safety functions, no fallback behavior
4. **Resource management**: file handles not closed, connections not released, memory not freed
5. **Concurrency**: race conditions, deadlocks, shared state without synchronization
6. **Error propagation**: swallowed exceptions, missing logging in critical paths

Respond with a JSON array of issues. Each issue:
- "title": short title
- "description": detailed explanation with safety implications
- "category": "safety"
- "severity": "critical" (safety risk), "major" (potential issue), or "minor"
- "line_number": line number
- "suggestion": safe alternative

If no issues found, return [].
Only output the JSON array."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_knowledge_extraction_prompt(
    issues: list[dict[str, Any]],
    existing_knowledge: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build prompt for Knowledge Agent to extract patterns from review results."""
    system = (
        "You are a knowledge extraction specialist for a code review system. "
        "Analyze review issues and identify patterns that should become reusable knowledge entries."
    )

    issues_text = "\n".join(
        f"- [{i.get('severity')}] {i.get('title')}: {i.get('description')} (file: {i.get('location', {}).get('file_path', '?')})"
        for i in issues
    )
    existing_text = "\n".join(
        f"- [{k.get('id')}] {k.get('title')}: {k.get('category')}"
        for k in existing_knowledge[:20]
    )

    user_content = f"""Analyze these review issues and identify knowledge patterns.

## Issues Found:
{issues_text}

## Existing Knowledge (for deduplication):
{existing_text}

Identify patterns where:
1. The same type of issue appears multiple times → suggest a new knowledge entry
2. An issue matches an existing knowledge entry → note the match for linking

Respond with a JSON array of suggested knowledge entries:
- "title": concise title
- "description": detailed explanation
- "category": "naming", "error_handling", "security", "performance", "safety", "formatting", "general"
- "example_bad": code showing the bad pattern
- "example_good": code showing the correct approach
- "related_issue_ids": which issues relate to this knowledge

Only output the JSON array."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
