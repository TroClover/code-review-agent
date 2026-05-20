"""Tests for false positive handling (TC-8.1~8.4)."""

import pytest
import tempfile
import os

from breview.false_positive.store import FalsePositiveStore
from breview.false_positive.filter import filter_false_positives
from breview.models.issue import Issue, IssueLocation, Severity


@pytest.fixture
def temp_store():
    """Create a temporary false positive store."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    store = FalsePositiveStore(storage_path=path)
    yield store
    os.unlink(path)


@pytest.fixture
def sample_issues():
    """Create sample issues for testing."""
    return [
        Issue(
            id="issue-1",
            title="Unused import",
            description="Import 'os' is unused",
            severity=Severity.MINOR,
            category="style",
            location=IssueLocation(file_path="test.py", line_start=1),
            source_agent="linter",
        ),
        Issue(
            id="issue-2",
            title="Hardcoded secret",
            description="Password hardcoded",
            severity=Severity.CRITICAL,
            category="security",
            location=IssueLocation(file_path="config.py", line_start=10),
            source_agent="safety",
        ),
    ]


class TestFalsePositiveStore:
    """TC-8.1~8.3: False positive storage."""

    def test_add_false_positive(self, temp_store):
        """TC-8.1: Adding a false positive should work."""
        entry = temp_store.add(
            issue_title="Unused import",
            file_path="test.py",
            marked_by="user1",
        )
        assert entry.issue_title == "Unused import"
        assert entry.file_path == "test.py"
        assert entry.marked_by == "user1"

    def test_is_false_positive(self, temp_store):
        """TC-8.2: Should detect known false positives."""
        temp_store.add(issue_title="Unused import", file_path="test.py")
        assert temp_store.is_false_positive("Unused import", "test.py") is True
        assert temp_store.is_false_positive("Unused import", "other.py") is False
        assert temp_store.is_false_positive("Other issue", "test.py") is False

    def test_is_false_positive_all_files(self, temp_store):
        """False positive without file_path should match all files."""
        temp_store.add(issue_title="Unused import")
        assert temp_store.is_false_positive("Unused import", "test.py") is True
        assert temp_store.is_false_positive("Unused import", "other.py") is True

    def test_get_stats(self, temp_store):
        """TC-8.3: Stats should be correct."""
        temp_store.add(issue_title="Issue 1", file_path="a.py", category="style")
        temp_store.add(issue_title="Issue 2", file_path="b.py", category="security")
        stats = temp_store.get_stats()
        assert stats["total"] == 2

    def test_remove_false_positive(self, temp_store):
        """Removing a false positive should work."""
        temp_store.add(issue_title="Unused import", file_path="test.py")
        assert temp_store.remove("Unused import", "test.py") is True
        assert temp_store.is_false_positive("Unused import", "test.py") is False

    def test_persistence(self, temp_store):
        """False positives should persist across store instances."""
        temp_store.add(issue_title="Persistent issue")
        # Create new store with same path
        new_store = FalsePositiveStore(storage_path=temp_store.storage_path)
        assert new_store.is_false_positive("Persistent issue") is True


class TestFalsePositiveFilter:
    """TC-8.4: False positive filtering."""

    def test_filter_removes_false_positives(self, temp_store, sample_issues):
        """TC-8.4: Should remove known false positives."""
        temp_store.add(issue_title="Unused import", file_path="test.py")
        filtered = filter_false_positives(sample_issues, temp_store)
        assert len(filtered) == 1
        assert filtered[0].title == "Hardcoded secret"

    def test_filter_keeps_non_false_positives(self, temp_store, sample_issues):
        """Should keep issues that are not false positives."""
        filtered = filter_false_positives(sample_issues, temp_store)
        assert len(filtered) == 2

    def test_filter_empty_issues(self, temp_store):
        """Should handle empty issue list."""
        filtered = filter_false_positives([], temp_store)
        assert len(filtered) == 0
