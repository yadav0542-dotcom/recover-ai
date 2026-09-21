from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.models.enums import FailureCategory, ProviderHealth


MODEL_VERSION = "recovery-logistic-v1"
FEATURE_NAMES = (
    "payment_amount",
    "payment_method",
    "failure_category",
    "previous_attempts",
    "time_since_failure_minutes",
    "provider_health",
    "customer_successful_payments",
    "order_value",
)
CATEGORICAL_FEATURE_INDEXES = [1, 2, 5]
NUMERIC_FEATURE_INDEXES = [0, 3, 4, 6, 7]


@dataclass(frozen=True)
class RecoveryPrediction:
    recovery_probability: float
    model_version: str
    important_features: dict[str, Any]
    explanation: str


def _training_rows() -> tuple[list[list[Any]], list[int]]:
    rows = [
        [500, "upi", FailureCategory.CUSTOMER_CORRECTABLE.value, 0, 5, ProviderHealth.HEALTHY.value, 12, 500],
        [1200, "card", FailureCategory.INSUFFICIENT_FUNDS.value, 0, 10, ProviderHealth.HEALTHY.value, 10, 1200],
        [2500, "card", FailureCategory.EXPIRED_CARD.value, 1, 45, ProviderHealth.HEALTHY.value, 8, 2500],
        [800, "upi", FailureCategory.TEMPORARY_PAYMENT_FAILURE.value, 0, 15, ProviderHealth.HEALTHY.value, 6, 800],
        [1800, "card", FailureCategory.HIGH_RISK_FRAUD_BLOCK.value, 2, 30, ProviderHealth.HEALTHY.value, 1, 1800],
        [650, "upi", FailureCategory.CUSTOMER_CANCELLED_CHECKOUT.value, 0, 3, ProviderHealth.HEALTHY.value, 9, 650],
        [400, "card", FailureCategory.CUSTOMER_CORRECTABLE.value, 1, 8, ProviderHealth.HEALTHY.value, 5, 400],
        [900, "upi", FailureCategory.INSUFFICIENT_FUNDS.value, 2, 20, ProviderHealth.HEALTHY.value, 3, 900],
        [3000, "card", FailureCategory.HIGH_RISK_FRAUD_BLOCK.value, 3, 90, ProviderHealth.DOWN.value, 0, 3000],
        [700, "upi", FailureCategory.TEMPORARY_PAYMENT_FAILURE.value, 0, 8, ProviderHealth.UNKNOWN.value, 7, 700],
        [1100, "card", FailureCategory.EXPIRED_CARD.value, 0, 12, ProviderHealth.HEALTHY.value, 14, 1100],
        [550, "upi", FailureCategory.CUSTOMER_CANCELLED_CHECKOUT.value, 1, 6, ProviderHealth.HEALTHY.value, 4, 550],
    ]
    labels = [1, 1, 0, 1, 0, 1, 1, 0, 0, 1, 0, 1]
    return rows, labels


@lru_cache(maxsize=1)
def train_recovery_model() -> Pipeline:
    rows, labels = _training_rows()
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURE_INDEXES),
            ("numeric", StandardScaler(), NUMERIC_FEATURE_INDEXES),
        ]
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    model.fit(rows, labels)
    return model


def predict_recovery_probability(
    *,
    payment_amount: int,
    payment_method: str,
    failure_category: FailureCategory,
    previous_attempts: int,
    time_since_failure_minutes: int,
    provider_health: ProviderHealth,
    customer_successful_payments: int,
    order_value: int,
) -> RecoveryPrediction:
    features = {
        "payment_amount": payment_amount,
        "payment_method": payment_method,
        "failure_category": failure_category.value,
        "previous_attempts": previous_attempts,
        "time_since_failure_minutes": time_since_failure_minutes,
        "provider_health": provider_health.value,
        "customer_successful_payments": customer_successful_payments,
        "order_value": order_value,
    }
    row = [[features[name] for name in FEATURE_NAMES]]
    probability = float(train_recovery_model().predict_proba(row)[0][1])
    if probability >= 0.65:
        explanation = "Higher recovery probability is supported by the payment context and customer history."
    elif probability <= 0.35:
        explanation = "Lower recovery probability is driven by the failure context and payment history."
    else:
        explanation = "Recovery probability is moderate for the supplied payment context."
    return RecoveryPrediction(
        recovery_probability=round(min(max(probability, 0.0), 1.0), 6),
        model_version=MODEL_VERSION,
        important_features=features,
        explanation=explanation,
    )