from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderStatus
from app.schemas.recovery import OrderRead


class OrderCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    razorpay_order_id: str | None = Field(default=None, max_length=100)
    cart_data: dict[str, Any] | None = None
    status: OrderStatus = OrderStatus.PENDING


class OrderResponse(OrderRead):
    model_config = ConfigDict(from_attributes=True)
