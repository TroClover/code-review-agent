"""Tests for cost control (TC-9.1~9.5)."""

import pytest
import time

from breview.cost.monitor import CostMonitor


class TestCostMonitor:
    """TC-9.1~9.5: Cost monitoring and budget control."""

    def test_check_budget_within_limit(self):
        """TC-9.1: Budget check should pass when within limit."""
        monitor = CostMonitor(max_cost_per_review=1.0)
        assert monitor.check_budget() is True

    def test_check_budget_exceeded(self):
        """TC-9.2: Budget check should fail when exceeded."""
        monitor = CostMonitor(max_cost_per_review=0.01)
        monitor.record_usage(input_tokens=1000, output_tokens=1000, cost_usd=0.05, model="gpt-4")
        assert monitor.check_budget() is False

    def test_record_usage(self):
        """TC-9.1: Token usage should be tracked."""
        monitor = CostMonitor(max_cost_per_review=1.0)
        monitor.record_usage(input_tokens=100, output_tokens=50, cost_usd=0.01, model="gpt-4")
        assert monitor._current_tokens == 150
        assert monitor._current_cost == 0.01

    def test_get_cost_summary(self):
        """TC-9.1: Cost summary should include all fields."""
        monitor = CostMonitor(max_cost_per_review=1.0)
        monitor.record_usage(input_tokens=100, output_tokens=50, cost_usd=0.05, model="gpt-4")
        summary = monitor.get_cost_summary()
        assert summary["current_review_cost_usd"] == 0.05
        assert summary["current_review_tokens"] == 150
        assert summary["max_cost_per_review_usd"] == 1.0
        assert summary["remaining_budget_usd"] == 0.95
        assert summary["budget_exceeded"] is False

    def test_cache_hit(self):
        """TC-9.3: Cache should return cached result."""
        monitor = CostMonitor(enable_cache=True)
        monitor.cache_result("diff content", "test.py", '[{"title": "test"}]')
        result = monitor.get_cached_result("diff content", "test.py")
        assert result == '[{"title": "test"}]'

    def test_cache_miss(self):
        """TC-9.4: Cache should return None for different diff."""
        monitor = CostMonitor(enable_cache=True)
        monitor.cache_result("diff content", "test.py", '[{"title": "test"}]')
        result = monitor.get_cached_result("different diff", "test.py")
        assert result is None

    def test_cache_disabled(self):
        """Cache should not work when disabled."""
        monitor = CostMonitor(enable_cache=False)
        monitor.cache_result("diff content", "test.py", '[{"title": "test"}]')
        result = monitor.get_cached_result("diff content", "test.py")
        assert result is None

    def test_record_review(self):
        """Review cost should be recorded."""
        monitor = CostMonitor(max_cost_per_review=1.0)
        monitor.record_review(
            review_id="test-1",
            total_tokens=1000,
            input_tokens=800,
            output_tokens=200,
            cost_usd=0.05,
            model="gpt-4",
            files_reviewed=5,
            duration_seconds=10.0,
        )
        report = monitor.get_historical_report()
        assert report["total_reviews"] == 1
        assert report["total_cost_usd"] == 0.05
