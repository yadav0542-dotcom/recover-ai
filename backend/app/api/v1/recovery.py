from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.recovery_agent import recommend_recovery
from app.core.database import get_db
from app.models.enums import OrderStatus, PaymentStatus
from app.models.order import Order
from app.models.payment import Payment
from app.policies.recovery import PolicyInput, audit_policy_decision, evaluate_recovery_policy
from app.schemas.classification import (
    FailureClassificationRequest,
    FailureClassificationResponse,
)
from app.schemas.prediction import RecoveryPredictionRequest, RecoveryPredictionResponse
from app.schemas.recommendation import (
    RecoveryRecommendationRequest,
    RecoveryRecommendationResponse,
)
from app.schemas.evaluation import RecoveryEvaluationRequest, RecoveryEvaluationResponse
from app.schemas.execution import RecoveryExecutionRequest, RecoveryExecutionResponse
from app.schemas.workflow import RecoveryWorkflowRequest, RecoveryWorkflowResponse
from app.ml.recovery_model import predict_recovery_probability
from app.services.recovery_execution import execute_recovery_action
from app.services.recovery_workflow import process_recovery_workflow
from app.services.failure_classifier import classify_payment_failure


router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.post("/process", response_model=RecoveryWorkflowResponse)
def process_recovery(
    payload: RecoveryWorkflowRequest,
    db: Session = Depends(get_db),
) -> RecoveryWorkflowResponse:
    payment_id = payload.payment_id
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    if payment.order_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment has no related order.")
    order = db.get(Order, payment.order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    try:
        result = process_recovery_workflow(db, payment, order)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RecoveryWorkflowResponse(
        payment_id=result.payment_id,
        order_id=result.order_id,
        failure_category=result.failure_category,
        recovery_probability=result.recovery_probability,
        ai_recommended_action=result.ai_recommended_action,
        final_policy_action=result.final_policy_action,
        retry_allowed=result.retry_allowed,
        execution_status=result.execution_status,
        explanation=result.explanation,
        policy_reason=result.policy_reason,
        safety_override=result.safety_override,
        audit_id=result.audit_id,
        policy_audit_id=result.policy_audit_id,
    )


@router.post("/execute", response_model=RecoveryExecutionResponse)
def execute_recovery(
    payload: RecoveryExecutionRequest,
    db: Session = Depends(get_db),
) -> RecoveryExecutionResponse:
    payment = db.get(Payment, payload.payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    order = db.get(Order, payload.order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if payment.order_id != order.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment does not belong to the supplied order.")

    try:
        result = execute_recovery_action(
            db,
            payment,
            order,
            payload.final_action,
            payload.policy_decision,
            payload.retry_allowed,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()

    return RecoveryExecutionResponse(
        payment_id=result.payment_id,
        final_action=result.final_action,
        execution_status=result.execution_status,
        executed=result.executed,
        message=result.message,
        safety_reason=result.safety_reason,
        audit_id=result.audit_id,
    )


@router.post("/evaluate", response_model=RecoveryEvaluationResponse)
def evaluate_recovery(
    payload: RecoveryEvaluationRequest,
    db: Session = Depends(get_db),
) -> RecoveryEvaluationResponse:
    order_status = payload.order_status or OrderStatus.PENDING
    failure_category = payload.failure_category
    failure_reason = payload.failure_reason
    failure_source = payload.failure_source

    if failure_category is None and payload.payment_status not in (
        PaymentStatus.SUCCESS,
        PaymentStatus.REFUND_PENDING,
        PaymentStatus.REFUND_FAILED,
    ):
        try:
            classification = classify_payment_failure(
                failure_code=payload.failure_code,
                failure_reason=payload.failure_reason,
                failure_source=payload.failure_source,
                failure_step=payload.failure_step,
                payment_method=payload.payment_method,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        failure_category = classification.category
        failure_reason = classification.reason
        failure_source = classification.source

    recovery_probability = payload.recovery_probability
    if recovery_probability is None and failure_category is not None:
        prediction = predict_recovery_probability(
            payment_amount=payload.payment_amount,
            payment_method=payload.payment_method,
            failure_category=failure_category,
            previous_attempts=payload.previous_attempt_count,
            time_since_failure_minutes=0,
            provider_health=payload.provider_health,
            customer_successful_payments=payload.customer_successful_payments,
            order_value=payload.order_value or payload.payment_amount,
        )
        recovery_probability = prediction.recovery_probability
    recovery_probability = recovery_probability if recovery_probability is not None else 1.0

    ai_action = payload.ai_recommended_action
    ai_confidence = payload.ai_confidence
    if ai_action is None:
        recommendation = recommend_recovery(
            RecoveryRecommendationRequest(
                payment_id=payload.payment_id,
                payment_status=payload.payment_status,
                order_status=order_status,
                failure_category=failure_category,
                failure_reason=failure_reason,
                failure_source=failure_source,
                payment_method=payload.payment_method,
                payment_amount=payload.payment_amount,
                recovery_probability=recovery_probability,
                provider_health=payload.provider_health,
                previous_attempt_count=payload.previous_attempt_count,
            )
        )
        ai_action = recommendation.recommended_action
        ai_confidence = recommendation.confidence

    decision = evaluate_recovery_policy(
        PolicyInput(
            payment_status=payload.payment_status,
            order_status=order_status,
            failure_category=failure_category,
            failure_source=failure_source,
            provider_health=payload.provider_health,
            ai_recommendation=ai_action,
        )
    )
    audit_policy_decision(db, "payment", payload.payment_id, PolicyInput(
        payment_status=payload.payment_status,
        order_status=order_status,
        failure_category=failure_category,
        failure_source=failure_source,
        provider_health=payload.provider_health,
        ai_recommendation=ai_action,
    ), decision)
    db.commit()

    return RecoveryEvaluationResponse(
        payment_id=payload.payment_id,
        failure_category=failure_category,
        ai_recommended_action=decision.recommended_action,
        final_policy_action=decision.final_action,
        retry_allowed=decision.retry_allowed,
        policy_decision="OVERRIDE" if decision.ai_overridden else ("ALLOW" if decision.retry_allowed else "BLOCK"),
        reason=decision.reason,
        safety_override=decision.ai_overridden,
        confidence=ai_confidence,
    )


@router.post("/recommend", response_model=RecoveryRecommendationResponse)
def recommend_recovery_action(
    payload: RecoveryRecommendationRequest,
) -> RecoveryRecommendationResponse:
    recommendation = recommend_recovery(payload)
    return RecoveryRecommendationResponse(
        recommended_action=recommendation.recommended_action,
        recommended_delay_minutes=recommendation.recommended_delay_minutes,
        confidence=recommendation.confidence,
        explanation=recommendation.explanation,
        safety_notes=recommendation.safety_notes,
    )


@router.post("/predict", response_model=RecoveryPredictionResponse)
def predict_recovery(
    payload: RecoveryPredictionRequest,
) -> RecoveryPredictionResponse:
    prediction = predict_recovery_probability(
        payment_amount=payload.payment_amount,
        payment_method=payload.payment_method,
        failure_category=payload.failure_category,
        previous_attempts=payload.previous_attempts,
        time_since_failure_minutes=payload.time_since_failure_minutes,
        provider_health=payload.provider_health,
        customer_successful_payments=payload.customer_successful_payments,
        order_value=payload.order_value,
    )
    return RecoveryPredictionResponse(
        payment_id=payload.payment_id,
        recovery_probability=prediction.recovery_probability,
        model_version=prediction.model_version,
        important_features=prediction.important_features,
        explanation=prediction.explanation,
    )


@router.post("/classify", response_model=FailureClassificationResponse)
def classify_failure(
    payload: FailureClassificationRequest,
    db: Session = Depends(get_db),
) -> FailureClassificationResponse:
    payment = None
    if payload.payment_id is not None:
        payment = db.get(Payment, payload.payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")

    try:
        classification = classify_payment_failure(
            simulated_result=payload.simulated_result,
            failure_code=(payload.failure_code if payload.failure_code is not None else payment.failure_code if payment else None),
            failure_reason=(payload.failure_reason if payload.failure_reason is not None else payment.failure_reason if payment else None),
            failure_source=(payload.failure_source if payload.failure_source is not None else payment.failure_source if payment else None),
            failure_step=(payload.failure_step if payload.failure_step is not None else payment.failure_step if payment else None),
            payment_method=(payload.payment_method if payload.payment_method is not None else payment.payment_method if payment else None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return FailureClassificationResponse(
        payment_id=payload.payment_id,
        failure_category=classification.category,
        reason=classification.reason,
        failure_source=classification.source,
        failure_step=classification.step,
    )
