import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, configure_mappers

import app.models  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.enums import FailureCategory, OrderStatus, PaymentStatus, ProviderHealth, RecoveryAction
from app.policies.recovery import PolicyInput, audit_policy_decision, evaluate_recovery_policy


@pytest.mark.parametrize(("context", "action", "allowed"), [
    (PolicyInput(PaymentStatus.SUCCESS, OrderStatus.CANCELLED), RecoveryAction.REFUND_RECONCILE, False),
    (PolicyInput(PaymentStatus.SUCCESS, OrderStatus.UNKNOWN), RecoveryAction.RECONCILE, False),
    (PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.HIGH_RISK_FRAUD_BLOCK), RecoveryAction.BLOCK_RETRY, False),
    (PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.TEMPORARY_PAYMENT_FAILURE, provider_health=ProviderHealth.DOWN), RecoveryAction.WAIT_AND_NOTIFY, False),
    (PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.CUSTOMER_CORRECTABLE), RecoveryAction.RETRY_NOW, True),
    (PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.INSUFFICIENT_FUNDS), RecoveryAction.WAIT_AND_NOTIFY, False),
    (PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.EXPIRED_CARD), RecoveryAction.ALTERNATE_PAYMENT, False),
    (PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.CUSTOMER_CANCELLED_CHECKOUT), RecoveryAction.RESUME_PAYMENT, True),
    (PolicyInput(PaymentStatus.REFUND_PENDING), RecoveryAction.TRACK_REFUND, False),
    (PolicyInput(PaymentStatus.REFUND_FAILED), RecoveryAction.ESCALATE, False),
])
def test_required_rules(context, action, allowed):
    outcome = evaluate_recovery_policy(context)
    assert (outcome.final_action, outcome.retry_allowed) == (action, allowed)


@pytest.mark.parametrize("context", [
    PolicyInput(PaymentStatus.SUCCESS, OrderStatus.CANCELLED), PolicyInput(PaymentStatus.SUCCESS, OrderStatus.UNKNOWN),
    PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.HIGH_RISK_FRAUD_BLOCK), PolicyInput(PaymentStatus.REFUND_PENDING),
    PolicyInput(PaymentStatus.REFUND_FAILED), PolicyInput(PaymentStatus.FAILED, failure_category=FailureCategory.TEMPORARY_PAYMENT_FAILURE, provider_health=ProviderHealth.DOWN),
])
def test_safety_invariants_never_retry(context):
    assert evaluate_recovery_policy(context).retry_allowed is False


def test_relationships_override_and_audit_json():
    configure_mappers()
    context = PolicyInput(PaymentStatus.SUCCESS, OrderStatus.CANCELLED, ai_recommendation=RecoveryAction.RETRY_NOW)
    outcome = evaluate_recovery_policy(context)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        audit_policy_decision(session, "payment", uuid.uuid4(), context, outcome)
        session.commit()
        audit = session.query(AuditLog).one()
    assert outcome.ai_overridden and audit.event_type == "POLICY_OVERRIDE"
    assert audit.previous_state["ai_recommendation"] == "RETRY_NOW"
    assert audit.new_state["final_action"] == "REFUND_RECONCILE"
    assert audit.actor == "policy_engine"