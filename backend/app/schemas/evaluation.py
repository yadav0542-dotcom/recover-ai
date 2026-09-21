from pydantic import BaseModel, Field
from uuid import UUID

from app.models.enums import (
    FailureCategory,
    OrderStatus,
    PaymentFailureSource,
    PaymentFailureStep,
    PaymentStatus,
    ProviderHealth,
    RecoveryAction,
)


class RecoveryEvaluationRequest(BaseModel):
    payment_id: UUID
    payment_status: PaymentStatus
    order_status: OrderStatus | None = None
    failure_category: FailureCategory | None = None
    failure_code: str | None = Field(default=None, max_length=100)
    failure_reason: str = Field(default="", max_length=500)
    failure_source: PaymentFailureSource | None = None
    failure_step: PaymentFailureStep | None = None
    payment_method: str = Field(min_length=1, max_length=50)
    payment_amount: int = Field(gt=0)
    recovery_probability: float | None = Field(default=None, ge=0, le=1)
    provider_health: ProviderHealth
    previous_attempt_count: int = Field(ge=0)
    customer_successful_payments: int = Field(default=0, ge=0)
    order_value: int | None = Field(default=None, gt=0)
    ai_recommended_action: RecoveryAction | None = None
    ai_confidence: float | None = Field(default=None, ge=0, le=1)


class RecoveryEvaluationResponse(BaseModel):
    payment_id: UUID
    failure_category: FailureCategory | None
    ai_recommended_action: RecoveryAction | None
    final_policy_action: RecoveryAction
    retry_allowed: bool
    policy_decision: str
    reason: str
    safety_override: bool
    confidence: float | None