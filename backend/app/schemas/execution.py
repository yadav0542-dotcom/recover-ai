from pydantic import BaseModel
from uuid import UUID

from app.models.enums import RecoveryAction


class RecoveryExecutionRequest(BaseModel):
    payment_id: UUID
    order_id: UUID
    final_action: RecoveryAction
    policy_decision: str
    retry_allowed: bool


class RecoveryExecutionResponse(BaseModel):
    payment_id: UUID
    final_action: RecoveryAction
    execution_status: str
    executed: bool
    message: str
    safety_reason: str
    audit_id: UUID | None
