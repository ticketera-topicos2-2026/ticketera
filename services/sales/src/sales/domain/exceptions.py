"""Domain-specific business exceptions for sales."""


class DomainError(Exception):
    """Base error for all sales domain rule violations."""


class SeatNotAvailableError(DomainError):
    """Raised when attempting to sell or reserve an unavailable seat."""


class EmptyOrderError(DomainError):
    """Raised when attempting to create an order without any tickets."""


class DuplicateSeatError(DomainError):
    """Raised when attempting to purchase duplicate seats in the same order."""


class IncompatibleCurrencyError(DomainError):
    """Raised when attempting monetary operations across different currencies."""
