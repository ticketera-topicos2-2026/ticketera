"""Pydantic schemas for sales HTTP request and response models matching openapi.yaml."""

from pydantic import BaseModel, ConfigDict, Field


class SeatItem(BaseModel):
    seat_id: str
    category: str
    price_centavos: int = Field(ge=0)


class InventoryInitRequest(BaseModel):
    seats: list[SeatItem] = Field(min_length=1)


class SeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seat_id: str
    category: str
    price_centavos: int
    status: str


class PurchaseRequest(BaseModel):
    seat_ids: list[str] = Field(min_length=1)


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    seat_id: str
    code: str


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    event_id: str
    customer_id: str
    total_amount_centavos: int
    currency: str = "ARS"
    status: str = "CONFIRMED"
    tickets: list[TicketResponse]
