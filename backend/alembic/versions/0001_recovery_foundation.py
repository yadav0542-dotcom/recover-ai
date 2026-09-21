"""Create RecoverAI recovery foundation tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_recovery_foundation"
down_revision = None
branch_labels = None
depends_on = None

payment_status = postgresql.ENUM("PENDING", "PAYMENT_SUCCESS", "PAYMENT_FAILED", "REFUND_PENDING", "REFUND_FAILED", name="paymentstatus", create_type=False)
order_status = postgresql.ENUM("ORDER_PENDING", "ORDER_PAID", "ORDER_CANCELLED", "ORDER_STATUS_UNKNOWN", name="orderstatus", create_type=False)
failure_category = postgresql.ENUM("HIGH_RISK_FRAUD_BLOCK", "TEMPORARY_PAYMENT_FAILURE", "CUSTOMER_CORRECTABLE", "INSUFFICIENT_FUNDS", "EXPIRED_CARD", "CUSTOMER_CANCELLED_CHECKOUT", name="failurecategory", create_type=False)
failure_source = postgresql.ENUM("CUSTOMER", "PROVIDER", "BANK", "SYSTEM", name="paymentfailuresource", create_type=False)
failure_step = postgresql.ENUM("AUTHORIZATION", "CAPTURE", "CHECKOUT", "REFUND", name="paymentfailurestep", create_type=False)
recovery_action = postgresql.ENUM("REFUND_RECONCILE", "RECONCILE", "BLOCK_RETRY", "WAIT_AND_NOTIFY", "RETRY_NOW", "ALTERNATE_PAYMENT", "RESUME_PAYMENT", "TRACK_REFUND", "ESCALATE", "REVIEW", name="recoveryaction", create_type=False)
recovery_status = postgresql.ENUM("OPEN", "RESOLVED", "ESCALATED", name="recoverycasestatus", create_type=False)

def upgrade():
    bind = op.get_bind()
    for item in (payment_status, order_status, failure_category, failure_source, failure_step, recovery_action, recovery_status): item.create(bind, checkfirst=True)
    op.create_table("orders", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("razorpay_order_id", sa.String(100), unique=True), sa.Column("customer_id", sa.String(100), nullable=False), sa.Column("amount", sa.Integer(), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="INR"), sa.Column("status", order_status, nullable=False, server_default="ORDER_PENDING"), sa.Column("cart_data", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("payments", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id")), sa.Column("razorpay_payment_id", sa.String(100), unique=True), sa.Column("razorpay_order_id", sa.String(100)), sa.Column("customer_id", sa.String(100), nullable=False), sa.Column("amount", sa.Integer(), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="INR"), sa.Column("payment_method", sa.String(50)), sa.Column("status", payment_status, nullable=False, server_default="PENDING"), sa.Column("failure_code", sa.String(100)), sa.Column("failure_reason", sa.String(500)), sa.Column("failure_source", failure_source), sa.Column("failure_step", failure_step), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("recovery_cases", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("payment_id", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=False), sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id")), sa.Column("failure_category", failure_category, nullable=False), sa.Column("recoverability_probability", sa.Float()), sa.Column("recommended_action", recovery_action), sa.Column("recommended_delay", sa.Integer()), sa.Column("confidence", sa.Float()), sa.Column("policy_decision", recovery_action, nullable=False), sa.Column("status", recovery_status, nullable=False, server_default="OPEN"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("audit_logs", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("entity_type", sa.String(50), nullable=False), sa.Column("entity_id", sa.String(64), nullable=False), sa.Column("event_type", sa.String(100), nullable=False), sa.Column("previous_state", sa.JSON()), sa.Column("new_state", sa.JSON()), sa.Column("reason", sa.Text(), nullable=False), sa.Column("actor", sa.String(100), nullable=False, server_default="policy_engine"), sa.Column("metadata", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for table, columns in (("orders", ("razorpay_order_id", "customer_id")), ("payments", ("order_id", "razorpay_payment_id", "razorpay_order_id", "customer_id", "failure_code")), ("recovery_cases", ("payment_id", "order_id")), ("audit_logs", ("entity_type", "entity_id"))):
        for column in columns: op.create_index(f"ix_{table}_{column}", table, [column])

def downgrade():
    for table in ("audit_logs", "recovery_cases", "payments", "orders"): op.drop_table(table)
    bind = op.get_bind()
    for item in (recovery_status, recovery_action, failure_step, failure_source, failure_category, order_status, payment_status): item.drop(bind, checkfirst=True)