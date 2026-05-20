"""Test raw LLM output for code review."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from breview.config.loader import load_config
from breview.llm.client import create_llm_client
from breview.llm.prompts import build_code_review_prompt


SAMPLE_DIFF = """diff --git a/sensor_processor.py b/sensor_processor.py
--- a/sensor_processor.py
+++ b/sensor_processor.py
@@ -1,5 +1,20 @@
 import os
+import pickle
+import time
 from typing import List, Optional

+API_KEY = "sk-1234567890abcdef"
+
 class SensorProcessor:
-    def __init__(self):
-        self.buffer = []
+    def __init__(self, config_path: str):
+        self.config_path = config_path
+        self.buffer = []
+
+    def load_config(self):
+        with open(self.config_path, 'r') as f:
+            config = f.read()
+        return config
+
+    def process_data(self, data: bytes):
+        self.data = pickle.loads(data)
+        result = self.data['points']
+        return result
"""


async def test_raw_llm():
    """Test raw LLM output."""
    print("=" * 60)
    print("Raw LLM Output Test")
    print("=" * 60)

    # Load config
    config_path = Path(__file__).parent / ".breview.yml"
    config = load_config(repo_path=config_path)
    llm_client = create_llm_client(config)

    # Build prompt
    file_context = {
        "file_path": "sensor_processor.py",
        "change_type": "modified",
        "diff_content": SAMPLE_DIFF,
        "surrounding_code": "",
        "file_header": "import os\nimport pickle\nimport time",
        "function_signatures": ["class SensorProcessor:", "def __init__:", "def load_config:", "def process_data:"],
        "language": "python",
        "author_role": "full_time",
    }

    messages = build_code_review_prompt(file_context, profile="standard")

    print("Sending request to LLM...")
    print(f"Model: {config.llm.model}")
    print()

    try:
        response = await llm_client.complete(
            messages=messages,
            model=config.llm.model,
            temperature=0.1,
            max_tokens=4096,
        )

        # Save to file to avoid encoding issues
        output_file = Path(__file__).parent / "llm_output.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(response.content)

        print(f"Raw LLM Response saved to: {output_file}")
        print(f"Response length: {len(response.content)} characters")
        print(f"Tokens: {response.input_tokens} in / {response.output_tokens} out")
        print(f"Cost: ${response.cost_usd:.6f}")

        # Try to parse
        from breview.llm.parser import parse_llm_issues
        issues = parse_llm_issues(response.content, "code_review", "sensor_processor.py")
        print()
        print(f"Parsed {len(issues)} issues:")
        for issue in issues:
            print(f"  - [{issue.severity.value}] {issue.title}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_raw_llm())
