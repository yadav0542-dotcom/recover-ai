from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

from app.models.enums import (
    FailureCategory,
    PaymentFailureSource,
    PaymentFailureStep,
    PaymentStatus,
)
from app.schemas.recovery import PaymentRead


class SimulatedResult(StrEnum):
    SUCCESS = "SUCCESS"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    CUSTOMER_CORRECTABLE = "CUSTOMER_CORRECTABLE"
    HIGH_RISK_FRAUD_BLOCK = "HIGH_RISK_FRAUD_BLOCK"
    CUSTOMER_CANCELLED = "CUSTOMER_CANCELLED"
    PAYMENT_TIMEOUT = "PAYMENT_TIMEOUT"


class PaymentCreate(BaseModel):
    order_id: UUID | None = None
    customer_id: str = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    razorpay_payment_id: str | None = Field(default=None, max_length=100)
    razorpay_order_id: str | None = Field(default=None, max_length=100)
    payment_method: str | None = Field(default=None, max_length=50)
    status: PaymentStatus = PaymentStatus.PENDING
    failure_code: str | None = Field(default=None, max_length=100)
    failure_reason: str | None = Field(default=None, max_length=500)
    failure_source: PaymentFailureSource | None = None
    failure_step: PaymentFailureStep | None = None


class PaymentResponse(PaymentRead):
    model_config = ConfigDict(from_attributes=True)


class PaymentSimulationRequest(BaseModel):
    order_id: UUID
    payment_method: str = Field(min_length=1, max_length=50)
    amount: int = Field(gt=0)
    simulated_result: SimulatedResult


class PaymentSimulationResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    payment_status: PaymentStatus
    failure_category: FailureCategory | None
    failure_reason: str | None
    failure_source: PaymentFailureSource | None
    failure_step: PaymentFailureStep | None
