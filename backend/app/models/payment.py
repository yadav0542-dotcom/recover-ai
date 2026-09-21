import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    PaymentFailureSource,
    PaymentFailureStep,
    PaymentStatus,
)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id"),
        index=True,
        nullable=True,
    )

    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
    )

    razorpay_order_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )

    customer_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )

    amount: Mapped[int] = mapped_column(Integer)

    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
    )

    payment_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
            name="paymentstatus",
        ),
        default=PaymentStatus.PENDING,
    )

    failure_code: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    failure_source: Mapped[PaymentFailureSource | None] = mapped_column(
        Enum(
            PaymentFailureSource,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
            name="paymentfailuresource",
        ),
        nullable=True,
    )

    failure_step: Mapped[PaymentFailureStep | None] = mapped_column(
        Enum(
            PaymentFailureStep,
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
            name="paymentfailurestep",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    order: Mapped["Order | None"] = relationship(
        back_populates="payments",
    )

    recovery_cases: Mapped[list["RecoveryCase"]] = relationship(
        back_populates="payment",
    )