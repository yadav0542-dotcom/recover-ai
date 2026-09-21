import hashlib
import hmac
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import razorpay
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.enums import PaymentFailureSource, PaymentFailureStep, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment


@dataclass(frozen=True)
class RazorpayOrderResult:
    order: Order
    razorpay_order_id: str
    mocked: bool


@dataclass(frozen=True)
class VerifiedPaymentResult:
    payment: Payment
    order: Order


class RazorpayConfigurationError(ValueError):
    pass


class RazorpaySignatureError(ValueError):
    pass


def _client() -> razorpay.Client | None:
    settings = get_settings()
    if settings.razorpay_mode.lower() != "test":
        raise RazorpayConfigurationError("Only Razorpay test mode is permitted.")
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        return None
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def _mock_order_id() -> str:
    return f"order_mock_{uuid4().hex}"


def create_test_order(session: Session, amount: int, currency: str, customer_id: str) -> RazorpayOrderResult:
    client = _client()
    if client is None:
        razorpay_order_id = _mock_order_id()
        mocked = True
    else:
        response = client.order.create({"amount": amount, "currency": currency, "receipt": f"recover_{uuid4().hex}"})
        razorpay_order_id = response["id"]
        mocked = False

    order = Order(
        razorpay_order_id=razorpay_order_id,
        customer_id=customer_id,
        amount=amount,
        currency=currency,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return RazorpayOrderResult(order, razorpay_order_id, mocked)


def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, signature: str) -> None:
    settings = get_settings()
    if settings.razorpay_mode.lower() != "test":
        raise RazorpayConfigurationError("Only Razorpay test mode is permitted.")
    if not settings.razorpay_key_secret:
        raise RazorpaySignatureError("Razorpay key secret is not configured.")
    client = razorpay.Client(auth=(settings.razorpay_key_id or "test", settings.razorpay_key_secret))
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": signature,
            }
        )
    except razorpay.errors.SignatureVerificationError as exc:
        raise RazorpaySignatureError("Invalid Razorpay payment signature.") from exc


def verify_webhook_signature(payload: bytes, signature: str) -> None:
    secret = get_settings().razorpay_webhook_secret
    if not secret:
        raise RazorpaySignatureError("Razorpay webhook secret is not configured.")
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise RazorpaySignatureError("Invalid Razorpay webhook signature.")


def _find_payment(session: Session, razorpay_payment_id: str, razorpay_order_id: str | None) -> Payment | None:
    payment = session.scalar(
        select(Payment).where(Payment.razorpay_payment_id == razorpay_payment_id)
    )
    if payment is not None or razorpay_order_id is None:
        return payment
    return session.scalar(select(Payment).where(Payment.razorpay_order_id == razorpay_order_id))


def verify_and_record_payment(
    session: Session,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    signature: str,
) -> VerifiedPaymentResult:
    verify_payment_signature(razorpay_order_id, razorpay_payment_id, signature)
    order = session.scalar(select(Order).where(Order.razorpay_order_id == razorpay_order_id))
    if order is None:
        raise ValueError("Razorpay order mapping not found.")
    payment = _find_payment(session, razorpay_payment_id, razorpay_order_id)
    if payment is None:
        payment = Payment(
            order_id=order.id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            customer_id=order.customer_id,
            amount=order.amount,
            currency=order.currency,
            payment_method="razorpay",
        )
        session.add(payment)
    payment.status = PaymentStatus.SUCCESS
    payment.failure_code = None
    payment.failure_reason = None
    payment.failure_source = None
    payment.failure_step = None
    order.status = order.status
    session.add(
        AuditLog(
            entity_type="payment",
            entity_id=str(payment.id),
            event_type="RAZORPAY_PAYMENT_VERIFIED",
            previous_state=None,
            new_state={"status": PaymentStatus.SUCCESS.value, "razorpay_payment_id": razorpay_payment_id},
            reason="Razorpay test-mode payment signature verified.",
            actor="razorpay_service",
            metadata_={"simulated": False, "mode": "test"},
        )
    )
    session.commit()
    session.refresh(payment)
    return VerifiedPaymentResult(payment, order)


def webhook_event_already_processed(session: Session, event_id: str) -> bool:
    return session.scalar(
        select(AuditLog.id).where(
            AuditLog.event_type == "RAZORPAY_WEBHOOK",
            AuditLog.metadata_["event_id"].as_string() == event_id,
        )
    ) is not None


def process_webhook_event(session: Session, event_id: str, event: dict[str, Any]) -> str:
    if webhook_event_already_processed(session, event_id):
        return "DUPLICATE"

    event_name = event.get("event", "")
    payload = event.get("payload", {})
    payment_entity = payload.get("payment", {}).get("entity", {})
    order_entity = payload.get("order", {}).get("entity", {})
    razorpay_order_id = payment_entity.get("order_id") or order_entity.get("id")
    razorpay_payment_id = payment_entity.get("id")
    payment = _find_payment(session, razorpay_payment_id, razorpay_order_id) if razorpay_payment_id else None
    order = session.scalar(select(Order).where(Order.razorpay_order_id == razorpay_order_id)) if razorpay_order_id else None

    if payment is not None and event_name in {"payment.captured", "order.paid"}:
        payment.status = PaymentStatus.SUCCESS
        payment.failure_code = None
        payment.failure_reason = None
    elif payment is not None and event_name in {"payment.failed", "payment.authorized"}:
        payment.status = PaymentStatus.FAILED if event_name == "payment.failed" else PaymentStatus.PENDING
        payment.failure_code = payment_entity.get("error_code")
        payment.failure_reason = payment_entity.get("error_description")
        payment.failure_source = PaymentFailureSource.PROVIDER
        payment.failure_step = PaymentFailureStep.AUTHORIZATION
    if order is not None and event_name in {"payment.captured", "order.paid"}:
        from app.models.enums import OrderStatus
        order.status = OrderStatus.PAID

    session.add(
        AuditLog(
            entity_type="payment" if payment is not None else "razorpay_webhook",
            entity_id=str(payment.id if payment is not None else event_id),
            event_type="RAZORPAY_WEBHOOK",
            previous_state=None,
            new_state={"event": event_name, "payment_id": razorpay_payment_id, "order_id": razorpay_order_id},
            reason="Razorpay test-mode webhook processed without executing recovery actions.",
            actor="razorpay_webhook",
            metadata_={"event_id": event_id, "event": event_name, "known_event": event_name in {"payment.captured", "order.paid", "payment.failed", "payment.authorized"}},
        )
    )
    session.commit()
    if event_name == "payment.failed" and payment is not None and order is not None:
        from app.services.recovery_workflow import process_recovery_workflow

        process_recovery_workflow(session, payment, order)
        return "PROCESSED_RECOVERY"
    return "PROCESSED"
