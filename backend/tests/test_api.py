from collections.abc import Generator
import hashlib
import hmac
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.recovery_agent import RecoveryRecommendationAgent
from app.core.database import Base, get_db
from app.core.config import get_settings
from app.models.enums import OrderStatus
from app.models.order import Order
from app.main import app as api_app
import app.models  # noqa: F401


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    api_app.dependency_overrides[get_db] = override_get_db
    with TestClient(api_app) as test_client:
        yield test_client
    api_app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def order_payload() -> dict:
    return {
        "customer_id": "customer-123",
        "amount": 1250,
        "currency": "INR",
        "cart_data": {"items": [{"sku": "sku-1", "quantity": 1}]},
    }


def payment_payload(order_id: str | None = None) -> dict:
    return {
        "order_id": order_id,
        "customer_id": "customer-123",
        "amount": 1250,
        "currency": "INR",
        "payment_method": "card",
    }


def create_simulation_order(client: TestClient) -> str:
    response = client.post("/api/v1/orders", json=order_payload())
    assert response.status_code == 201
    return response.json()["id"]


def simulate_payload(order_id: str, simulated_result: str) -> dict:
    return {
        "order_id": order_id,
        "payment_method": "card",
        "amount": 1250,
        "simulated_result": simulated_result,
    }


def test_health_is_available_at_root_and_versioned_paths(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_order_create_and_get(client: TestClient) -> None:
    create_response = client.post("/api/v1/orders", json=order_payload())

    assert create_response.status_code == 201
    order = create_response.json()
    assert order["customer_id"] == "customer-123"
    assert order["status"] == "ORDER_PENDING"

    get_response = client.get(f"/api/v1/orders/{order['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == order["id"]


def test_order_validation_and_not_found(client: TestClient) -> None:
    invalid_response = client.post(
        "/api/v1/orders",
        json={**order_payload(), "amount": 0},
    )
    missing_response = client.get(f"/api/v1/orders/{uuid4()}")

    assert invalid_response.status_code == 422
    assert missing_response.status_code == 404


def test_payment_create_and_get_for_existing_order(client: TestClient) -> None:
    order_response = client.post("/api/v1/orders", json=order_payload())
    order_id = order_response.json()["id"]

    create_response = client.post(
        "/api/v1/payments",
        json=payment_payload(order_id),
    )

    assert create_response.status_code == 201
    payment = create_response.json()
    assert payment["order_id"] == order_id
    assert payment["customer_id"] == "customer-123"

    get_response = client.get(f"/api/v1/payments/{payment['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == payment["id"]


def test_payment_rejects_missing_order_and_unknown_payment(client: TestClient) -> None:
    missing_order_response = client.post(
        "/api/v1/payments",
        json=payment_payload(str(uuid4())),
    )
    unknown_payment_response = client.get(f"/api/v1/payments/{uuid4()}")

    assert missing_order_response.status_code == 404
    assert unknown_payment_response.status_code == 404


def test_payment_simulation_success_marks_order_paid(client: TestClient) -> None:
    order_id = create_simulation_order(client)

    response = client.post(
        "/api/v1/payments/simulate",
        json=simulate_payload(order_id, "SUCCESS"),
    )

    assert response.status_code == 201
    assert response.json()["payment_status"] == "PAYMENT_SUCCESS"
    assert response.json()["failure_category"] is None
    assert client.get(f"/api/v1/orders/{order_id}").json()["status"] == "ORDER_PAID"


@pytest.mark.parametrize(
    ("simulated_result", "failure_category"),
    [
        ("TEMPORARY_FAILURE", "TEMPORARY_PAYMENT_FAILURE"),
        ("INSUFFICIENT_FUNDS", "INSUFFICIENT_FUNDS"),
        ("HIGH_RISK_FRAUD_BLOCK", "HIGH_RISK_FRAUD_BLOCK"),
        ("CUSTOMER_CANCELLED", "CUSTOMER_CANCELLED_CHECKOUT"),
    ],
)
def test_payment_simulation_failures_keep_order_pending(
    client: TestClient,
    simulated_result: str,
    failure_category: str,
) -> None:
    order_id = create_simulation_order(client)

    response = client.post(
        "/api/v1/payments/simulate",
        json=simulate_payload(order_id, simulated_result),
    )

    body = response.json()
    assert response.status_code == 201
    assert body["payment_status"] == "PAYMENT_FAILED"
    assert body["failure_category"] == failure_category
    assert body["failure_reason"]
    assert body["failure_source"]
    assert body["failure_step"]
    assert client.get(f"/api/v1/orders/{order_id}").json()["status"] == "ORDER_PENDING"


def test_payment_simulation_rejects_invalid_order_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/payments/simulate",
        json=simulate_payload(str(uuid4()), "SUCCESS"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found."


def test_failure_classification_can_load_payment_by_id(client: TestClient) -> None:
    order_id = create_simulation_order(client)
    payment_response = client.post(
        "/api/v1/payments/simulate",
        json=simulate_payload(order_id, "INSUFFICIENT_FUNDS"),
    )
    payment_id = payment_response.json()["payment_id"]

    response = client.post(
        "/api/v1/recovery/classify",
        json={"payment_id": payment_id},
    )

    assert response.status_code == 200
    assert response.json()["payment_id"] == payment_id
    assert response.json()["failure_category"] == "INSUFFICIENT_FUNDS"


def test_failure_classification_accepts_failure_details(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/classify",
        json={
            "failure_code": "CARD_EXPIRED",
            "failure_reason": "The card has expired.",
            "payment_method": "card",
        },
    )

    assert response.status_code == 200
    assert response.json()["payment_id"] is None
    assert response.json()["failure_category"] == "EXPIRED_CARD"
    assert response.json()["reason"] == "The card has expired."


def test_failure_classification_rejects_unknown_details(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/classify",
        json={"failure_code": "UNSUPPORTED_FAILURE"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported payment failure input"


def prediction_payload(failure_category: str) -> dict:
    return {
        "payment_amount": 1000,
        "payment_method": "card",
        "failure_category": failure_category,
        "previous_attempts": 0,
        "time_since_failure_minutes": 10,
        "provider_health": "HEALTHY",
        "customer_successful_payments": 8,
        "order_value": 1000,
    }


def test_recovery_prediction_returns_explainable_probability(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/predict",
        json=prediction_payload("CUSTOMER_CORRECTABLE"),
    )

    body = response.json()
    assert response.status_code == 200
    assert 0 <= body["recovery_probability"] <= 1
    assert body["model_version"] == "recovery-logistic-v1"
    assert body["important_features"]["failure_category"] == "CUSTOMER_CORRECTABLE"
    assert body["explanation"]


def test_recovery_prediction_is_deterministic(client: TestClient) -> None:
    payload = prediction_payload("TEMPORARY_PAYMENT_FAILURE")

    first = client.post("/api/v1/recovery/predict", json=payload)
    second = client.post("/api/v1/recovery/predict", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["recovery_probability"] == second.json()["recovery_probability"]


def test_temporary_failure_has_higher_probability_than_high_risk_block(client: TestClient) -> None:
    temporary = client.post(
        "/api/v1/recovery/predict",
        json=prediction_payload("TEMPORARY_PAYMENT_FAILURE"),
    )
    high_risk = client.post(
        "/api/v1/recovery/predict",
        json=prediction_payload("HIGH_RISK_FRAUD_BLOCK"),
    )

    assert temporary.status_code == 200
    assert high_risk.status_code == 200
    assert temporary.json()["recovery_probability"] > high_risk.json()["recovery_probability"]


def test_recovery_prediction_rejects_invalid_input(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/predict",
        json={**prediction_payload("UNKNOWN_FAILURE"), "previous_attempts": -1},
    )

    assert response.status_code == 422


def recommendation_payload(**overrides: str | int | float | None) -> dict:
    payload: dict[str, str | int | float | None] = {
        "payment_id": str(uuid4()),
        "payment_status": "PAYMENT_FAILED",
        "order_status": "ORDER_PENDING",
        "failure_category": "TEMPORARY_PAYMENT_FAILURE",
        "failure_reason": "The provider is temporarily unavailable.",
        "failure_source": "PROVIDER",
        "payment_method": "card",
        "payment_amount": 1200,
        "recovery_probability": 0.65,
        "provider_health": "PROVIDER_DOWN",
        "previous_attempt_count": 0,
    }
    payload.update(overrides)
    return payload


def test_recommendation_waits_for_temporary_provider_failure(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/recommend",
        json=recommendation_payload(),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["recommended_action"] == "WAIT_AND_NOTIFY"
    assert body["recommended_delay_minutes"] == 30
    assert body["safety_notes"]


def test_recommendation_blocks_high_risk_retry(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/recommend",
        json=recommendation_payload(
            failure_category="HIGH_RISK_FRAUD_BLOCK",
            provider_health="HEALTHY",
        ),
    )

    assert response.status_code == 200
    assert response.json()["recommended_action"] == "BLOCK_RETRY"


def test_recommendation_handles_insufficient_funds(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/recommend",
        json=recommendation_payload(
            failure_category="INSUFFICIENT_FUNDS",
            provider_health="HEALTHY",
        ),
    )

    assert response.status_code == 200
    assert response.json()["recommended_action"] == "RESUME_PAYMENT"


def test_recommendation_uses_alternate_payment_for_expired_card(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/recommend",
        json=recommendation_payload(
            failure_category="EXPIRED_CARD",
            provider_health="HEALTHY",
        ),
    )

    assert response.status_code == 200
    assert response.json()["recommended_action"] == "ALTERNATE_PAYMENT"


def test_recommendation_retries_customer_correctable_failure(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/recommend",
        json=recommendation_payload(
            failure_category="CUSTOMER_CORRECTABLE",
            provider_health="HEALTHY",
            failure_source="CUSTOMER",
        ),
    )

    assert response.status_code == 200
    assert response.json()["recommended_action"] == "RETRY_NOW"


def test_recommendation_reconciles_successful_cancelled_order(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/recommend",
        json=recommendation_payload(
            payment_status="PAYMENT_SUCCESS",
            order_status="ORDER_CANCELLED",
            failure_category=None,
            failure_source=None,
            failure_reason="",
            provider_health="HEALTHY",
        ),
    )

    assert response.status_code == 200
    assert response.json()["recommended_action"] == "REFUND_RECONCILE"


def test_recommendation_mock_mode_is_safe_without_llm_key(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/recommend",
        json=recommendation_payload(),
    )

    assert response.status_code == 200
    assert any("no payment" in note.lower() for note in response.json()["safety_notes"])


def test_recommendation_agent_uses_mock_mode_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    get_settings.cache_clear()

    agent = RecoveryRecommendationAgent()

    assert agent.has_api_key is False
    assert agent.mode == "mock"
    get_settings.cache_clear()


def evaluation_payload(**overrides: str | int | float | None) -> dict:
    payload: dict[str, str | int | float | None] = {
        "payment_id": str(uuid4()),
        "payment_status": "PAYMENT_FAILED",
        "order_status": "ORDER_PENDING",
        "failure_category": "CUSTOMER_CORRECTABLE",
        "failure_reason": "Wrong CVV entered.",
        "failure_source": "CUSTOMER",
        "failure_step": "AUTHORIZATION",
        "payment_method": "card",
        "payment_amount": 1000,
        "recovery_probability": 0.8,
        "provider_health": "HEALTHY",
        "previous_attempt_count": 0,
        "customer_successful_payments": 5,
        "order_value": 1000,
        "ai_recommended_action": "RETRY_NOW",
        "ai_confidence": 0.9,
    }
    payload.update(overrides)
    return payload


def test_policy_allows_safe_customer_correctable_retry(client: TestClient) -> None:
    response = client.post("/api/v1/recovery/evaluate", json=evaluation_payload())

    body = response.json()
    assert response.status_code == 200
    assert body["final_policy_action"] == "RETRY_NOW"
    assert body["retry_allowed"] is True
    assert body["safety_override"] is False
    assert body["policy_decision"] == "ALLOW"


def test_policy_overrides_fraud_retry(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            failure_category="HIGH_RISK_FRAUD_BLOCK",
            failure_reason="Fraud risk block.",
            failure_source="PROVIDER",
            ai_recommended_action="RETRY_NOW",
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ai_recommended_action"] == "RETRY_NOW"
    assert body["final_policy_action"] == "BLOCK_RETRY"
    assert body["retry_allowed"] is False
    assert body["safety_override"] is True
    assert body["policy_decision"] == "OVERRIDE"


def test_policy_blocks_retry_during_provider_outage(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            failure_category="TEMPORARY_PAYMENT_FAILURE",
            failure_reason="Provider unavailable.",
            failure_source="PROVIDER",
            provider_health="PROVIDER_DOWN",
            ai_recommended_action="RETRY_NOW",
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["final_policy_action"] == "WAIT_AND_NOTIFY"
    assert body["retry_allowed"] is False
    assert body["safety_override"] is True


def test_policy_reconciles_successful_cancelled_order(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            payment_status="PAYMENT_SUCCESS",
            order_status="ORDER_CANCELLED",
            failure_category=None,
            failure_reason="",
            failure_source=None,
            failure_step=None,
            ai_recommended_action="RETRY_NOW",
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["final_policy_action"] == "REFUND_RECONCILE"
    assert body["retry_allowed"] is False
    assert body["safety_override"] is True


def test_policy_reconciles_successful_unknown_order(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            payment_status="PAYMENT_SUCCESS",
            order_status="ORDER_STATUS_UNKNOWN",
            failure_category=None,
            failure_reason="",
            failure_source=None,
            failure_step=None,
            ai_recommended_action="RETRY_NOW",
        ),
    )

    assert response.status_code == 200
    assert response.json()["final_policy_action"] == "RECONCILE"
    assert response.json()["retry_allowed"] is False


def test_policy_requires_alternate_payment_for_expired_card(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            failure_category="EXPIRED_CARD",
            failure_reason="Card expired.",
            ai_recommended_action="RETRY_NOW",
        ),
    )

    assert response.status_code == 200
    assert response.json()["final_policy_action"] == "ALTERNATE_PAYMENT"
    assert response.json()["retry_allowed"] is False


def test_policy_handles_insufficient_funds_without_immediate_retry(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            failure_category="INSUFFICIENT_FUNDS",
            failure_reason="Insufficient balance.",
            failure_source="BANK",
            ai_recommended_action="RETRY_NOW",
        ),
    )

    assert response.status_code == 200
    assert response.json()["final_policy_action"] == "WAIT_AND_NOTIFY"
    assert response.json()["retry_allowed"] is False


def test_policy_resumes_customer_cancelled_checkout(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            failure_category="CUSTOMER_CANCELLED_CHECKOUT",
            failure_reason="Customer cancelled checkout.",
            failure_source="CUSTOMER",
            failure_step="CHECKOUT",
            ai_recommended_action="BLOCK_RETRY",
        ),
    )

    assert response.status_code == 200
    assert response.json()["final_policy_action"] == "RESUME_PAYMENT"
    assert response.json()["retry_allowed"] is True


def test_policy_tracks_refund_pending(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            payment_status="REFUND_PENDING",
            failure_category=None,
            failure_reason="",
            failure_source=None,
            failure_step=None,
            ai_recommended_action="RETRY_NOW",
        ),
    )

    assert response.status_code == 200
    assert response.json()["final_policy_action"] == "TRACK_REFUND"
    assert response.json()["retry_allowed"] is False


def test_policy_composes_classifier_model_and_agent_when_inputs_are_missing(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/evaluate",
        json=evaluation_payload(
            failure_category=None,
            failure_code="PROVIDER_UNAVAILABLE",
            failure_reason="Provider temporarily unavailable.",
            failure_source="PROVIDER",
            failure_step="AUTHORIZATION",
            recovery_probability=None,
            ai_recommended_action=None,
            ai_confidence=None,
            provider_health="PROVIDER_DOWN",
        ),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["failure_category"] == "TEMPORARY_PAYMENT_FAILURE"
    assert body["ai_recommended_action"] == "WAIT_AND_NOTIFY"
    assert body["final_policy_action"] == "WAIT_AND_NOTIFY"
    assert body["confidence"] is not None


def create_execution_payment(client: TestClient, simulated_result: str = "CUSTOMER_CORRECTABLE") -> tuple[str, str]:
    order_id = create_simulation_order(client)
    response = client.post(
        "/api/v1/payments/simulate",
        json=simulate_payload(order_id, simulated_result),
    )
    assert response.status_code == 201
    return response.json()["payment_id"], order_id


def execution_payload(payment_id: str, order_id: str, **overrides: str | bool) -> dict:
    payload: dict[str, str | bool] = {
        "payment_id": payment_id,
        "order_id": order_id,
        "final_action": "RETRY_NOW",
        "policy_decision": "ALLOW",
        "retry_allowed": True,
    }
    payload.update(overrides)
    return payload


def test_execution_records_approved_retry(client: TestClient) -> None:
    payment_id, order_id = create_execution_payment(client)

    response = client.post(
        "/api/v1/recovery/execute",
        json=execution_payload(payment_id, order_id),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["execution_status"] == "SIMULATED"
    assert body["executed"] is True
    assert body["audit_id"]
    assert "no payment provider" in body["message"]


def test_execution_blocks_retry_when_policy_disallows_it(client: TestClient) -> None:
    payment_id, order_id = create_execution_payment(client)

    response = client.post(
        "/api/v1/recovery/execute",
        json=execution_payload(payment_id, order_id, retry_allowed=False),
    )

    assert response.status_code == 200
    assert response.json()["execution_status"] == "BLOCKED"
    assert response.json()["executed"] is False


def test_execution_prevents_retry_after_successful_payment(client: TestClient) -> None:
    payment_id, order_id = create_execution_payment(client, "SUCCESS")

    response = client.post(
        "/api/v1/recovery/execute",
        json=execution_payload(payment_id, order_id),
    )

    assert response.status_code == 200
    assert response.json()["execution_status"] == "BLOCKED"
    assert response.json()["executed"] is False
    assert "already succeeded" in response.json()["safety_reason"]


@pytest.mark.parametrize(
    ("final_action", "expected_message"),
    [
        ("WAIT_AND_NOTIFY", "waiting recovery"),
        ("ALTERNATE_PAYMENT", "Alternate payment"),
        ("RECONCILE", "reconciliation"),
        ("REFUND_RECONCILE", "refund reconciliation"),
        ("TRACK_REFUND", "refund tracking"),
        ("ESCALATE", "escalation"),
        ("BLOCK_RETRY", "Blocked action"),
    ],
)
def test_execution_records_safe_simulated_actions(
    client: TestClient,
    final_action: str,
    expected_message: str,
) -> None:
    payment_id, order_id = create_execution_payment(client)

    response = client.post(
        "/api/v1/recovery/execute",
        json=execution_payload(payment_id, order_id, final_action=final_action, retry_allowed=False),
    )

    assert response.status_code == 200
    assert response.json()["execution_status"] == "SIMULATED"
    assert response.json()["executed"] is True
    assert expected_message.lower() in response.json()["message"].lower()


def test_execution_prevents_duplicate_simulated_action(client: TestClient) -> None:
    payment_id, order_id = create_execution_payment(client)
    payload = execution_payload(payment_id, order_id)

    first = client.post("/api/v1/recovery/execute", json=payload)
    second = client.post("/api/v1/recovery/execute", json=payload)

    assert first.status_code == 200
    assert first.json()["executed"] is True
    assert second.status_code == 200
    assert second.json()["execution_status"] == "DUPLICATE"
    assert second.json()["executed"] is False


def test_execution_rejects_unknown_payment(client: TestClient) -> None:
    response = client.post(
        "/api/v1/recovery/execute",
        json=execution_payload(str(uuid4()), str(uuid4())),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found."


def test_execution_blocks_retry_for_successful_cancelled_order(client: TestClient) -> None:
    payment_id, order_id = create_execution_payment(client, "SUCCESS")
    dependency = api_app.dependency_overrides[get_db]()
    db = next(dependency)
    order = db.get(Order, UUID(order_id))
    assert order is not None
    order.status = OrderStatus.CANCELLED
    db.commit()
    dependency.close()

    response = client.post(
        "/api/v1/recovery/execute",
        json=execution_payload(payment_id, order_id),
    )

    assert response.status_code == 200
    assert response.json()["execution_status"] == "BLOCKED"
    assert "cancelled" in response.json()["safety_reason"]


def set_order_status(order_id: str, order_status: OrderStatus) -> None:
    dependency = api_app.dependency_overrides[get_db]()
    db = next(dependency)
    order = db.get(Order, UUID(order_id))
    assert order is not None
    order.status = order_status
    db.commit()
    db.close()


def process_payment(client: TestClient, simulated_result: str) -> tuple[str, str, dict]:
    payment_id, order_id = create_execution_payment(client, simulated_result)
    response = client.post("/api/v1/recovery/process", json={"payment_id": payment_id})
    assert response.status_code == 200
    return payment_id, order_id, response.json()


def test_recovery_workflow_processes_temporary_failure(client: TestClient) -> None:
    _, _, body = process_payment(client, "TEMPORARY_FAILURE")

    assert body["failure_category"] == "TEMPORARY_PAYMENT_FAILURE"
    assert 0 <= body["recovery_probability"] <= 1
    assert body["ai_recommended_action"] == "WAIT_AND_NOTIFY"
    assert body["final_policy_action"] == "WAIT_AND_NOTIFY"
    assert body["execution_status"] == "SIMULATED"
    assert body["audit_id"]
    assert body["policy_audit_id"]


def test_recovery_workflow_processes_insufficient_funds(client: TestClient) -> None:
    _, _, body = process_payment(client, "INSUFFICIENT_FUNDS")

    assert body["failure_category"] == "INSUFFICIENT_FUNDS"
    assert body["final_policy_action"] == "WAIT_AND_NOTIFY"
    assert body["retry_allowed"] is False


def test_recovery_workflow_blocks_high_risk_fraud(client: TestClient) -> None:
    _, _, body = process_payment(client, "HIGH_RISK_FRAUD_BLOCK")

    assert body["failure_category"] == "HIGH_RISK_FRAUD_BLOCK"
    assert body["ai_recommended_action"] == "BLOCK_RETRY"
    assert body["final_policy_action"] == "BLOCK_RETRY"
    assert body["execution_status"] == "SIMULATED"
    assert body["retry_allowed"] is False


def test_recovery_workflow_processes_customer_correctable_failure(client: TestClient) -> None:
    _, _, body = process_payment(client, "CUSTOMER_CORRECTABLE")

    assert body["failure_category"] == "CUSTOMER_CORRECTABLE"
    assert body["ai_recommended_action"] == "RETRY_NOW"
    assert body["final_policy_action"] == "RETRY_NOW"
    assert body["retry_allowed"] is True
    assert body["execution_status"] == "SIMULATED"


def test_recovery_workflow_successful_cancelled_order_refund_reconciles(client: TestClient) -> None:
    payment_id, order_id = create_execution_payment(client, "SUCCESS")
    set_order_status(order_id, OrderStatus.CANCELLED)

    response = client.post("/api/v1/recovery/process", json={"payment_id": payment_id})

    body = response.json()
    assert response.status_code == 200
    assert body["final_policy_action"] == "REFUND_RECONCILE"
    assert body["execution_status"] == "SIMULATED"
    assert body["retry_allowed"] is False


def test_recovery_workflow_successful_unknown_order_reconciles(client: TestClient) -> None:
    payment_id, order_id = create_execution_payment(client, "SUCCESS")
    set_order_status(order_id, OrderStatus.UNKNOWN)

    response = client.post("/api/v1/recovery/process", json={"payment_id": payment_id})

    body = response.json()
    assert response.status_code == 200
    assert body["final_policy_action"] == "RECONCILE"
    assert body["execution_status"] == "SIMULATED"
    assert body["retry_allowed"] is False


def test_recovery_workflow_skips_successful_payment_in_normal_order(client: TestClient) -> None:
    _, _, body = process_payment(client, "SUCCESS")

    assert body["execution_status"] == "SKIPPED"
    assert body["final_policy_action"] is None
    assert body["retry_allowed"] is False


def test_recovery_workflow_prevents_duplicate_execution(client: TestClient) -> None:
    payment_id, _ = create_execution_payment(client, "CUSTOMER_CORRECTABLE")

    first = client.post("/api/v1/recovery/process", json={"payment_id": payment_id})
    second = client.post("/api/v1/recovery/process", json={"payment_id": payment_id})

    assert first.status_code == 200
    assert first.json()["execution_status"] == "SIMULATED"
    assert second.status_code == 200
    assert second.json()["execution_status"] == "DUPLICATE"
    assert second.json()["retry_allowed"] is True


def test_recovery_workflow_rejects_unknown_payment(client: TestClient) -> None:
    response = client.post("/api/v1/recovery/process", json={"payment_id": str(uuid4())})

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found."


def razorpay_signature(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(
        secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def webhook_signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_razorpay_order_creation_uses_mock_without_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/v1/razorpay/orders",
        json={"amount": 1500, "currency": "INR", "customer_id": "customer-razorpay"},
    )

    body = response.json()
    assert response.status_code == 201
    assert body["mocked"] is True
    assert body["mode"] == "test"
    assert body["razorpay_order_id"].startswith("order_mock_")
    assert body["local_order_id"]


def test_razorpay_payment_signature_verification_updates_payment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "test_key_secret"
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", secret)
    get_settings.cache_clear()
    order_response = client.post("/api/v1/razorpay/orders", json={"amount": 1500, "currency": "INR"})
    order_body = order_response.json()
    payment_id = f"pay_test_{uuid4().hex}"

    response = client.post(
        "/api/v1/razorpay/verify",
        json={
            "razorpay_order_id": order_body["razorpay_order_id"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": razorpay_signature(order_body["razorpay_order_id"], payment_id, secret),
        },
    )

    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["status"] == "PAYMENT_SUCCESS"
    get_settings.cache_clear()


def test_razorpay_invalid_payment_signature_is_rejected(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "test_key_secret")
    get_settings.cache_clear()
    order_body = client.post("/api/v1/razorpay/orders", json={"amount": 1500}).json()

    response = client.post(
        "/api/v1/razorpay/verify",
        json={
            "razorpay_order_id": order_body["razorpay_order_id"],
            "razorpay_payment_id": "pay_invalid",
            "razorpay_signature": "invalid-signature",
        },
    )

    assert response.status_code == 400
    assert "Invalid Razorpay payment signature" in response.json()["detail"]
    get_settings.cache_clear()


def test_razorpay_webhook_updates_payment_and_ignores_duplicate(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "webhook_secret"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)
    get_settings.cache_clear()
    order_body = client.post("/api/v1/razorpay/orders", json={"amount": 1500}).json()
    payment_body = client.post(
        "/api/v1/payments",
        json={
            "order_id": order_body["local_order_id"],
            "customer_id": "razorpay_test_customer",
            "amount": 1500,
            "currency": "INR",
            "razorpay_order_id": order_body["razorpay_order_id"],
            "razorpay_payment_id": "pay_webhook_test",
        },
    ).json()
    event = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_webhook_test", "order_id": order_body["razorpay_order_id"]}}},
    }
    body = json.dumps(event).encode()
    headers = {"X-Razorpay-Signature": webhook_signature(body, secret), "X-Razorpay-Event-Id": "evt_test_1"}

    first = client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)
    second = client.post("/api/v1/webhooks/razorpay", content=body, headers=headers)

    assert payment_body["status"] == "PENDING"
    assert first.status_code == 200
    assert first.json()["status"] == "PROCESSED"
    assert second.status_code == 200
    assert second.json()["status"] == "DUPLICATE"
    payment = client.get(f"/api/v1/payments/{payment_body['id']}")
    assert payment.json()["status"] == "PAYMENT_SUCCESS"
    get_settings.cache_clear()


def test_dashboard_endpoints_handle_empty_database(client: TestClient) -> None:
    summary = client.get("/api/v1/dashboard/summary")
    failures = client.get("/api/v1/dashboard/failures")
    recoveries = client.get("/api/v1/dashboard/recoveries")
    audit = client.get("/api/v1/dashboard/audit")

    assert summary.status_code == 200
    assert summary.json() == {
        "revenue_at_risk": 0,
        "revenue_recovered": 0,
        "recovery_rate": 0.0,
        "unsafe_retries_blocked": 0,
        "pending_recoveries": 0,
        "total_payments": 0,
        "failed_payments": 0,
        "successful_payments": 0,
    }
    assert failures.json() == {"failures": []}
    assert recoveries.json()["action_counts"] == {}
    assert recoveries.json()["execution_status_counts"] == {}
    assert audit.json()["entries"] == []
    assert audit.json()["total"] == 0


def test_dashboard_endpoints_return_real_payment_recovery_and_audit_data(client: TestClient) -> None:
    create_execution_payment(client, "TEMPORARY_FAILURE")
    process_payment(client, "CUSTOMER_CORRECTABLE")
    create_execution_payment(client, "SUCCESS")

    summary = client.get("/api/v1/dashboard/summary").json()
    failures = client.get("/api/v1/dashboard/failures").json()
    recoveries = client.get("/api/v1/dashboard/recoveries").json()
    audit = client.get("/api/v1/dashboard/audit?limit=3").json()

    assert summary["total_payments"] == 3
    assert summary["failed_payments"] == 2
    assert summary["successful_payments"] == 1
    assert summary["revenue_at_risk"] == 2500
    assert summary["revenue_recovered"] == 1250
    assert summary["pending_recoveries"] == 1
    categories = {item["failure_category"]: item["count"] for item in failures["failures"]}
    assert categories["TEMPORARY_PAYMENT_FAILURE"] == 1
    assert categories["CUSTOMER_CORRECTABLE"] == 1
    assert recoveries["action_counts"]["RETRY_NOW"] >= 1
    assert recoveries["execution_status_counts"]["SIMULATED"] >= 1
    assert recoveries["recovered_amount"] == 1250
    assert audit["limit"] == 3
    assert audit["total"] >= 2
    assert 0 < len(audit["entries"]) <= 3


def test_failed_razorpay_webhook_triggers_simulated_recovery_workflow(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "webhook_secret"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)
    get_settings.cache_clear()
    order_body = client.post("/api/v1/razorpay/orders", json={"amount": 1500}).json()
    payment_body = client.post(
        "/api/v1/payments",
        json={
            "order_id": order_body["local_order_id"],
            "customer_id": "razorpay_test_customer",
            "amount": 1500,
            "currency": "INR",
            "razorpay_order_id": order_body["razorpay_order_id"],
            "razorpay_payment_id": "pay_webhook_failed",
        },
    ).json()
    event = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_webhook_failed",
                    "order_id": order_body["razorpay_order_id"],
                    "error_code": "PROVIDER_UNAVAILABLE",
                    "error_description": "Provider temporarily unavailable.",
                }
            }
        },
    }
    body = json.dumps(event).encode()

    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={
            "X-Razorpay-Signature": webhook_signature(body, secret),
            "X-Razorpay-Event-Id": "evt_failed_1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PROCESSED_RECOVERY"
    assert client.get(f"/api/v1/payments/{payment_body['id']}").json()["status"] == "PAYMENT_FAILED"
    get_settings.cache_clear()
