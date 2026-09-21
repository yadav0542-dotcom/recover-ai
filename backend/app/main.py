from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.orders import router as orders_router
from app.api.v1.payments import router as payments_router
from app.api.v1.razorpay import router as razorpay_router
from app.api.v1.recovery import router as recovery_router
from app.api.v1.dashboard import router as dashboard_router

from app.webhooks.razorpay import router as razorpay_webhook_router

from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title="RecoverAI API",
    version="0.1.0",
)

# CORS configuration for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
app.include_router(health_router)

# API v1 routes
app.include_router(
    health_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    orders_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    payments_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    razorpay_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    recovery_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    dashboard_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    razorpay_webhook_router,
    prefix=settings.api_v1_prefix,
)