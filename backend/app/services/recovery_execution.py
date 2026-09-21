from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import OrderStatus, PaymentStatus, RecoveryAction
from app.models.order import Order
from app.models.payment import Payment


RETRY_ACTIONS = {RecoveryAction.RETRY_NOW, RecoveryAction.RESUME_PAYMENT}
BLOCKED_POLICY_DECISIONS = {"DENY", "DENIED", "REJECTED", "BLOCKED"}


@dataclass(frozen=True)
class RecoveryExecutionResult:
    payment_id: UUID
    final_action: RecoveryAction
    execution_status: str
    executed: bool
    message: str
    safety_reason: str
    audit_id: UUID | None


def _audit_metadata(audit: AuditLog) -> dict[str, Any] | None:
    return audit.metadata_


def _prior_successful_execution(
    session: Session,
    payment_id: UUID,
    final_action: RecoveryAction,
) -> AuditLog | None:
    audits = session.scalars(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "payment",
            AuditLog.entity_id == str(payment_id),
            AuditLog.event_type == "RECOVERY_EXECUTION",
        )
        .order_by(AuditLog.created_at.desc())
    )
    for audit in audits:
        metadata = _audit_metadata(audit) or {}
        if metadata.get("final_action") == final_action.value and metadata.get("executed") is True:
            return audit
    return None


def _record_execution(
    session: Session,
    payment_id: UUID,
    order_id: UUID,
    final_action: RecoveryAction,
    policy_decision: str,
    retry_allowed: bool,
    execution_status: str,
    executed: bool,
    message: str,
    safety_reason: str,
) -> AuditLog:
    audit = AuditLog(
        entity_type="payment",
        entity_id=str(payment_id),
        event_type="RECOVERY_EXECUTION",
        previous_state=None,
        new_state={
            "payment_id": str(payment_id),
            "order_id": str(order_id),
            "final_action": final_action.value,
            "execution_status": execution_status,
            "executed": executed,
        },
        reason=safety_reason,
        actor="recovery_execution",
        metadata_={
            "final_action": final_action.value,
            "policy_decision": policy_decision,
            "retry_allowed": retry_allowed,
            "execution_status": execution_status,
            "executed": executed,
            "simulated": True,
        },
    )
    session.add(audit)
    session.flush()
    return audit


def execute_recovery_action(
    session: Session,
    payment: Payment,
    order: Order,
    final_action: RecoveryAction,
    policy_decision: str,
    retry_allowed: bool,
) -> RecoveryExecutionResult:
    if payment.order_id != order.id:
        raise ValueError("Payment does not belong to the supplied order")

    duplicate = _prior_successful_execution(session, payment.id, final_action)
    if duplicate is not None:
        message = "This simulated recovery action was already executed for the payment."
        safety_reason = "Duplicate execution prevented by the existing recovery execution audit record."
        audit = _record_execution(
            session,
            payment.id,
            order.id,
            final_action,
            policy_decision,
            retry_allowed,
            "DUPLICATE",
            False,
            message,
            safety_reason,
        )
        return RecoveryExecutionResult(payment.id, final_action, "DUPLICATE", False, message, safety_reason, audit.id)

    if policy_decision.upper() in BLOCKED_POLICY_DECISIONS:
        message = "Recovery action was not executed because policy explicitly blocked it."
        safety_reason = f"Policy decision {policy_decision} does not authorize execution."
        audit = _record_execution(
            session,
            payment.id,
            order.id,
            final_action,
            policy_decision,
            retry_allowed,
            "BLOCKED",
            False,
            message,
            safety_reason,
        )
        return RecoveryExecutionResult(payment.id, final_action, "BLOCKED", False, message, safety_reason, audit.id)

    if final_action in RETRY_ACTIONS and not retry_allowed:
        message = "Retry action was not executed because the policy disallowed retries."
        safety_reason = "retry_allowed is false for this policy-approved execution request."
        audit = _record_execution(
            session,
            payment.id,
            order.id,
            final_action,
            policy_decision,
            retry_allowed,
            "BLOCKED",
            False,
            message,
            safety_reason,
        )
        return RecoveryExecutionResult(payment.id, final_action, "BLOCKED", False, message, safety_reason, audit.id)

    if (
        final_action in RETRY_ACTIONS
        and payment.status is PaymentStatus.SUCCESS
        and order.status is OrderStatus.CANCELLED
    ):
        message = "Retry was not executed because a successful payment belongs to a cancelled order."
        safety_reason = "A successful payment with a cancelled order requires refund reconciliation, not a retry."
        audit = _record_execution(
            session,
            payment.id,
            order.id,
            final_action,
            policy_decision,
            retry_allowed,
            "BLOCKED",
            False,
            message,
            safety_reason,
        )
        return RecoveryExecutionResult(payment.id, final_action, "BLOCKED", False, message, safety_reason, audit.id)

    if final_action in RETRY_ACTIONS and payment.status is PaymentStatus.SUCCESS:
        message = "Retry was not executed because the payment already succeeded."
        safety_reason = "Payment already succeeded; a successful payment must never be retried."
        audit = _record_execution(
            session,
            payment.id,
            order.id,
            final_action,
            policy_decision,
            retry_allowed,
            "BLOCKED",
            False,
            message,
            safety_reason,
        )
        return RecoveryExecutionResult(payment.id, final_action, "BLOCKED", False, message, safety_reason, audit.id)

    if final_action in RETRY_ACTIONS and order.status is OrderStatus.CANCELLED:
        message = "Retry was not executed because the order is cancelled."
        safety_reason = "Cancelled orders cannot be retried."
        audit = _record_execution(
            session,
            payment.id,
            order.id,
            final_action,
            policy_decision,
            retry_allowed,
            "BLOCKED",
            False,
            message,
            safety_reason,
        )
        return RecoveryExecutionResult(payment.id, final_action, "BLOCKED", False, message, safety_reason, audit.id)

    if final_action in RETRY_ACTIONS and order.status is OrderStatus.UNKNOWN:
        message = "Retry was not executed because the order status is unknown."
        safety_reason = "Unknown order state requires reconciliation before retrying."
        audit = _record_execution(
            session,
            payment.id,
            order.id,
            final_action,
            policy_decision,
            retry_allowed,
            "BLOCKED",
            False,
            message,
            safety_reason,
        )
        return RecoveryExecutionResult(payment.id, final_action, "BLOCKED", False, message, safety_reason, audit.id)

    messages = {
        RecoveryAction.RETRY_NOW: "Simulated retry attempt recorded; no payment provider was called.",
        RecoveryAction.WAIT_AND_NOTIFY: "Simulated waiting recovery and notification record logged.",
        RecoveryAction.RESUME_PAYMENT: "Simulated resumable payment session recorded.",
        RecoveryAction.ALTERNATE_PAYMENT: "Alternate payment method recommendation recorded.",
        RecoveryAction.BLOCK_RETRY: "Blocked action recorded; no retry was attempted.",
        RecoveryAction.RECONCILE: "Simulated reconciliation task recorded.",
        RecoveryAction.REFUND_RECONCILE: "Simulated refund reconciliation tracking recorded.",
        RecoveryAction.TRACK_REFUND: "Simulated refund tracking record logged.",
        RecoveryAction.ESCALATE: "Simulated escalation record logged.",
        RecoveryAction.REVIEW: "Review record logged without executing a payment action.",
    }
    message = messages[final_action]
    safety_reason = "Action was permitted by the supplied deterministic policy result and recorded as simulation-only."
    audit = _record_execution(
        session,
        payment.id,
        order.id,
        final_action,
        policy_decision,
        retry_allowed,
        "SIMULATED",
        True,
        message,
        safety_reason,
    )
    return RecoveryExecutionResult(payment.id, final_action, "SIMULATED", True, message, safety_reason, audit.id)
