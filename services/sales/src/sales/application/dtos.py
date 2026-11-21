"""Data Transfer Objects for sales application layer."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SeatInitDTO:
    seat_id: str
    category: str
    price_centavos: int
