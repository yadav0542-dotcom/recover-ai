from pydantic import BaseModel, Field
from uuid import UUID

from app.models.enums import PaymentStatus


class RazorpayOrderCreate(BaseModel):
    amount: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    customer_id: str = Field(default="razorpay_test_customer", min_length=1, max_length=100)


class RazorpayOrderResponse(BaseModel):
    local_order_id: UUID
    razorpay_order_id: str
    amount: int
    currency: str
    mode: str
    mocked: bool


class RazorpayPaymentVerify(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=1, max_length=200)


class RazorpayPaymentResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    razorpay_order_id: str
    razorpay_payment_id: str
    status: PaymentStatus
    verified: bool
