"""Application layer exceptions for sales bounded context."""


class ApplicationError(Exception):
    """Base application exception."""


class InventoryAlreadyInitializedError(ApplicationError):
    """Raised when trying to initialize inventory for an event that already has seats."""


class OrderNotFoundError(ApplicationError):
    """Raised when an order does not exist or customer is not authorized to access it (BOLA)."""


class IdempotencyKeyMismatchError(ApplicationError):
    """Raised when the same idempotency key is submitted with a different request payload."""

