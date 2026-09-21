from dataclasses import dataclass

from app.core.config import get_settings
from app.models.enums import (
    FailureCategory,
    OrderStatus,
    PaymentFailureSource,
    PaymentStatus,
    ProviderHealth,
    RecoveryAction,
)
from app.schemas.recommendation import (
    RecoveryRecommendationRequest,
    RecoveryRecommendationResponse,
)


@dataclass(frozen=True)
class RecoveryRecommendation:
    recommended_action: RecoveryAction
    recommended_delay_minutes: int
    confidence: float
    explanation: str
    safety_notes: list[str]


MOCK_SAFETY_NOTES = [
    "Recommendation only: no payment, retry, refund, or database action was executed.",
    "The deterministic development policy must be reviewed before any future execution layer is added.",
]


def _recommend_in_mock_mode(payload: RecoveryRecommendationRequest) -> RecoveryRecommendation:
    if payload.payment_status is PaymentStatus.SUCCESS and payload.order_status is OrderStatus.CANCELLED:
        return RecoveryRecommendation(
            RecoveryAction.REFUND_RECONCILE,
            0,
            0.99,
            "Payment succeeded after the order was cancelled, so the payment requires refund reconciliation.",
            MOCK_SAFETY_NOTES,
        )
    if payload.payment_status is PaymentStatus.SUCCESS and payload.order_status is OrderStatus.UNKNOWN:
        return RecoveryRecommendation(
            RecoveryAction.RECONCILE,
            0,
            0.98,
            "Payment succeeded while the order status is unknown, so the payment and order require reconciliation.",
            MOCK_SAFETY_NOTES,
        )
    if payload.failure_category is FailureCategory.HIGH_RISK_FRAUD_BLOCK:
        return RecoveryRecommendation(
            RecoveryAction.BLOCK_RETRY,
            0,
            0.99,
            "The fraud or risk block makes an automatic retry unsafe.",
            MOCK_SAFETY_NOTES,
        )
    if payload.failure_category is FailureCategory.EXPIRED_CARD:
        return RecoveryRecommendation(
            RecoveryAction.ALTERNATE_PAYMENT,
            0,
            0.96,
            "The card is expired, so the customer should use another payment method.",
            MOCK_SAFETY_NOTES,
        )
    if payload.failure_category is FailureCategory.CUSTOMER_CORRECTABLE:
        return RecoveryRecommendation(
            RecoveryAction.RETRY_NOW,
            0,
            0.91,
            "The payment details are correctable, so a retry is appropriate after correction.",
            MOCK_SAFETY_NOTES,
        )
    if payload.failure_category is FailureCategory.INSUFFICIENT_FUNDS:
        action = (
            RecoveryAction.RESUME_PAYMENT
            if payload.recovery_probability >= 0.55 and payload.previous_attempt_count == 0
            else RecoveryAction.WAIT_AND_NOTIFY
        )
        return RecoveryRecommendation(
            action,
            30 if action is RecoveryAction.WAIT_AND_NOTIFY else 0,
            0.82,
            "Insufficient funds call for a deferred notification or a resumed payment flow based on recovery likelihood.",
            MOCK_SAFETY_NOTES,
        )
    if payload.provider_health in (ProviderHealth.DOWN, ProviderHealth.UNKNOWN):
        return RecoveryRecommendation(
            RecoveryAction.WAIT_AND_NOTIFY,
            30,
            0.94,
            "Provider health is unavailable, so the customer should be notified after a short wait.",
            MOCK_SAFETY_NOTES,
        )
    if payload.failure_source in (PaymentFailureSource.PROVIDER, PaymentFailureSource.BANK):
        return RecoveryRecommendation(
            RecoveryAction.WAIT_AND_NOTIFY,
            30,
            0.88,
            "The failure source indicates a provider or bank issue, so an immediate retry is avoided.",
            MOCK_SAFETY_NOTES,
        )
    if payload.failure_category is FailureCategory.CUSTOMER_CANCELLED_CHECKOUT:
        return RecoveryRecommendation(
            RecoveryAction.RESUME_PAYMENT,
            0,
            0.86,
            "The customer cancelled checkout, so the payment flow can be resumed explicitly.",
            MOCK_SAFETY_NOTES,
        )
    return RecoveryRecommendation(
        RecoveryAction.WAIT_AND_NOTIFY,
        30,
        0.7,
        "The failure does not provide enough evidence for an immediate action, so the customer should be notified after a wait.",
        MOCK_SAFETY_NOTES,
    )


class RecoveryRecommendationAgent:
    """Recommendation-only agent with deterministic mock behavior by default."""

    def __init__(self, mode: str | None = None) -> None:
        settings = get_settings()
        self.mode = mode or settings.recovery_agent_mode
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.has_api_key = bool(settings.llm_api_key)

    def recommend(self, payload: RecoveryRecommendationRequest) -> RecoveryRecommendation:
        # An external provider adapter can be added later without changing this safety boundary.
        return _recommend_in_mock_mode(payload)


def recommend_recovery(payload: RecoveryRecommendationRequest) -> RecoveryRecommendation:
    return RecoveryRecommendationAgent().recommend(payload)
