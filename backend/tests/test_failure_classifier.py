import pytest

from app.models.enums import FailureCategory, PaymentFailureSource, PaymentFailureStep
from app.schemas.payments import SimulatedResult
from app.services.failure_classifier import classify_payment_failure


@pytest.mark.parametrize(
    ("simulated_result", "expected_category"),
    [
        (SimulatedResult.TEMPORARY_FAILURE, FailureCategory.TEMPORARY_PAYMENT_FAILURE),
        (SimulatedResult.PAYMENT_TIMEOUT, FailureCategory.TEMPORARY_PAYMENT_FAILURE),
        (SimulatedResult.INSUFFICIENT_FUNDS, FailureCategory.INSUFFICIENT_FUNDS),
        (SimulatedResult.CUSTOMER_CORRECTABLE, FailureCategory.CUSTOMER_CORRECTABLE),
        (SimulatedResult.HIGH_RISK_FRAUD_BLOCK, FailureCategory.HIGH_RISK_FRAUD_BLOCK),
        (SimulatedResult.CUSTOMER_CANCELLED, FailureCategory.CUSTOMER_CANCELLED_CHECKOUT),
    ],
)
def test_classifies_simulated_results(
    simulated_result: SimulatedResult,
    expected_category: FailureCategory,
) -> None:
    classification = classify_payment_failure(simulated_result=simulated_result)

    assert classification.category is expected_category
    assert classification.reason
    assert classification.source
    assert classification.step


def test_classifies_expired_card_from_failure_details() -> None:
    classification = classify_payment_failure(
        failure_code="CARD_EXPIRED",
        failure_reason="The customer's card has expired.",
        payment_method="card",
    )

    assert classification.category is FailureCategory.EXPIRED_CARD
    assert classification.source is PaymentFailureSource.CUSTOMER
    assert classification.step is PaymentFailureStep.AUTHORIZATION


def test_classifies_customer_input_error_from_failure_details() -> None:
    classification = classify_payment_failure(
        failure_reason="Wrong CVV entered for the card.",
        failure_source=PaymentFailureSource.CUSTOMER,
    )

    assert classification.category is FailureCategory.CUSTOMER_CORRECTABLE


def test_classifies_temporary_provider_issue_from_source() -> None:
    classification = classify_payment_failure(
        failure_code="PROVIDER_UNAVAILABLE",
        failure_source=PaymentFailureSource.PROVIDER,
        failure_step=PaymentFailureStep.CAPTURE,
    )

    assert classification.category is FailureCategory.TEMPORARY_PAYMENT_FAILURE
    assert classification.step is PaymentFailureStep.CAPTURE


def test_rejects_unknown_failure_input() -> None:
    with pytest.raises(ValueError, match="Unsupported payment failure input"):
        classify_payment_failure(failure_code="UNKNOWN_FAILURE_CODE")


def test_rejects_success_as_failure_input() -> None:
    with pytest.raises(ValueError, match="Successful payments"):
        classify_payment_failure(simulated_result=SimulatedResult.SUCCESS)
