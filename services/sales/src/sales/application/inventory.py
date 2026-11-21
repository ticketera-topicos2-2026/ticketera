"""Inventory management use cases."""

from dataclasses import dataclass

from sales.application.dtos import SeatInitDTO
from sales.application.exceptions import InventoryAlreadyInitializedError
from sales.application.ports import InventoryRepository
from sales.domain.models import Money, Seat, SeatStatus


@dataclass(frozen=True)
class InitializeInventoryCommand:
    event_id: str
    seats: list[SeatInitDTO]


class InitializeInventoryUseCase:
    """Initializes seat inventory for an event."""

    def __init__(self, inventory_repo: InventoryRepository) -> None:
        self.inventory_repo = inventory_repo

    def execute(self, cmd: InitializeInventoryCommand) -> None:
        if self.inventory_repo.exists_any(cmd.event_id):
            raise InventoryAlreadyInitializedError(
                f"Inventory for event {cmd.event_id} has already been initialized"
            )

        seat_entities = [
            Seat(
                event_id=cmd.event_id,
                seat_id=s.seat_id,
                category=s.category,
                price=Money(amount_centavos=s.price_centavos, currency="ARS"),
                status=SeatStatus.AVAILABLE,
            )
            for s in cmd.seats
        ]
        self.inventory_repo.save_all(seat_entities)


class GetAvailableSeatsUseCase:
    """Queries seats for an event, optionally filtered by status."""

    def __init__(self, inventory_repo: InventoryRepository) -> None:
        self.inventory_repo = inventory_repo

    def execute(self, event_id: str, status: SeatStatus | None = SeatStatus.AVAILABLE) -> list[Seat]:
        return self.inventory_repo.find_by_event(event_id=event_id, status=status)
