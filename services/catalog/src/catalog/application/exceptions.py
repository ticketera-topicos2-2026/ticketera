"""Errors of the catalog use cases, mapped to HTTP statuses by the API layer."""


class NotAllowedError(Exception):
    """The user holds no role that the operation requires (403)."""


class EventNotFoundError(Exception):
    """The event does not exist, is not visible to the user, or belongs to another owner (404, EC-04)."""


class IdempotencyKeyMismatchError(Exception):
    """The idempotency key was already used by this user with a different request (422, EC-05)."""
