"""Tests for the role identification system."""

import pytest

from breview.config.schema import BreviewConfig, RoleMapping
from breview.models.review import AuthorRole
from breview.roles.identifier import RoleIdentifier


class TestRoleIdentifier:
    """Tests for RoleIdentifier."""

    def setup_method(self):
        config = BreviewConfig(roles=RoleMapping(
            interns=["intern-001", "intern-002"],
            seniors=["senior-001"],
        ))
        self.identifier = RoleIdentifier(config)

    def test_intern_detection(self):
        assert self.identifier.identify("intern-001") == AuthorRole.INTERN
        assert self.identifier.identify("intern-002") == AuthorRole.INTERN

    def test_senior_detection(self):
        assert self.identifier.identify("senior-001") == AuthorRole.SENIOR

    def test_full_time_default(self):
        assert self.identifier.identify("regular-dev") == AuthorRole.FULL_TIME
        assert self.identifier.identify("some-random-user") == AuthorRole.FULL_TIME

    def test_empty_config(self):
        config = BreviewConfig(roles=RoleMapping())
        identifier = RoleIdentifier(config)
        assert identifier.identify("anyone") == AuthorRole.FULL_TIME
