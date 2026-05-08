"""Role identifier - maps GitHub users to author roles."""

from __future__ import annotations

from ..models.review import AuthorRole


class RoleIdentifier:
    """Identifies the author role based on GitHub username and team membership."""

    def __init__(self, config):
        self.interns: set[str] = set(config.roles.interns) if hasattr(config, "roles") else set()
        self.seniors: set[str] = set(config.roles.seniors) if hasattr(config, "roles") else set()

    def identify(self, username: str) -> AuthorRole:
        """Identify the role of a GitHub user.

        Args:
            username: GitHub username

        Returns:
            Author role (INTERN, FULL_TIME, or SENIOR)
        """
        if username in self.interns:
            return AuthorRole.INTERN
        if username in self.seniors:
            return AuthorRole.SENIOR
        return AuthorRole.FULL_TIME
