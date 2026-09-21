from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.enums import (
    FailureCategory,
    OrderStatus,
    PaymentFailureSource,
    PaymentFailureStep,
    PaymentStatus,
)
from app.models.order import Order
from app.models.payment import Payment
from app.schemas.payments import PaymentSimulationRequest, SimulatedResult


@dataclass(frozen=True)
class SimulationOutcome:
    status: PaymentStatus
    failure_category: FailureCategory | None = None
    failure_reason: str | None = None
    failure_source: PaymentFailureSource | None = None
    failure_step: PaymentFailureStep | None = None


SIMULATION_OUTCOMES: dict[SimulatedResult, SimulationOutcome] = {
    SimulatedResult.SUCCESS: SimulationOutcome(status=PaymentStatus.SUCCESS),
    SimulatedResult.TEMPORARY_FAILURE: SimulationOutcome(
        status=PaymentStatus.FAILED,
        failure_category=FailureCategory.TEMPORARY_PAYMENT_FAILURE,
        failure_reason="The payment provider reported a temporary authorization failure.",
        failure_source=PaymentFailureSource.PROVIDER,
        failure_step=PaymentFailureStep.AUTHORIZATION,
    ),
    SimulatedResult.INSUFFICIENT_FUNDS: SimulationOutcome(
        status=PaymentStatus.FAILED,
        failure_category=FailureCategory.INSUFFICIENT_FUNDS,
        failure_reason="The issuing bank declined the payment because funds were insufficient.",
        failure_source=PaymentFailureSource.BANK,
        failure_step=PaymentFailureStep.AUTHORIZATION,
    ),
    SimulatedResult.CUSTOMER_CORRECTABLE: SimulationOutcome(
        status=PaymentStatus.FAILED,
        failure_category=FailureCategory.CUSTOMER_CORRECTABLE,
        failure_reason="The customer must correct the payment details before retrying.",
        failure_source=PaymentFailureSource.CUSTOMER,
        failure_step=PaymentFailureStep.AUTHORIZATION,
    ),
    SimulatedResult.HIGH_RISK_FRAUD_BLOCK: SimulationOutcome(
        status=PaymentStatus.FAILED,
        failure_category=FailureCategory.HIGH_RISK_FRAUD_BLOCK,
        failure_reason="The payment was blocked by the provider's fraud controls.",
        failure_source=PaymentFailureSource.PROVIDER,
        failure_step=PaymentFailureStep.AUTHORIZATION,
    ),
    SimulatedResult.CUSTOMER_CANCELLED: SimulationOutcome(
        status=PaymentStatus.FAILED,
        failure_category=FailureCategory.CUSTOMER_CANCELLED_CHECKOUT,
        failure_reason="The customer cancelled checkout before payment completion.",
        failure_source=PaymentFailureSource.CUSTOMER,
        failure_step=PaymentFailureStep.CHECKOUT,
    ),
    SimulatedResult.PAYMENT_TIMEOUT: SimulationOutcome(
        status=PaymentStatus.FAILED,
        failure_category=FailureCategory.TEMPORARY_PAYMENT_FAILURE,
        failure_reason="The payment provider did not respond before the authorization timed out.",
        failure_source=PaymentFailureSource.SYSTEM,
        failure_step=PaymentFailureStep.AUTHORIZATION,
    ),
}


def simulate_payment(
    db: Session,
    order: Order,
    payload: PaymentSimulationRequest,
) -> tuple[Payment, Order]:
    outcome = SIMULATION_OUTCOMES[payload.simulated_result]
    payment = Payment(
        order_id=order.id,
        razorpay_payment_id=f"sim_{uuid4().hex}",
        razorpay_order_id=order.razorpay_order_id,
        customer_id=order.customer_id,
        amount=payload.amount,
        currency=order.currency,
        payment_method=payload.payment_method,
        status=outcome.status,
        failure_code=outcome.failure_category.value if outcome.failure_category else None,
        failure_reason=outcome.failure_reason,
        failure_source=outcome.failure_source,
        failure_step=outcome.failure_step,
    )
    order.status = OrderStatus.PAID if outcome.status is PaymentStatus.SUCCESS else OrderStatus.PENDING
    db.add(payment)
    db.commit()
    db.refresh(payment)
    db.refresh(order)
    return payment, order