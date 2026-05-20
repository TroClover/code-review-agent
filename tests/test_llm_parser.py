"""Tests for LLM output parser."""

import json

import pytest

from breview.llm.parser import parse_llm_issues, _extract_json, _convert_to_issue


class TestExtractJson:
    """Tests for JSON extraction from LLM output."""

    def test_raw_json_array(self):
        text = '[{"title": "test"}]'
        assert _extract_json(text) == text

    def test_json_in_code_block(self):
        text = 'Here are the issues:\n```json\n[{"title": "test"}]\n```\nDone.'
        result = _extract_json(text)
        assert result == '[{"title": "test"}]'

    def test_json_in_plain_code_block(self):
        text = '```\n[{"title": "test"}]\n```'
        result = _extract_json(text)
        assert result == '[{"title": "test"}]'

    def test_no_json(self):
        text = 'No issues found.'
        result = _extract_json(text)
        assert result == text


class TestParseLlmIssues:
    """Tests for parsing LLM output into Issue objects."""

    def test_valid_json_array(self):
        output = json.dumps([
            {
                "title": "Unused variable",
                "description": "Variable x is unused",
                "severity": "minor",
                "category": "style",
                "line_number": 10,
                "suggestion": "Remove the variable",
            }
        ])
        issues = parse_llm_issues(output, "style", "test.py")
        assert len(issues) == 1
        assert issues[0].title == "Unused variable"
        assert issues[0].severity.value == "minor"
        assert issues[0].location.file_path == "test.py"
        assert issues[0].location.line_start == 10

    def test_multiple_issues(self):
        output = json.dumps([
            {"title": "Issue 1", "description": "d1", "severity": "critical", "line_number": 1},
            {"title": "Issue 2", "description": "d2", "severity": "major", "line_number": 5},
        ])
        issues = parse_llm_issues(output, "code_review", "test.py")
        assert len(issues) == 2

    def test_empty_array(self):
        issues = parse_llm_issues("[]", "style", "test.py")
        assert len(issues) == 0

    def test_invalid_json(self):
        issues = parse_llm_issues("not json at all", "style", "test.py")
        assert len(issues) == 0

    def test_json_with_trailing_comma(self):
        output = '[{"title": "test", "description": "d", "severity": "minor", "line_number": 1,}]'
        issues = parse_llm_issues(output, "style", "test.py")
        assert len(issues) == 1

    def test_missing_fields_use_defaults(self):
        output = json.dumps([{"title": "Minimal issue"}])
        issues = parse_llm_issues(output, "style", "test.py")
        assert len(issues) == 1
        assert issues[0].severity.value == "minor"
        assert issues[0].source_agent == "style"

    def test_invalid_severity_fallback(self):
        output = json.dumps([{"title": "t", "description": "d", "severity": "unknown", "line_number": 1}])
        issues = parse_llm_issues(output, "style", "test.py")
        assert len(issues) == 1
        assert issues[0].severity.value == "minor"

    def test_not_a_list(self):
        output = '{"title": "single issue"}'
        issues = parse_llm_issues(output, "style", "test.py")
        assert len(issues) == 0

    def test_base_line_offset(self):
        output = json.dumps([{"title": "t", "description": "d", "severity": "minor", "line_number": 5}])
        issues = parse_llm_issues(output, "style", "test.py", base_line=100)
        assert issues[0].location.line_start == 104  # 5 + 100 - 1


class TestConvertToIssue:
    """Tests for raw dict to Issue conversion."""

    def test_basic_conversion(self):
        raw = {
            "title": "Test",
            "description": "Desc",
            "severity": "major",
            "category": "logic",
            "line_number": 42,
            "suggestion": "Fix it",
        }
        issue = _convert_to_issue(raw, "code_review", "file.py", 1)
        assert issue is not None
        assert issue.title == "Test"
        assert issue.severity.value == "major"
        assert issue.category == "logic"
        assert issue.suggestion == "Fix it"

    def test_function_name_in_location(self):
        raw = {"title": "t", "description": "d", "severity": "minor", "line_number": 1, "function_name": "main"}
        issue = _convert_to_issue(raw, "style", "file.py", 1)
        assert issue.location.function_name == "main"
