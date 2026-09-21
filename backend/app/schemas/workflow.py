from pydantic import BaseModel
from uuid import UUID

from app.models.enums import FailureCategory, RecoveryAction


class RecoveryWorkflowRequest(BaseModel):
    payment_id: UUID


class RecoveryWorkflowResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    failure_category: FailureCategory | None
    recovery_probability: float | None
    ai_recommended_action: RecoveryAction | None
    final_policy_action: RecoveryAction | None
    retry_allowed: bool
    execution_status: str
    explanation: str
    policy_reason: str
    safety_override: bool
    audit_id: UUID | None
    policy_audit_id: UUID | None
