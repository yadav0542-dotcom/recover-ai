import type { HealthResponse } from "@/types/api";

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
