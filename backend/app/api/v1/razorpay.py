from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.razorpay import (
    RazorpayOrderCreate,
    RazorpayOrderResponse,
    RazorpayPaymentResponse,
    RazorpayPaymentVerify,
)
from app.services.razorpay_service import (
    RazorpayConfigurationError,
    RazorpaySignatureError,
    create_test_order,
    verify_and_record_payment,
)


router = APIRouter(prefix="/razorpay", tags=["razorpay"])


@router.post("/orders", response_model=RazorpayOrderResponse, status_code=status.HTTP_201_CREATED)
def create_razorpay_order(payload: RazorpayOrderCreate, db: Session = Depends(get_db)) -> RazorpayOrderResponse:
    try:
        result = create_test_order(db, payload.amount, payload.currency, payload.customer_id)
    except RazorpayConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RazorpayOrderResponse(
        local_order_id=result.order.id,
        razorpay_order_id=result.razorpay_order_id,
        amount=result.order.amount,
        currency=result.order.currency,
        mode="test",
        mocked=result.mocked,
    )


@router.post("/verify", response_model=RazorpayPaymentResponse)
def verify_razorpay_payment(
    payload: RazorpayPaymentVerify,
    db: Session = Depends(get_db),
) -> RazorpayPaymentResponse:
    try:
        result = verify_and_record_payment(
            db,
            payload.razorpay_order_id,
            payload.razorpay_payment_id,
            payload.razorpay_signature,
        )
    except RazorpaySignatureError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RazorpayPaymentResponse(
        payment_id=result.payment.id,
        order_id=result.order.id,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        status=result.payment.status,
        verified=True,
    )
