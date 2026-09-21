import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import FailureCategory, RecoveryAction, RecoveryCaseStatus


class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    failure_category: Mapped[FailureCategory] = mapped_column(Enum(FailureCategory))
    recoverability_probability: Mapped[float | None] = mapped_column(Float)
    recommended_action: Mapped[RecoveryAction | None] = mapped_column(Enum(RecoveryAction))
    recommended_delay: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    policy_decision: Mapped[RecoveryAction] = mapped_column(Enum(RecoveryAction))
    status: Mapped[RecoveryCaseStatus] = mapped_column(
        Enum(RecoveryCaseStatus), default=RecoveryCaseStatus.OPEN
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    payment: Mapped["Payment"] = relationship(back_populates="recovery_cases")
    order: Mapped["Order | None"] = relationship()
