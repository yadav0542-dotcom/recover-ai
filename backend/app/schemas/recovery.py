from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import FailureCategory, OrderStatus, PaymentStatus, RecoveryAction, RecoveryCaseStatus


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_id: UUID | None
    razorpay_payment_id: str | None
    razorpay_order_id: str | None
    customer_id: str
    amount: int
    currency: str
    payment_method: str | None
    status: PaymentStatus
    failure_code: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    razorpay_order_id: str | None
    customer_id: str
    amount: int
    currency: str
    status: OrderStatus
    cart_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class RecoveryCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    payment_id: UUID
    order_id: UUID | None
    failure_category: FailureCategory
    recoverability_probability: float | None
    recommended_action: RecoveryAction | None
    recommended_delay: int | None
    confidence: float | None
    policy_decision: RecoveryAction
    status: RecoveryCaseStatus
    created_at: datetime
    updated_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    entity_type: str
    entity_id: str
    event_type: str
    previous_state: dict[str, Any] | None
    new_state: dict[str, Any] | None
    reason: str
    actor: str
    metadata_: dict[str, Any] | None
    created_at: datetime
