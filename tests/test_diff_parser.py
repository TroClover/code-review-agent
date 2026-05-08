"""Tests for the diff parser module."""

import pytest

from breview.diff.parser import ChangeType, DiffParser, ParsedDiff


class TestDiffParser:
    """Tests for DiffParser."""

    def setup_method(self):
        self.parser = DiffParser()

    def test_empty_diff(self):
        result = self.parser.parse("")
        assert isinstance(result, ParsedDiff)
        assert result.total_files == 0

    def test_simple_addition(self):
        diff = """diff --git a/test.py b/test.py
new file mode 100644
--- /dev/null
+++ b/test.py
@@ -0,0 +1,3 @@
+def hello():
+    print("hello")
+"""
        result = self.parser.parse(diff)
        assert result.total_files == 1
        assert result.files[0].new_path == "test.py"
        assert result.files[0].change_type == ChangeType.ADDED
        assert result.total_additions == 3

    def test_simple_modification(self):
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
-    print("hello")
+    print("hello world")
+    print("goodbye")
 """
        result = self.parser.parse(diff)
        assert result.total_files == 1
        assert result.files[0].change_type == ChangeType.MODIFIED

    def test_multiple_files(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1,2 @@
 pass
+# comment
diff --git b/b.py b/b.py
new file mode 100644
--- /dev/null
+++ b/b.py
@@ -0,0 +1 @@
+x = 1
"""
        result = self.parser.parse(diff)
        assert result.total_files == 2
