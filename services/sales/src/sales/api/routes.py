"""Sales router implementing inventory, seat queries, ticket purchases, and orders."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from sales.api.auth import CurrentUser, get_current_user, require_role
from sales.api.schemas import (
    InventoryInitRequest,
    OrderResponse,
    PurchaseRequest,
    SeatResponse,
    TicketResponse,
)
from sales.application.dtos import SeatInitDTO
from sales.application.exceptions import (
    IdempotencyKeyMismatchError,
    InventoryAlreadyInitializedError,
    OrderNotFoundError,
)
from sales.application.inventory import (
    GetAvailableSeatsUseCase,
    InitializeInventoryCommand,
    InitializeInventoryUseCase,
)
from sales.application.orders import GetOrderUseCase, PurchaseTicketsCommand, PurchaseTicketsUseCase
from sales.domain.exceptions import SeatNotAvailableError
from sales.domain.models import SeatStatus

router = APIRouter()


@router.post(
    "/events/{event_id}/inventory",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMIN"))],
)
def initialize_inventory(
    event_id: str,
    payload: InventoryInitRequest,
    request: Request,
) -> dict[str, str]:
    uow = request.app.state.uow_factory()
    use_case = InitializeInventoryUseCase(uow)
    dtos = [
        SeatInitDTO(seat_id=s.seat_id, category=s.category, price_centavos=s.price_centavos)
        for s in payload.seats
    ]
    try:
        use_case.execute(InitializeInventoryCommand(event_id=event_id, seats=dtos))
    except InventoryAlreadyInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return {"status": "created"}


@router.get(
    "/events/{event_id}/seats",
    response_model=list[SeatResponse],
)
def get_available_seats(
    event_id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    seat_status: Annotated[SeatStatus | None, Query(alias="status")] = SeatStatus.AVAILABLE,
) -> list[SeatResponse]:
    with request.app.state.uow_factory() as uow:
        use_case = GetAvailableSeatsUseCase(uow.inventory_repo)
        seats = use_case.execute(event_id=event_id, status=seat_status)
    return [
        SeatResponse(
            seat_id=s.seat_id,
            category=s.category,
            price_centavos=s.price.amount_centavos,
            status=s.status.value,
        )
        for s in seats
    ]


@router.post(
    "/events/{event_id}/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def purchase_tickets(
    event_id: str,
    payload: PurchaseRequest,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderResponse:
    if not current_user.has_role("CLIENT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires CLIENT role",
        )

    # Validate Idempotency-Key header (400 if missing or invalid UUID)
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Idempotency-Key header",
        )
    try:
        uuid.UUID(idempotency_key)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Idempotency-Key UUID format",
        ) from err

    # Validate duplicates in seat_ids
    if len(payload.seat_ids) != len(set(payload.seat_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate seat_ids in purchase request",
        )

    uow = request.app.state.uow_factory()
    use_case = PurchaseTicketsUseCase(uow)
    try:
        result = use_case.execute(
            PurchaseTicketsCommand(
                customer_id=current_user.customer_id,
                event_id=event_id,
                seat_ids=payload.seat_ids,
                idempotency_key=idempotency_key,
            )
        )
    except IdempotencyKeyMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except SeatNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    order = result.order
    return OrderResponse(
        order_id=order.order_id,
        event_id=order.event_id,
        customer_id=order.customer_id,
        total_amount_centavos=order.total_amount.amount_centavos,
        currency=order.total_amount.currency,
        status=order.status.value,
        tickets=[
            TicketResponse(ticket_id=t.ticket_id, seat_id=t.seat_id, code=t.code) for t in order.tickets
        ],
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
)
def get_order(
    order_id: str,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OrderResponse:
    with request.app.state.uow_factory() as uow:
        use_case = GetOrderUseCase(uow.order_repo)
        try:
            order = use_case.execute(
                order_id=order_id,
                requesting_user_id=current_user.customer_id,
                is_admin=current_user.has_role("ADMIN"),
            )
        except OrderNotFoundError as exc:
            # BOLA protection: 404 instead of 403
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            ) from exc

    return OrderResponse(
        order_id=order.order_id,
        event_id=order.event_id,
        customer_id=order.customer_id,
        total_amount_centavos=order.total_amount.amount_centavos,
        currency=order.total_amount.currency,
        status=order.status.value,
        tickets=[
            TicketResponse(ticket_id=t.ticket_id, seat_id=t.seat_id, code=t.code) for t in order.tickets
        ],
    )
