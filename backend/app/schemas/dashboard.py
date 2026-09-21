from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    revenue_at_risk: int
    revenue_recovered: int
    recovery_rate: float
    unsafe_retries_blocked: int
    pending_recoveries: int
    total_payments: int
    failed_payments: int
    successful_payments: int


class FailureDistributionItem(BaseModel):
    failure_category: str
    count: int


class DashboardFailuresResponse(BaseModel):
    failures: list[FailureDistributionItem]


class RecoveryMetricsResponse(BaseModel):
    action_counts: dict[str, int]
    execution_status_counts: dict[str, int]
    recovered_amount: int
    blocked_retry_count: int


class AuditEntry(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    event_type: str
    reason: str
    actor: str
    created_at: datetime | None
    previous_state: dict[str, Any] | None
    new_state: dict[str, Any] | None
    metadata: dict[str, Any] | None


class DashboardAuditResponse(BaseModel):
    entries: list[AuditEntry]
    limit: int
    offset: int
    total: int
