"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeading } from "@/components/page-heading";
import {
  getDashboardAudit,
  getDashboardFailures,
  getDashboardRecoveries,
  getDashboardSummary,
} from "@/lib/api";

import type {
  AuditEntry,
  DashboardSummary,
  FailureDistribution,
  RecoveryMetrics,
} from "@/types/api";

const auditEventLabels: Record<string, string> = {
  POLICY_OVERRIDE: "Policy override",
  RECOVERY_EXECUTION: "Recovery executed",
  POLICY_DECISION: "Policy decision",
  PAYMENT_CREATED: "Payment created",
  PAYMENT_FAILED: "Payment failed",
  PAYMENT_SUCCESS: "Payment succeeded",
  RECOVERY_STARTED: "Recovery started",
  RECOVERY_COMPLETED: "Recovery completed",
  RETRY_BLOCKED: "Retry blocked",
  REFUND_RECONCILIATION: "Refund reconciliation",
};

function formatAuditEvent(eventType: string) {
  return (
    auditEventLabels[eventType] ??
    eventType
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

const failureLabels: Record<string, string> = {
  CUSTOMER_CANCELLED_CHECKOUT: "Customer cancelled checkout",
  INSUFFICIENT_FUNDS: "Insufficient funds",
  TEMPORARY_PAYMENT_FAILURE: "Temporary payment failure",
  CUSTOMER_CORRECTABLE: "Customer correction required",
  HIGH_RISK_FRAUD_BLOCK: "High-risk fraud block",
  PAYMENT_TIMEOUT: "Payment timeout",
};

function formatFailureCategory(category: string) {
  return (
    failureLabels[category] ??
    category
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

const recoveryActionLabels: Record<string, string> = {
  RETRY_NOW: "Retry now",
  WAIT_AND_NOTIFY: "Wait and notify",
  ALTERNATE_PAYMENT: "Alternate payment",
  RESUME_PAYMENT: "Resume payment",
  BLOCK_RETRY: "Block retry",
  REFUND_RECONCILE: "Refund reconciliation",
  RECONCILE: "Reconcile",
  TRACK_REFUND: "Track refund",
  ESCALATE: "Escalate",
  REVIEW: "Review",
};

function formatRecoveryAction(action: string) {
  return (
    recoveryActionLabels[action] ??
    action
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

export default function Home() {
  const [summary, setSummary] =
    useState<DashboardSummary | null>(null);

  const [failures, setFailures] =
    useState<FailureDistribution[]>([]);

  const [recoveries, setRecoveries] =
    useState<RecoveryMetrics | null>(null);

  const [audit, setAudit] =
    useState<AuditEntry[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      getDashboardSummary(),
      getDashboardFailures(),
      getDashboardRecoveries(),
      getDashboardAudit(),
    ])
      .then(
        ([
          summaryResponse,
          failureResponse,
          recoveryResponse,
          auditResponse,
        ]) => {
          setSummary(summaryResponse);
          setFailures(failureResponse.failures);
          setRecoveries(recoveryResponse);
          setAudit(auditResponse.entries);
        },
      )
      .catch((requestError) =>
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Unable to load dashboard data.",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  const metrics = [
    {
      label: "Revenue at risk",
      value: summary
        ? `₹ ${summary.revenue_at_risk.toLocaleString("en-IN")}`
        : "—",
      detail: "Failed payment volume",
      accent: "bg-blue-600",
    },
    {
      label: "Revenue recovered",
      value: summary
        ? `₹ ${summary.revenue_recovered.toLocaleString("en-IN")}`
        : "—",
      detail: "Successful recovery volume",
      accent: "bg-emerald-600",
    },
    {
      label: "Recovery rate",
      value: summary
        ? `${summary.recovery_rate}%`
        : "—",
      detail: `${summary?.successful_payments ?? "—"} successful payments`,
      accent: "bg-indigo-600",
    },
    {
      label: "Unsafe retries blocked",
      value: summary
        ? String(summary.unsafe_retries_blocked)
        : "—",
      detail: "Policy and execution guards",
      accent: "bg-red-600",
    },
    {
      label: "Pending recoveries",
      value: summary
        ? String(summary.pending_recoveries)
        : "—",
      detail: "Awaiting recovery action",
      accent: "bg-amber-500",
    },
  ];

  const maxFailureCount = Math.max(
    ...failures.map((failure) => failure.count),
    1,
  );

  return (
    <div className="mx-auto max-w-7xl">
      {/* Page heading */}
      <PageHeading
        eyebrow="Overview"
        title="Revenue recovery"
        description="Monitor payment failures, recovery activity, and the policy controls protecting payment execution."
        action={
          <span className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Live database metrics
          </span>
        }
      />

      {/* Error */}
      {error && (
        <div className="error-box mb-6 p-4 text-sm">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="mb-6 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-700">
          Loading dashboard metrics…
        </div>
      )}

      {/* KPI metrics */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {metrics.map((metric) => (
          <article
            key={metric.label}
            className="panel p-5"
          >
            <div
              className={`mb-5 h-1 w-8 rounded-full ${metric.accent}`}
            />

            <p className="text-sm font-medium text-[#526071]">
              {metric.label}
            </p>

            <p className="metric-value mt-3">
              {metric.value}
            </p>

            <p className="mt-3 text-xs leading-5 text-[#7a8797]">
              {metric.detail}
            </p>
          </article>
        ))}
      </section>

      {/* Failure distribution + simulator */}
      <section className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        {/* Failure distribution */}
        <article className="panel p-6">
          <div className="flex items-start justify-between gap-5">
            <div>
              <p className="text-sm font-semibold text-[#172033]">
                Failure distribution
              </p>

              <p className="mt-1 text-sm text-[#7a8797]">
                Payment failure categories recorded by the
                classifier.
              </p>
            </div>

            <span className="text-sm font-medium text-[#526071]">
              {summary?.failed_payments ?? "—"} failures
            </span>
          </div>

          <div className="mt-7 space-y-5">
            {failures.length === 0 && !loading && (
              <p className="rounded-lg border border-dashed border-[#d5dce5] p-8 text-center text-sm text-[#7a8797]">
                No failures recorded yet.
              </p>
            )}

            {failures.map((failure) => (
              <div key={failure.failure_category}>
                <div className="mb-2 flex justify-between gap-4 text-sm">
                  <span className="break-words text-[#526071]">
                    {formatFailureCategory(
                      failure.failure_category,
                    )}
                  </span>

                  <span className="font-semibold text-[#172033]">
                    {failure.count}
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-[#edf0f4]">
                  <div
                    className="h-full rounded-full bg-blue-600"
                    style={{
                      width: `${
                        (failure.count / maxFailureCount) *
                        100
                      }%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </article>

        {/* Recovery workflow */}
        <article className="panel p-6">
          <p className="text-sm font-semibold text-[#172033]">
            Recovery workflow
          </p>

          <h2 className="mt-2 text-xl font-semibold text-[#172033]">
            Test a payment event
          </h2>

          <p className="mt-3 text-sm leading-6 text-[#526071]">
            Create a controlled payment event and send it
            through the RecoverAI recovery workflow.
          </p>

          <Link
            href="/payment-simulator"
            className="primary-button mt-7"
          >
            Open payment simulator
            <span className="ml-2" aria-hidden="true">
              →
            </span>
          </Link>

          <div className="mt-7 border-t border-[#e2e7ee] pt-5">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[#7a8797]">
                Payments tracked
              </span>

              <span className="font-semibold text-[#172033]">
                {summary?.total_payments ?? "—"}
              </span>
            </div>

            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-[#7a8797]">
                Execution mode
              </span>

              <span className="font-semibold text-emerald-700">
                Simulated only
              </span>
            </div>
          </div>
        </article>
      </section>

      {/* Recovery activity + Audit */}
      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* Recovery activity */}
        <article className="panel p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-[#172033]">
                Recovery activity
              </p>

              <p className="mt-1 text-sm text-[#7a8797]">
                Actions and execution outcomes.
              </p>
            </div>

            <Link
              href="/recovery-cases"
              className="rounded-md px-2 py-1 text-sm font-semibold text-blue-600 transition-colors hover:bg-blue-50 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              Open cases →
            </Link>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-3">
            {Object.entries(
              recoveries?.action_counts ?? {},
            ).map(([action, count]) => (
              <div
                key={action}
                className="rounded-lg border border-[#e2e7ee] bg-[#fafbfc] p-4"
              >
                <p className="break-words text-xs font-medium text-[#7a8797]">
                  {formatRecoveryAction(action)}
                </p>

                <p className="mt-2 text-2xl font-bold text-[#172033]">
                  {count}
                </p>
              </div>
            ))}

            {!loading &&
              Object.keys(
                recoveries?.action_counts ?? {},
              ).length === 0 && (
                <p className="col-span-2 text-sm text-[#7a8797]">
                  No recovery executions recorded yet.
                </p>
              )}
          </div>
        </article>

        {/* Recent audit activity */}
        <article className="panel p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-[#172033]">
                Recent audit activity
              </p>

              <p className="mt-1 text-sm text-[#7a8797]">
                Traceability for recovery decisions.
              </p>
            </div>

            <Link
              href="/audit-logs"
              className="rounded-md px-2 py-1 text-sm font-semibold text-blue-600 transition-colors hover:bg-blue-50 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              View all →
            </Link>
          </div>

          <div className="mt-5">
            {audit.map((entry) => (
              <div
                key={entry.id}
                className="border-b border-[#e2e7ee] py-4 last:border-0"
              >
                {/* Event name + time */}
                <div className="flex items-start justify-between gap-4">
                  <span className="text-sm font-bold text-[#172033]">
                    {formatAuditEvent(entry.event_type)}
                  </span>

                  <span className="shrink-0 text-xs font-medium text-[#66758a]">
                    {entry.created_at
                      ? new Date(
                          entry.created_at,
                        ).toLocaleTimeString()
                      : "—"}
                  </span>
                </div>

                {/* Reason */}
                <p className="mt-1 text-sm leading-5 text-[#66758a]">
                  {entry.reason}
                </p>
              </div>
            ))}

            {!loading && audit.length === 0 && (
              <p className="text-sm text-[#7a8797]">
                No audit events recorded yet.
              </p>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}