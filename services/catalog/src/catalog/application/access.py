"""The authenticated user as the application sees it: a value, never a token (token-claims contract of
e1-identity-access; spec catalog/service-access)."""

from dataclasses import dataclass

ADMIN = "ADMIN"
EVENT_OWNER = "EVENT_OWNER"
CLIENT = "CLIENT"
PLATFORM_ROLES = frozenset({ADMIN, EVENT_OWNER, CLIENT})
MANAGER_ROLES = frozenset({ADMIN, EVENT_OWNER})


@dataclass(frozen=True)
class AuthenticatedUser:
    """The user identified by the token's `sub`, holding only platform roles."""

    sub: str
    roles: frozenset[str]

    @property
    def is_admin(self) -> bool:
        return ADMIN in self.roles

    @property
    def manages_events(self) -> bool:
        return bool(self.roles & MANAGER_ROLES)

    def can_manage(self, owner_id: str) -> bool:
        """An ADMIN manages every event; an EVENT_OWNER only their own (EC-04)."""
        return self.is_admin or (EVENT_OWNER in self.roles and owner_id == self.sub)
