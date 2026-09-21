from dataclasses import dataclass

from app.models.enums import (
    FailureCategory,
    PaymentFailureSource,
    PaymentFailureStep,
)
from app.schemas.payments import SimulatedResult


@dataclass(frozen=True)
class FailureClassification:
    category: FailureCategory
    reason: str
    source: PaymentFailureSource
    step: PaymentFailureStep


SIMULATED_RESULT_CATEGORIES: dict[SimulatedResult, FailureCategory] = {
    SimulatedResult.TEMPORARY_FAILURE: FailureCategory.TEMPORARY_PAYMENT_FAILURE,
    SimulatedResult.PAYMENT_TIMEOUT: FailureCategory.TEMPORARY_PAYMENT_FAILURE,
    SimulatedResult.INSUFFICIENT_FUNDS: FailureCategory.INSUFFICIENT_FUNDS,
    SimulatedResult.CUSTOMER_CORRECTABLE: FailureCategory.CUSTOMER_CORRECTABLE,
    SimulatedResult.HIGH_RISK_FRAUD_BLOCK: FailureCategory.HIGH_RISK_FRAUD_BLOCK,
    SimulatedResult.CUSTOMER_CANCELLED: FailureCategory.CUSTOMER_CANCELLED_CHECKOUT,
}

CATEGORY_DEFAULTS: dict[FailureCategory, tuple[str, PaymentFailureSource, PaymentFailureStep]] = {
    FailureCategory.HIGH_RISK_FRAUD_BLOCK: (
        "The payment was blocked by fraud or risk controls.",
        PaymentFailureSource.PROVIDER,
        PaymentFailureStep.AUTHORIZATION,
    ),
    FailureCategory.TEMPORARY_PAYMENT_FAILURE: (
        "The payment failed because of a temporary provider, bank, or server issue.",
        PaymentFailureSource.PROVIDER,
        PaymentFailureStep.AUTHORIZATION,
    ),
    FailureCategory.CUSTOMER_CORRECTABLE: (
        "The customer must correct the payment details before retrying.",
        PaymentFailureSource.CUSTOMER,
        PaymentFailureStep.AUTHORIZATION,
    ),
    FailureCategory.INSUFFICIENT_FUNDS: (
        "The payment was declined because the available balance was insufficient.",
        PaymentFailureSource.BANK,
        PaymentFailureStep.AUTHORIZATION,
    ),
    FailureCategory.EXPIRED_CARD: (
        "The payment card has expired.",
        PaymentFailureSource.CUSTOMER,
        PaymentFailureStep.AUTHORIZATION,
    ),
    FailureCategory.CUSTOMER_CANCELLED_CHECKOUT: (
        "The customer cancelled checkout before payment completion.",
        PaymentFailureSource.CUSTOMER,
        PaymentFailureStep.CHECKOUT,
    ),
}

EXACT_CATEGORY_VALUES = {category.value: category for category in FailureCategory}


def _normalized_text(*values: str | None) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ") for value in values if value)


def _category_from_signals(
    simulated_result: SimulatedResult | None,
    failure_code: str | None,
    failure_reason: str | None,
    failure_source: PaymentFailureSource | None,
    failure_step: PaymentFailureStep | None,
    payment_method: str | None,
) -> FailureCategory:
    if simulated_result is not None:
        if simulated_result is SimulatedResult.SUCCESS:
            raise ValueError("Successful payments do not have a failure category")
        return SIMULATED_RESULT_CATEGORIES[simulated_result]

    normalized_code = failure_code.strip().upper() if failure_code else ""
    if normalized_code in EXACT_CATEGORY_VALUES:
        return EXACT_CATEGORY_VALUES[normalized_code]

    text = _normalized_text(failure_code, failure_reason, payment_method)
    if any(signal in text for signal in ("fraud", "risk block", "high risk", "blocked")):
        return FailureCategory.HIGH_RISK_FRAUD_BLOCK
    if any(signal in text for signal in ("cancelled", "canceled", "checkout cancelled")):
        return FailureCategory.CUSTOMER_CANCELLED_CHECKOUT
    if any(signal in text for signal in ("insufficient", "not enough", "low balance", "insufficient balance")):
        return FailureCategory.INSUFFICIENT_FUNDS
    if any(signal in text for signal in ("expired card", "card expired", "expiry")):
        return FailureCategory.EXPIRED_CARD
    if any(
        signal in text
        for signal in (
            "cvv",
            "upi pin",
            "wrong pin",
            "incorrect pin",
            "invalid details",
            "wrong details",
            "incorrect details",
        )
    ):
        return FailureCategory.CUSTOMER_CORRECTABLE
    if any(
        signal in text
        for signal in (
            "timeout",
            "timed out",
            "temporar",
            "provider unavailable",
            "bank unavailable",
            "server error",
            "network error",
            "gateway",
        )
    ):
        return FailureCategory.TEMPORARY_PAYMENT_FAILURE

    if failure_step is PaymentFailureStep.CHECKOUT and failure_source is PaymentFailureSource.CUSTOMER:
        return FailureCategory.CUSTOMER_CANCELLED_CHECKOUT
    if failure_source in (
        PaymentFailureSource.PROVIDER,
        PaymentFailureSource.BANK,
        PaymentFailureSource.SYSTEM,
    ):
        return FailureCategory.TEMPORARY_PAYMENT_FAILURE
    if failure_source is PaymentFailureSource.CUSTOMER:
        return FailureCategory.CUSTOMER_CORRECTABLE

    raise ValueError("Unsupported payment failure input")


def classify_payment_failure(
    *,
    simulated_result: SimulatedResult | None = None,
    failure_code: str | None = None,
    failure_reason: str | None = None,
    failure_source: PaymentFailureSource | None = None,
    failure_step: PaymentFailureStep | None = None,
    payment_method: str | None = None,
) -> FailureClassification:
    category = _category_from_signals(
        simulated_result,
        failure_code,
        failure_reason,
        failure_source,
        failure_step,
        payment_method,
    )
    default_reason, default_source, default_step = CATEGORY_DEFAULTS[category]
    return FailureClassification(
        category=category,
        reason=failure_reason or default_reason,
        source=failure_source or default_source,
        step=failure_step or default_step,
    )
