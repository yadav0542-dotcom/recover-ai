// frontend/types/api.ts

export type HealthResponse = {
  status: "ok";
  service: string;
};

export type OrderResponse = {
  id: string;
  customer_id: string;
  amount: number;
  currency: string;
  status: string;
  razorpay_order_id: string | null;
  cart_data?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SimulationResponse = {
  payment_id: string;
  order_id: string;
  payment_status: string;
  failure_category: string | null;
  failure_reason: string | null;
  failure_source: string | null;
  failure_step: string | null;
};

export type RecoveryWorkflowResponse = {
  payment_id: string;
  order_id: string;
  failure_category: string | null;
  recovery_probability: number | null;
  ai_recommended_action: string | null;
  final_policy_action: string | null;
  retry_allowed: boolean;
  execution_status: string;
  explanation: string;
  policy_reason: string;
  safety_override: boolean;
  audit_id: string | null;
  policy_audit_id: string | null;
};

export type DashboardSummary = {
  revenue_at_risk: number;
  revenue_recovered: number;
  recovery_rate: number;
  unsafe_retries_blocked: number;
  pending_recoveries: number;
  total_payments: number;
  failed_payments: number;
  successful_payments: number;
};

export type FailureDistribution = {
  failure_category: string;
  count: number;
};

export type RecoveryMetrics = {
  action_counts: Record<string, number>;
  execution_status_counts: Record<string, number>;
  recovered_amount: number;
  blocked_retry_count: number;
};

export type AuditState = Record<string, unknown>;

export type AuditEntry = {
  id: string;
  entity_type: string;
  entity_id: string;
  event_type: string;
  reason: string;
  actor: string;
  created_at: string | null;
  previous_state: AuditState | null;
  new_state: AuditState | null;
  metadata: AuditState | null;
};

export type DashboardAudit = {
  entries: AuditEntry[];
  limit: number;
  offset: number;
  total: number;
};