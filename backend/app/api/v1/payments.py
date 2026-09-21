from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import FailureCategory
from app.models.order import Order
from app.models.payment import Payment
from app.schemas.payments import (
    PaymentCreate,
    PaymentResponse,
    PaymentSimulationRequest,
    PaymentSimulationResponse,
)
from app.services.payment_simulation import simulate_payment


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/simulate", response_model=PaymentSimulationResponse, status_code=status.HTTP_201_CREATED)
def simulate_payment_endpoint(
    payload: PaymentSimulationRequest,
    db: Session = Depends(get_db),
) -> PaymentSimulationResponse:
    order = db.get(Order, payload.order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if payload.amount != order.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payment amount must match the order amount.",
        )

    payment, _ = simulate_payment(db, order, payload)
    failure_category = FailureCategory(payment.failure_code) if payment.failure_code else None
    return PaymentSimulationResponse(
        payment_id=payment.id,
        order_id=payment.order_id,
        payment_status=payment.status,
        failure_category=failure_category,
        failure_reason=payment.failure_reason,
        failure_source=payment.failure_source,
        failure_step=payment.failure_step,
    )


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db)) -> Payment:
    if payload.order_id is not None and db.get(Order, payload.order_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    payment = Payment(**payload.model_dump())
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A payment with this Razorpay payment ID already exists.",
        ) from exc
    db.refresh(payment)
    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: UUID, db: Session = Depends(get_db)) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    return payment
