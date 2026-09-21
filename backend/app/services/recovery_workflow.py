from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.recovery_agent import recommend_recovery
from app.ml.recovery_model import predict_recovery_probability
from app.models.enums import OrderStatus, PaymentStatus, ProviderHealth
from app.models.order import Order
from app.models.payment import Payment
from app.policies.recovery import PolicyInput, audit_policy_decision, evaluate_recovery_policy
from app.schemas.recommendation import RecoveryRecommendationRequest
from app.services.failure_classifier import classify_payment_failure
from app.services.recovery_execution import RecoveryExecutionResult, execute_recovery_action


@dataclass(frozen=True)
class RecoveryWorkflowResult:
    payment_id: UUID
    order_id: UUID
    failure_category: object | None
    recovery_probability: float | None
    ai_recommended_action: object | None
    final_policy_action: object | None
    retry_allowed: bool
    execution_status: str
    explanation: str
    policy_reason: str
    safety_override: bool
    audit_id: UUID | None
    policy_audit_id: UUID | None


def _skipped_success_result(payment: Payment, order: Order) -> RecoveryWorkflowResult:
    return RecoveryWorkflowResult(
        payment_id=payment.id,
        order_id=order.id,
        failure_category=None,
        recovery_probability=None,
        ai_recommended_action=None,
        final_policy_action=None,
        retry_allowed=False,
        execution_status="SKIPPED",
        explanation="Successful payments are not processed as failed recoveries unless reconciliation is required.",
        policy_reason="No recovery execution is permitted for a successful payment in its current order state.",
        safety_override=False,
        audit_id=None,
        policy_audit_id=None,
    )


def process_recovery_workflow(session: Session, payment: Payment, order: Order) -> RecoveryWorkflowResult:
    if payment.order_id != order.id:
        raise ValueError("Payment does not belong to the supplied order")

    if payment.status is PaymentStatus.SUCCESS and order.status not in (OrderStatus.CANCELLED, OrderStatus.UNKNOWN):
        return _skipped_success_result(payment, order)

    failure_category = None
    failure_reason = payment.failure_reason or ""
    failure_source = payment.failure_source
    if payment.status not in (PaymentStatus.SUCCESS, PaymentStatus.REFUND_PENDING, PaymentStatus.REFUND_FAILED):
        classification = classify_payment_failure(
            failure_code=payment.failure_code,
            failure_reason=payment.failure_reason,
            failure_source=payment.failure_source,
            failure_step=payment.failure_step,
            payment_method=payment.payment_method,
        )
        failure_category = classification.category
        failure_reason = classification.reason
        failure_source = classification.source

    recovery_probability = None
    if failure_category is not None:
        prediction = predict_recovery_probability(
            payment_amount=payment.amount,
            payment_method=payment.payment_method or "unknown",
            failure_category=failure_category,
            previous_attempts=0,
            time_since_failure_minutes=0,
            provider_health=ProviderHealth.UNKNOWN,
            customer_successful_payments=0,
            order_value=order.amount,
        )
        recovery_probability = prediction.recovery_probability

    recommendation = recommend_recovery(
        RecoveryRecommendationRequest(
            payment_id=payment.id,
            payment_status=payment.status,
            order_status=order.status,
            failure_category=failure_category,
            failure_reason=failure_reason,
            failure_source=failure_source,
            payment_method=payment.payment_method or "unknown",
            payment_amount=payment.amount,
            recovery_probability=recovery_probability if recovery_probability is not None else 1.0,
            provider_health=ProviderHealth.UNKNOWN,
            previous_attempt_count=0,
        )
    )
    context = PolicyInput(
        payment_status=payment.status,
        order_status=order.status,
        failure_category=failure_category,
        failure_source=failure_source,
        provider_health=ProviderHealth.UNKNOWN,
        ai_recommendation=recommendation.recommended_action,
    )
    decision = evaluate_recovery_policy(context)
    policy_audit = audit_policy_decision(session, "payment", payment.id, context, decision)
    execution: RecoveryExecutionResult = execute_recovery_action(
        session,
        payment,
        order,
        decision.final_action,
        "OVERRIDE" if decision.ai_overridden else ("ALLOW" if decision.retry_allowed else "BLOCK"),
        decision.retry_allowed,
    )
    session.commit()

    return RecoveryWorkflowResult(
        payment_id=payment.id,
        order_id=order.id,
        failure_category=failure_category,
        recovery_probability=recovery_probability,
        ai_recommended_action=recommendation.recommended_action,
        final_policy_action=decision.final_action,
        retry_allowed=decision.retry_allowed,
        execution_status=execution.execution_status,
        explanation=recommendation.explanation,
        policy_reason=decision.reason,
        safety_override=decision.ai_overridden,
        audit_id=execution.audit_id,
        policy_audit_id=policy_audit.id,
    )
