"""Tests for linter integration (TC-7.1~7.4)."""

import pytest
from unittest.mock import patch, MagicMock

from breview.linter.parsers import (
    parse_clang_tidy_output,
    parse_flake8_output,
    parse_ruff_output,
)
from breview.linter.runner import LinterRunner
from breview.models.issue import Severity


class TestRuffParser:
    """TC-7.1: Parse ruff output."""

    def test_parse_ruff_json_output(self):
        """Parse ruff JSON format output."""
        output = '''[
            {
                "code": "F401",
                "message": "'os' imported but unused",
                "fix": null,
                "location": {"row": 1, "column": 0},
                "end_location": {"row": 1, "column": 2},
                "filename": "example.py"
            }
        ]'''
        issues = parse_ruff_output(output, "example.py")
        assert len(issues) == 1
        assert issues[0].title.startswith("F401")
        assert issues[0].severity == Severity.MAJOR
        assert issues[0].location.file_path == "example.py"
        assert issues[0].location.line_start == 1

    def test_parse_ruff_text_output(self):
        """Parse ruff text format output."""
        output = "example.py:1:1: F401 'os' imported but unused"
        issues = parse_ruff_output(output, "example.py")
        assert len(issues) == 1
        assert issues[0].title.startswith("F401")

    def test_parse_ruff_empty_output(self):
        """Parse empty ruff output."""
        issues = parse_ruff_output("", "example.py")
        assert len(issues) == 0

    def test_parse_ruff_multiple_issues(self):
        """Parse ruff output with multiple issues."""
        output = '''[
            {"code": "F401", "message": "unused import", "location": {"row": 1, "column": 0}, "end_location": {"row": 1, "column": 10}, "filename": "test.py"},
            {"code": "E501", "message": "line too long", "location": {"row": 5, "column": 0}, "end_location": {"row": 5, "column": 100}, "filename": "test.py"}
        ]'''
        issues = parse_ruff_output(output, "test.py")
        assert len(issues) == 2

    def test_ruff_severity_mapping(self):
        """Test severity mapping for different ruff codes."""
        # F = pyflakes -> MAJOR
        output = '[{"code": "F811", "message": "test", "location": {"row": 1, "column": 0}, "end_location": {"row": 1, "column": 5}, "filename": "t.py"}]'
        issues = parse_ruff_output(output, "t.py")
        assert issues[0].severity == Severity.MAJOR

        # E = pycodestyle -> MINOR
        output = '[{"code": "E501", "message": "test", "location": {"row": 1, "column": 0}, "end_location": {"row": 1, "column": 5}, "filename": "t.py"}]'
        issues = parse_ruff_output(output, "t.py")
        assert issues[0].severity == Severity.MINOR

        # S = bandit -> CRITICAL
        output = '[{"code": "S101", "message": "test", "location": {"row": 1, "column": 0}, "end_location": {"row": 1, "column": 5}, "filename": "t.py"}]'
        issues = parse_ruff_output(output, "t.py")
        assert issues[0].severity == Severity.CRITICAL


class TestFlake8Parser:
    """TC-7.2: Parse flake8 output."""

    def test_parse_flake8_output(self):
        """Parse flake8 text format output."""
        output = "./example.py:1:1: F401 'os' imported but unused"
        issues = parse_flake8_output(output, "example.py")
        assert len(issues) == 1
        assert issues[0].title.startswith("F401")

    def test_parse_flake8_empty_output(self):
        """Parse empty flake8 output."""
        issues = parse_flake8_output("", "example.py")
        assert len(issues) == 0


class TestClangTidyParser:
    """TC-7.3: Parse clang-tidy output."""

    def test_parse_clang_tidy_warning(self):
        """Parse clang-tidy warning."""
        output = "/path/file.cpp:1:10: warning: unused variable 'x' [unused-variable]"
        issues = parse_clang_tidy_output(output, "file.cpp")
        assert len(issues) == 1
        assert issues[0].severity == Severity.MINOR
        assert "unused-variable" in issues[0].title

    def test_parse_clang_tidy_error(self):
        """Parse clang-tidy error."""
        output = "/path/file.cpp:5:3: error: use of undeclared identifier 'foo' [undeclared-var]"
        issues = parse_clang_tidy_output(output, "file.cpp")
        assert len(issues) == 1
        assert issues[0].severity == Severity.MAJOR

    def test_parse_clang_tidy_empty(self):
        """Parse empty clang-tidy output."""
        issues = parse_clang_tidy_output("", "file.cpp")
        assert len(issues) == 0


class TestLinterRunner:
    """TC-7.4: Linter runner."""

    def test_get_applicable_linters_python(self):
        """Python files should get ruff and flake8."""
        runner = LinterRunner(linter_configs=[
            {"name": "ruff", "enabled": True},
            {"name": "clang-tidy", "enabled": True},
        ])
        applicable = runner._get_applicable_linters("test.py")
        assert len(applicable) == 1
        assert applicable[0]["name"] == "ruff"

    def test_get_applicable_linters_cpp(self):
        """C++ files should get clang-tidy."""
        runner = LinterRunner(linter_configs=[
            {"name": "ruff", "enabled": True},
            {"name": "clang-tidy", "enabled": True},
        ])
        applicable = runner._get_applicable_linters("test.cpp")
        assert len(applicable) == 1
        assert applicable[0]["name"] == "clang-tidy"

    @patch("breview.linter.runner.shutil.which")
    def test_linter_not_available(self, mock_which):
        """Gracefully handle missing linter."""
        mock_which.return_value = None
        runner = LinterRunner(linter_configs=[{"name": "ruff", "enabled": True}])
        issues = runner.run_linters("test.py")
        assert len(issues) == 0
