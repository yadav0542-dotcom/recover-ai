from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import (
    FailureCategory,
    OrderStatus,
    PaymentFailureSource,
    PaymentStatus,
    ProviderHealth,
    RecoveryAction,
)


@dataclass(frozen=True)
class PolicyInput:
    payment_status: PaymentStatus
    order_status: OrderStatus | None = None
    failure_category: FailureCategory | None = None
    failure_source: PaymentFailureSource | None = None
    provider_health: ProviderHealth = ProviderHealth.UNKNOWN
    ai_recommendation: RecoveryAction | None = None


@dataclass(frozen=True)
class PolicyDecision:
    recommended_action: RecoveryAction | None
    final_action: RecoveryAction
    retry_allowed: bool
    reason: str
    ai_overridden: bool


def evaluate_recovery_policy(context: PolicyInput) -> PolicyDecision:
    if context.payment_status is PaymentStatus.SUCCESS and context.order_status is OrderStatus.CANCELLED:
        final, allowed, reason = RecoveryAction.REFUND_RECONCILE, False, "Retry blocked because a duplicate-payment risk exists for a successful payment with a cancelled order."
    elif context.payment_status is PaymentStatus.SUCCESS and context.order_status is OrderStatus.UNKNOWN:
        final, allowed, reason = RecoveryAction.RECONCILE, False, "Retry blocked until the successful payment and unknown order status are reconciled."
    elif context.failure_category is FailureCategory.HIGH_RISK_FRAUD_BLOCK:
        final, allowed, reason = RecoveryAction.BLOCK_RETRY, False, "Retry blocked for a high-risk or fraud-blocked payment."
    elif (
        context.failure_category is FailureCategory.TEMPORARY_PAYMENT_FAILURE
        and (
            context.provider_health is ProviderHealth.DOWN
            or context.failure_source in (PaymentFailureSource.PROVIDER, PaymentFailureSource.BANK)
        )
    ):
        final, allowed, reason = RecoveryAction.WAIT_AND_NOTIFY, False, "Immediate retry blocked while the payment provider is down."
    elif context.failure_category is FailureCategory.CUSTOMER_CORRECTABLE:
        final, allowed, reason = RecoveryAction.RETRY_NOW, True, "Customer-correctable failure may be retried after correction."
    elif context.failure_category is FailureCategory.INSUFFICIENT_FUNDS:
        final, allowed, reason = RecoveryAction.WAIT_AND_NOTIFY, False, "Immediate repeated retry blocked for insufficient funds."
    elif context.failure_category is FailureCategory.EXPIRED_CARD:
        final, allowed, reason = RecoveryAction.ALTERNATE_PAYMENT, False, "Retry blocked for the expired card; use an alternate payment method."
    elif context.failure_category is FailureCategory.CUSTOMER_CANCELLED_CHECKOUT:
        final, allowed, reason = RecoveryAction.RESUME_PAYMENT, True, "Customer may safely resume the payment checkout."
    elif context.payment_status is PaymentStatus.REFUND_PENDING:
        final, allowed, reason = RecoveryAction.TRACK_REFUND, False, "Payment retry blocked while the refund is pending."
    elif context.payment_status is PaymentStatus.REFUND_FAILED:
        final, allowed, reason = RecoveryAction.ESCALATE, False, "Payment retry blocked; failed refund requires escalation."
    else:
        final, allowed, reason = RecoveryAction.REVIEW, False, "No automatic recovery action is authorized."
    return PolicyDecision(context.ai_recommendation, final, allowed, reason, context.ai_recommendation is not None and context.ai_recommendation is not final)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def audit_policy_decision(session: Session, entity_type: str, entity_id: UUID | str, context: PolicyInput, decision: PolicyDecision) -> AuditLog:
    audit = AuditLog(entity_type=entity_type, entity_id=str(entity_id), event_type="POLICY_OVERRIDE" if decision.ai_overridden else "POLICY_DECISION", previous_state=_json_safe({"ai_recommendation": decision.recommended_action}), new_state=_json_safe({"final_action": decision.final_action, "retry_allowed": decision.retry_allowed}), reason=decision.reason, actor="policy_engine", metadata_=_json_safe({"ai_overridden": decision.ai_overridden, "provider_health": context.provider_health, "failure_category": context.failure_category}))
    session.add(audit)
    session.flush()
    return audit