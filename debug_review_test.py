"""Test full code review pipeline."""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Enable debug logging
logging.basicConfig(level=logging.WARNING, format='%(name)s: %(message)s')
logger = logging.getLogger('breview.llm.parser')
logger.setLevel(logging.DEBUG)
logger2 = logging.getLogger('breview.llm.client')
logger2.setLevel(logging.DEBUG)
logger3 = logging.getLogger('breview.agents')
logger3.setLevel(logging.DEBUG)

sys.path.insert(0, str(Path(__file__).parent))

from breview.config.loader import load_config
from breview.agents import OrchestratorAgent, CodeReviewAgent, SafetyAgent
from breview.agents.base import AgentType
from breview.cost.monitor import CostMonitor
from breview.degradation.manager import DegradationManager
from breview.false_positive.store import FalsePositiveStore
from breview.knowledge.index import KnowledgeIndex
from breview.llm.client import create_llm_client
from breview.models.review import PRInfo, ReviewProfile, ReviewRequest
from breview.profiles.manager import ProfileManager


# Sample diff with intentional issues for testing
SAMPLE_DIFF = """diff --git a/sensor_processor.py b/sensor_processor.py
index abc123..def456 100644
--- a/sensor_processor.py
+++ b/sensor_processor.py
@@ -1,10 +1,45 @@
 import os
+import pickle
+import time
 from typing import List, Optional

+API_KEY = "sk-1234567890abcdef"  # Hardcoded secret
+
 class SensorProcessor:
-    def __init__(self):
-        self.buffer = []
+    def __init__(self, config_path: str):
+        self.config_path = config_path
+        self.buffer = []  # Mutable default issue
+        self.data = None
+
+    def load_config(self):
+        # Path traversal vulnerability
+        with open(self.config_path, 'r') as f:
+            config = f.read()
+        return config
+
+    def process_data(self, data: bytes):
+        # Unsafe deserialization
+        self.data = pickle.loads(data)
+
+        # No validation
+        result = self.data['points']
+        return result
+
+    def save_result(self, result, path: str):
+        # SQL injection risk (simulated)
+        query = f"INSERT INTO results VALUES ('{result}')"
+
+        # Resource leak - file not closed properly
+        f = open(path, 'w')
+        f.write(str(result))
+        # Missing f.close()
+
+    def wait_for_data(self):
+        # Sleep in critical path
+        time.sleep(5)
+        return self.buffer
+
+    def process_batch(self, items: List) -> List:
+        # O(n²) in hot path
+        results = []
+        for item in items:
+            for other in items:
+                if item != other:
+                    results.append((item, other))
+        return results
"""


async def test_review_pipeline():
    """Test the full review pipeline."""
    print("=" * 60)
    print("BRT Code Review Agent - Full Pipeline Test")
    print("=" * 60)
    print()

    # Load config
    config_path = Path(__file__).parent / ".breview.yml"
    config = load_config(repo_path=config_path)

    print(f"Config loaded: {config.llm.provider}/{config.llm.model}")
    print(f"Base URL: {config.llm.base_url}")
    print()

    # Create LLM client
    llm_client = create_llm_client(config)
    print(f"LLM client created: {llm_client.provider.__class__.__name__}")
    print()

    # Create components
    cost_monitor = CostMonitor(
        max_cost_per_review=config.cost.max_cost_per_review,
        enable_cache=config.cost.enable_cache,
    )

    degradation_manager = DegradationManager()

    profile_manager = ProfileManager(
        profiles=config.profiles,
        default_branch=config.default_branch,
    )

    # Create agents
    code_review_agent = CodeReviewAgent(config, llm_client)
    code_review_agent.set_cost_monitor(cost_monitor)

    safety_agent = SafetyAgent(config, llm_client)
    safety_agent.set_cost_monitor(cost_monitor)

    agents = {
        AgentType.CODE_REVIEW: code_review_agent,
        AgentType.SAFETY: safety_agent,
    }

    orchestrator = OrchestratorAgent(
        config=config,
        agents=agents,
        profile_manager=profile_manager,
        cost_monitor=cost_monitor,
        degradation_manager=degradation_manager,
    )

    # Create review request
    request = ReviewRequest(
        pr_info=PRInfo(
            repo_full_name="test/sensor-project",
            pr_number=42,
            title="feat: Add sensor data processing module",
            description="This PR adds a new sensor data processing module with batch processing capabilities.",
            author="testuser",
            profile=ReviewProfile.STANDARD,
            head_branch="feature/sensor-processor",
            base_branch="main",
        ),
        diff_content=SAMPLE_DIFF,
    )

    print(f"Review request created:")
    print(f"  PR #{request.pr_info.pr_number}: {request.pr_info.title}")
    print(f"  Branch: {request.pr_info.head_branch} -> {request.pr_info.base_branch}")
    print(f"  Profile: {request.pr_info.profile.value}")
    print()

    # Run review
    print("Running review pipeline...")
    print("-" * 60)

    result = await orchestrator.run_pipeline(request)

    print("-" * 60)
    print()
    print("=" * 60)
    print("Review Results")
    print("=" * 60)
    print()

    # Display summary
    print(result.summary)
    print()

    # Display issues
    if result.issues:
        print(f"Issues Found: {len(result.issues)}")
        print()

        severity_marker = {
            "critical": "[CRITICAL]",
            "major": "[MAJOR]",
            "minor": "[MINOR]",
            "info": "[INFO]",
        }

        for i, issue in enumerate(result.issues, 1):
            marker = severity_marker.get(issue.severity.value, "[INFO]")
            print(f"{i}. {marker} {issue.title}")
            print(f"   File: {issue.location.file_path}:{issue.location.line_start}")
            print(f"   Category: {issue.category}")
            print(f"   Agent: {issue.source_agent}")
            print(f"   Description: {issue.description[:100]}")
            if issue.suggestion:
                print(f"   Suggestion: {issue.suggestion[:100]}")
            print()
    else:
        print("No issues found. LGTM!")
        print()

    # Display stats
    print("=" * 60)
    print("Statistics")
    print("=" * 60)
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Agents executed: {', '.join(result.agents_executed)}")
    print(f"Agents failed: {', '.join(result.agents_failed) if result.agents_failed else 'None'}")
    print(f"Approved: {result.is_approved}")
    print(f"Blocking issues: {result.blocking_issues_count}")

    # Show issue breakdown by agent
    if result.issues:
        print()
        print("Issues by agent:")
        agent_counts = {}
        for issue in result.issues:
            agent_counts[issue.source_agent] = agent_counts.get(issue.source_agent, 0) + 1
        for agent, count in agent_counts.items():
            print(f"  {agent}: {count} issue(s)")

    # Cost summary
    cost_summary = cost_monitor.get_cost_summary()
    print()
    print("Cost Summary:")
    print(f"  Current cost: ${cost_summary['current_review_cost_usd']:.4f}")
    print(f"  Budget: ${cost_summary['max_cost_per_review_usd']:.2f}")
    print(f"  Remaining: ${cost_summary['remaining_budget_usd']:.4f}")
    print(f"  Tokens used: {cost_summary['current_review_tokens']}")

    return result


if __name__ == "__main__":
    # Write output to file to avoid encoding issues
    output_file = Path(__file__).parent / "review_output.txt"
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    result = asyncio.run(test_review_pipeline())
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Output saved to: {output_file}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Issues found: {len(result.issues)}")
    print(f"Approved: {result.is_approved}")
