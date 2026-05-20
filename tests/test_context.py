"""Tests for the context builder."""

import pytest

from breview.context.builder import ContextBuilder
from breview.diff.parser import DiffParser


class TestContextBuilder:
    """Tests for ContextBuilder."""

    def setup_method(self):
        self.parser = DiffParser()
        self.builder = ContextBuilder()

    def test_build_context_empty_diff(self):
        parsed = self.parser.parse("")
        ctx = self.builder.build_context(parsed)
        assert len(ctx.file_contexts) == 0

    def test_build_context_single_file(self):
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 import os
+import sys

 def main():
"""
        parsed = self.parser.parse(diff)
        ctx = self.builder.build_context(parsed)
        assert len(ctx.file_contexts) == 1
        assert ctx.file_contexts[0].file_path == "test.py"
        assert ctx.file_contexts[0].change_type == "modified"

    def test_build_context_multiple_files(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1,2 @@
 pass
+# comment
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1 +1,2 @@
 x = 1
+y = 2
"""
        parsed = self.parser.parse(diff)
        ctx = self.builder.build_context(parsed)
        assert len(ctx.file_contexts) == 2

    def test_context_with_pr_description(self):
        parsed = self.parser.parse("")
        ctx = self.builder.build_context(parsed, pr_description="Fix bug #123")
        assert ctx.pr_description == "Fix bug #123"

    def test_context_with_author_role(self):
        parsed = self.parser.parse("")
        ctx = self.builder.build_context(parsed, author_role="intern")
        assert ctx.author_role == "intern"

    def test_diff_content_in_context(self):
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
 pass
+x = 1
"""
        parsed = self.parser.parse(diff)
        ctx = self.builder.build_context(parsed)
        assert "+x = 1" in ctx.file_contexts[0].diff_content

    def test_merge_ranges(self):
        ranges = [(1, 5), (3, 8), (10, 15)]
        merged = self.builder._merge_ranges(ranges)
        assert merged == [(1, 8), (10, 15)]

    def test_merge_overlapping_ranges(self):
        ranges = [(1, 3), (2, 4), (5, 7)]
        merged = self.builder._merge_ranges(ranges)
        assert merged == [(1, 4), (5, 7)]

    def test_extract_header_python(self):
        lines = [
            "import os",
            "import sys",
            "from pathlib import Path",
            "",
            "def main():",
            "    pass",
        ]
        header = self.builder._extract_header(lines)
        assert "import os" in header
        assert "import sys" in header
        assert "def main" not in header

    def test_extract_function_signatures_python(self):
        lines = [
            "def hello():",
            "    pass",
            "class Foo:",
            "    def bar(self):",
            "        pass",
        ]
        sigs = self.builder._extract_function_signatures(lines, "test.py")
        assert any("def hello" in s for s in sigs)
        assert any("def bar" in s for s in sigs)

    def test_full_file_review_context(self):
        content = "import os\ndef main():\n    pass"
        ctx = self.builder.build_file_context_for_full_review("new.py", content)
        assert ctx.file_path == "new.py"
        assert ctx.change_type == "added"
        assert ctx.total_lines == 3
