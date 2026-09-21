from pydantic import BaseModel, Field
from uuid import UUID

from app.models.enums import (
    FailureCategory,
    OrderStatus,
    PaymentFailureSource,
    PaymentStatus,
    ProviderHealth,
    RecoveryAction,
)


class RecoveryRecommendationRequest(BaseModel):
    payment_id: UUID
    payment_status: PaymentStatus
    order_status: OrderStatus
    failure_category: FailureCategory | None = None
    failure_reason: str = Field(default="", max_length=500)
    failure_source: PaymentFailureSource | None = None
    payment_method: str = Field(min_length=1, max_length=50)
    payment_amount: int = Field(gt=0)
    recovery_probability: float = Field(ge=0, le=1)
    provider_health: ProviderHealth
    previous_attempt_count: int = Field(ge=0)


class RecoveryRecommendationResponse(BaseModel):
    recommended_action: RecoveryAction
    recommended_delay_minutes: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    explanation: str
    safety_notes: list[str]
