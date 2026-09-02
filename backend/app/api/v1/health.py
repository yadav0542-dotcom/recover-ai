from fastapi import APIRouter

from app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return service liveness without requiring a database connection."""
    return HealthResponse(status="ok", service="recover-ai-backend")
