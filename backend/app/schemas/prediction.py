from pydantic import BaseModel, Field
from uuid import UUID

from app.models.enums import FailureCategory, ProviderHealth


class RecoveryPredictionRequest(BaseModel):
    payment_id: UUID | None = None
    payment_amount: int = Field(gt=0)
    payment_method: str = Field(min_length=1, max_length=50)
    failure_category: FailureCategory
    previous_attempts: int = Field(ge=0)
    time_since_failure_minutes: int = Field(ge=0)
    provider_health: ProviderHealth
    customer_successful_payments: int = Field(ge=0)
    order_value: int = Field(gt=0)


class RecoveryPredictionResponse(BaseModel):
    payment_id: UUID | None
    recovery_probability: float = Field(ge=0, le=1)
    model_version: str
    important_features: dict[str, int | str]
    explanation: str
