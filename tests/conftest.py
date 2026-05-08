"""Shared test fixtures."""

import pytest

from breview.config.schema import BreviewConfig


@pytest.fixture
def default_config() -> BreviewConfig:
    """Default configuration for tests."""
    return BreviewConfig()


@pytest.fixture
def sample_diff() -> str:
    """Sample unified diff for testing."""
    return """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,5 +1,8 @@
 import os
+import sys

-def main():
-    print("hello")
-    return 0
+def main(args=None):
+    if args is None:
+        args = sys.argv[1:]
+    print(f"hello {args}")
+    return 0
"""
