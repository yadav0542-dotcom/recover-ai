from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.schemas.dashboard import (
    AuditEntry,
    DashboardAuditResponse,
    DashboardFailuresResponse,
    DashboardSummary,
    FailureDistributionItem,
    RecoveryMetricsResponse,
)


RECOVERY_EVENT = "RECOVERY_EXECUTION"
RETRY_ACTIONS = {"RETRY_NOW", "RESUME_PAYMENT"}
SUCCESSFUL_RECOVERY_STATUSES = {"SIMULATED"}
RECOVERY_AMOUNT_ACTIONS = {"RETRY_NOW", "RESUME_PAYMENT", "RECONCILE", "REFUND_RECONCILE"}


def _payment_status_filter(status: PaymentStatus):
    return or_(
        Payment.status.cast(String) == status.value,
        Payment.status.cast(String) == status.name,
    )


def get_dashboard_summary(session: Session) -> DashboardSummary:
    total = session.scalar(select(func.count(Payment.id))) or 0
    failed = session.scalar(select(func.count(Payment.id)).where(_payment_status_filter(PaymentStatus.FAILED))) or 0
    successful = session.scalar(select(func.count(Payment.id)).where(_payment_status_filter(PaymentStatus.SUCCESS))) or 0
    at_risk = session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(_payment_status_filter(PaymentStatus.FAILED))
    ) or 0
    recovered = session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(_payment_status_filter(PaymentStatus.SUCCESS))
    ) or 0
    blocked = _blocked_retry_count(session)
    pending = max(failed - _executed_recovery_payment_count(session), 0)
    recovery_rate = round((recovered / (recovered + at_risk)) * 100, 2) if recovered + at_risk else 0.0
    return DashboardSummary(
        revenue_at_risk=int(at_risk),
        revenue_recovered=int(recovered),
        recovery_rate=recovery_rate,
        unsafe_retries_blocked=blocked,
        pending_recoveries=pending,
        total_payments=total,
        failed_payments=failed,
        successful_payments=successful,
    )


def get_failure_distribution(session: Session) -> DashboardFailuresResponse:
    rows = session.execute(
        select(Payment.failure_code, func.count(Payment.id))
        .where(_payment_status_filter(PaymentStatus.FAILED))
        .group_by(Payment.failure_code)
        .order_by(func.count(Payment.id).desc())
    )
    failures = [
        FailureDistributionItem(failure_category=category or "UNCLASSIFIED", count=count)
        for category, count in rows
    ]
    return DashboardFailuresResponse(failures=failures)


def get_recovery_metrics(session: Session) -> RecoveryMetricsResponse:
    audits = session.scalars(
        select(AuditLog).where(AuditLog.event_type == RECOVERY_EVENT).order_by(AuditLog.created_at.desc())
    ).all()
    action_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    blocked_retry_count = 0
    recovered_amount = 0
    for audit in audits:
        metadata = audit.metadata_ or {}
        action = str(metadata.get("final_action", "UNKNOWN"))
        execution_status = str(metadata.get("execution_status", "UNKNOWN"))
        action_counts[action] += 1
        status_counts[execution_status] += 1
        if action in RETRY_ACTIONS and execution_status in {"BLOCKED", "DUPLICATE"}:
            blocked_retry_count += 1
        if execution_status in SUCCESSFUL_RECOVERY_STATUSES:
            payment = _get_payment(session, audit.entity_id)
            if payment is not None and action in RECOVERY_AMOUNT_ACTIONS:
                recovered_amount += payment.amount
    return RecoveryMetricsResponse(
        action_counts=dict(action_counts),
        execution_status_counts=dict(status_counts),
        recovered_amount=recovered_amount,
        blocked_retry_count=blocked_retry_count,
    )


def _executed_recovery_payment_count(session: Session) -> int:
    audits = session.scalars(
        select(AuditLog).where(AuditLog.event_type == RECOVERY_EVENT)
    ).all()
    return len({audit.entity_id for audit in audits if (audit.metadata_ or {}).get("executed") is True})


def _blocked_retry_count(session: Session) -> int:
    audits = session.scalars(
        select(AuditLog).where(AuditLog.event_type.in_({"POLICY_OVERRIDE", RECOVERY_EVENT}))
    ).all()
    return sum(
        1
        for audit in audits
        if (
            ((audit.metadata_ or {}).get("final_action") in RETRY_ACTIONS
            and (audit.metadata_ or {}).get("execution_status") in {"BLOCKED", "DUPLICATE"})
            or audit.event_type == "POLICY_OVERRIDE"
        )
    )


def get_audit_entries(session: Session, limit: int, offset: int) -> DashboardAuditResponse:
    total = session.scalar(select(func.count(AuditLog.id))) or 0
    audits = session.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)
    ).all()
    entries = [
        AuditEntry(
            id=str(audit.id),
            entity_type=audit.entity_type,
            entity_id=audit.entity_id,
            event_type=audit.event_type,
            reason=audit.reason,
            actor=audit.actor,
            created_at=audit.created_at,
            previous_state=_json_safe(audit.previous_state),
            new_state=_json_safe(audit.new_state),
            metadata=_json_safe(audit.metadata_),
        )
        for audit in audits
    ]
    return DashboardAuditResponse(entries=entries, limit=limit, offset=offset, total=total)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _get_payment(session: Session, entity_id: str) -> Payment | None:
    try:
        return session.get(Payment, UUID(entity_id))
    except ValueError:
        return None
