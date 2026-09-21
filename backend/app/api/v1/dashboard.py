from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dashboard import (
    DashboardAuditResponse,
    DashboardFailuresResponse,
    DashboardSummary,
    RecoveryMetricsResponse,
)
from app.services.dashboard import (
    get_audit_entries,
    get_dashboard_summary,
    get_failure_distribution,
    get_recovery_metrics,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return get_dashboard_summary(db)


@router.get("/failures", response_model=DashboardFailuresResponse)
def dashboard_failures(db: Session = Depends(get_db)) -> DashboardFailuresResponse:
    return get_failure_distribution(db)


@router.get("/recoveries", response_model=RecoveryMetricsResponse)
def dashboard_recoveries(db: Session = Depends(get_db)) -> RecoveryMetricsResponse:
    return get_recovery_metrics(db)


@router.get("/audit", response_model=DashboardAuditResponse)
def dashboard_audit(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DashboardAuditResponse:
    return get_audit_entries(db, limit, offset)