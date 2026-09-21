from pydantic import BaseModel, Field, model_validator
from uuid import UUID

from app.models.enums import (
    FailureCategory,
    PaymentFailureSource,
    PaymentFailureStep,
)
from app.schemas.payments import SimulatedResult


class FailureClassificationRequest(BaseModel):
    payment_id: UUID | None = None
    simulated_result: SimulatedResult | None = None
    failure_code: str | None = Field(default=None, max_length=100)
    failure_reason: str | None = Field(default=None, max_length=500)
    failure_source: PaymentFailureSource | None = None
    failure_step: PaymentFailureStep | None = None
    payment_method: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def require_payment_or_failure_details(self) -> "FailureClassificationRequest":
        has_details = any(
            value is not None
            for value in (
                self.simulated_result,
                self.failure_code,
                self.failure_reason,
                self.failure_source,
                self.failure_step,
                self.payment_method,
            )
        )
        if self.payment_id is None and not has_details:
            raise ValueError("payment_id or failure details are required")
        return self


class FailureClassificationResponse(BaseModel):
    payment_id: UUID | None
    failure_category: FailureCategory
    reason: str
    failure_source: PaymentFailureSource
    failure_step: PaymentFailureStep
