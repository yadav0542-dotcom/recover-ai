import type { DashboardAudit, DashboardSummary, FailureDistribution, HealthResponse, OrderResponse, RecoveryMetrics, RecoveryWorkflowResponse, SimulationResponse } from "@/types/api";

const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function getBackendHealth(): Promise<HealthResponse> {
  const response = await fetch(`${backendBaseUrl}/api/v1/health`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Backend health check failed (${response.status})`);
  }

  return response.json() as Promise<HealthResponse>;
}

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return body as T;
}

export function createOrder(payload: { customer_id: string; amount: number; currency: string }): Promise<OrderResponse> {
  return request<OrderResponse>("/api/v1/orders", { method: "POST", body: JSON.stringify(payload) });
}

export function simulatePayment(payload: { order_id: string; payment_method: string; amount: number; simulated_result: string }): Promise<SimulationResponse> {
  return request<SimulationResponse>("/api/v1/payments/simulate", { method: "POST", body: JSON.stringify(payload) });
}

export function processRecovery(paymentId: string): Promise<RecoveryWorkflowResponse> {
  return request<RecoveryWorkflowResponse>("/api/v1/recovery/process", { method: "POST", body: JSON.stringify({ payment_id: paymentId }) });
}

export function getDashboardSummary(): Promise<DashboardSummary> { return request<DashboardSummary>("/api/v1/dashboard/summary", { method: "GET" }); }
export function getDashboardFailures(): Promise<{ failures: FailureDistribution[] }> { return request<{ failures: FailureDistribution[] }>("/api/v1/dashboard/failures", { method: "GET" }); }
export function getDashboardRecoveries(): Promise<RecoveryMetrics> { return request<RecoveryMetrics>("/api/v1/dashboard/recoveries", { method: "GET" }); }
export function getDashboardAudit(): Promise<DashboardAudit> { return request<DashboardAudit>("/api/v1/dashboard/audit?limit=6", { method: "GET" }); }
