"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { PageHeading } from "@/components/page-heading";
import { createOrder, processRecovery, simulatePayment } from "@/lib/api";
import type {
  RecoveryWorkflowResponse,
  SimulationResponse,
} from "@/types/api";

type ScenarioCategory =
  | "success"
  | "recoverable"
  | "blocked"
  | "checkout_cancel"
  | "reconciliation";

interface ScenarioConfig {
  value: string;
  label: string;
  description: string;
  category: ScenarioCategory;
  guidance: string;
  badgeLabel: string;
}

const SCENARIOS: ScenarioConfig[] = [
  {
    value: "SUCCESS",
    label: "Successful payment",
    description: "Payment completed successfully.",
    category: "success",
    guidance:
      "Payment completed successfully. No recovery action is required.",
    badgeLabel: "Payment succeeded",
  },
  {
    value: "TEMPORARY_FAILURE",
    label: "Temporary payment failure",
    description:
      "Temporary provider issue; waiting or retry may be considered.",
    category: "recoverable",
    guidance:
      "This appears to be a temporary issue. The payment can be evaluated by the recovery workflow.",
    badgeLabel: "Temporary failure",
  },
  {
    value: "PAYMENT_TIMEOUT",
    label: "Provider timeout",
    description: "The payment provider did not respond in time.",
    category: "recoverable",
    guidance:
      "The provider did not respond in time. Recovery policy can evaluate whether waiting or retrying is appropriate.",
    badgeLabel: "Provider timeout",
  },
  {
    value: "INSUFFICIENT_FUNDS",
    label: "Insufficient funds",
    description:
      "The issuing bank declined the payment because funds were insufficient.",
    category: "recoverable",
    guidance:
      "Customer action or an alternate payment method may be required.",
    badgeLabel: "Insufficient funds",
  },
  {
    value: "CUSTOMER_CORRECTABLE",
    label: "Customer correction required",
    description: "The customer must correct payment details.",
    category: "recoverable",
    guidance:
      "The customer should correct the payment details before trying again.",
    badgeLabel: "Customer action required",
  },
  {
    value: "HIGH_RISK_FRAUD_BLOCK",
    label: "High-risk fraud block",
    description:
      "Payment was blocked by fraud controls; automatic retry should remain blocked.",
    category: "blocked",
    guidance:
      "Automatic retry must remain blocked because the payment was stopped by risk controls.",
    badgeLabel: "Risk blocked",
  },
  {
    value: "CUSTOMER_CANCELLED",
    label: "Customer cancelled checkout",
    description: "Customer cancelled checkout before payment succeeded.",
    category: "checkout_cancel",
    guidance:
      "Checkout was cancelled before payment succeeded. The customer can resume payment later. No refund is required.",
    badgeLabel: "Checkout cancelled",
  },
  {
    value: "ORDER_CANCELLED_AFTER_PAYMENT",
    label: "Payment successful → platform cancelled order",
    description:
      "Payment succeeds first, then the shopping platform cancels the order.",
    category: "reconciliation",
    guidance:
      "The payment has already succeeded, so retry is prohibited. Refund reconciliation is required instead.",
    badgeLabel: "Refund reconciliation",
  },
];

interface PresetScenario {
  id: string;
  name: string;
  outcome: string;
  result?: string;
  amount?: string;
  method?: string;
  customerId?: string;
  isReconciliationDemo?: boolean;
  badge: string;
  badgeClass: string;
}

const PRESET_SCENARIOS: PresetScenario[] = [
  {
    id: "preset-temp",
    name: "Temporary payment failure",
    outcome: "Recovery workflow evaluation",
    result: "TEMPORARY_FAILURE",
    amount: "1250",
    method: "card",
    customerId: "demo_customer_01",
    badge: "Recoverable",
    badgeClass: "border-amber-200 bg-amber-50 text-amber-700",
  },
  {
    id: "preset-cancel",
    name: "Customer cancelled checkout",
    outcome: "Resume payment, no refund",
    result: "CUSTOMER_CANCELLED",
    amount: "850",
    method: "upi",
    customerId: "demo_customer_02",
    badge: "Checkout cancellation",
    badgeClass: "border-blue-200 bg-blue-50 text-blue-700",
  },
  {
    id: "preset-fraud",
    name: "High-risk fraud block",
    outcome: "Automatic retry blocked",
    result: "HIGH_RISK_FRAUD_BLOCK",
    amount: "45000",
    method: "card",
    customerId: "suspicious_buyer_07",
    badge: "Policy blocked",
    badgeClass: "border-red-200 bg-red-50 text-red-700",
  },
  {
    id: "preset-recon",
    name: "Payment successful, platform cancelled order",
    outcome: "Refund reconciliation, no retry",
    result: "ORDER_CANCELLED_AFTER_PAYMENT",
    amount: "2500",
    method: "card",
    customerId: "demo_customer_03",
    isReconciliationDemo: true,
    badge: "Reconciliation",
    badgeClass: "border-violet-200 bg-violet-50 text-violet-700",
  },
  {
    id: "preset-success",
    name: "Successful payment",
    outcome: "No recovery action required",
    result: "SUCCESS",
    amount: "1250",
    method: "card",
    customerId: "demo_customer_01",
    badge: "Completed",
    badgeClass: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
];

const scenarioLabels: Record<string, string> = {
  SUCCESS: "Successful payment",
  TEMPORARY_FAILURE: "Temporary payment failure",
  PAYMENT_TIMEOUT: "Provider timeout",
  INSUFFICIENT_FUNDS: "Insufficient funds",
  CUSTOMER_CORRECTABLE: "Customer correction required",
  HIGH_RISK_FRAUD_BLOCK: "High-risk fraud block",
  CUSTOMER_CANCELLED: "Customer cancelled checkout",
};

const actionLabels: Record<string, string> = {
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

function humanizeAction(action: string | null | undefined) {
  if (!action) return "—";

  return actionLabels[action] ?? action.replaceAll("_", " ");
}

export default function PaymentSimulatorPage() {
  const [customerId, setCustomerId] = useState("demo_customer_01");
  const [amount, setAmount] = useState("1250");
  const [method, setMethod] = useState("card");
  const [result, setResult] = useState("TEMPORARY_FAILURE");

  const [response, setResponse] =
    useState<SimulationResponse | null>(null);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [touched, setTouched] = useState({
    customerId: false,
    amount: false,
  });

  const [copiedId, setCopiedId] = useState(false);

  const [recoveryLoading, setRecoveryLoading] = useState(false);
  const [recoveryResponse, setRecoveryResponse] =
    useState<RecoveryWorkflowResponse | null>(null);

  const [recoveryError, setRecoveryError] = useState("");

  const [reconciliationDemo, setReconciliationDemo] =
    useState(false);

  const reconciliationRef = useRef<HTMLDivElement>(null);

  const isOrderCancellationDemo =
    result === "ORDER_CANCELLED_AFTER_PAYMENT";

  const isCustomerIdValid = customerId.trim().length > 0;

  const numericAmount = Number(amount);

  const isAmountValid =
    !Number.isNaN(numericAmount) && numericAmount > 0;

  const isFormValid =
    isCustomerIdValid && isAmountValid;

  const currentScenario =
    SCENARIOS.find((item) => item.value === result) ??
    SCENARIOS[1];

  function applyPreset(preset: PresetScenario) {
    if (preset.result) {
      setResult(preset.result);
    }

    if (preset.amount) {
      setAmount(preset.amount);
    }

    if (preset.method) {
      setMethod(preset.method);
    }

    if (preset.customerId) {
      setCustomerId(preset.customerId);
    }

    setTouched({
      customerId: false,
      amount: false,
    });

    setError("");
    setResponse(null);
    setRecoveryResponse(null);
    setRecoveryError("");
    setReconciliationDemo(
      Boolean(preset.isReconciliationDemo),
    );

    if (preset.isReconciliationDemo) {
      setTimeout(() => {
        reconciliationRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 50);
    }
  }

  async function submit() {
    setTouched({
      customerId: true,
      amount: true,
    });

    if (!isFormValid) return;

    setLoading(true);
    setError("");
    setResponse(null);
    setRecoveryResponse(null);
    setRecoveryError("");
    setReconciliationDemo(false);

    try {
      const order = await createOrder({
        customer_id: customerId.trim(),
        amount: numericAmount,
        currency: "INR",
      });

      /*
       * The backend currently understands SUCCESS as a successful
       * payment event. ORDER_CANCELLED_AFTER_PAYMENT is a frontend
       * demonstration layered on top of that successful payment.
       */
      const simulation = await simulatePayment({
        order_id: order.id,
        payment_method: method,
        amount: numericAmount,
        simulated_result: isOrderCancellationDemo
          ? "SUCCESS"
          : result,
      });

      setResponse(simulation);

      window.localStorage.setItem(
        "recoverai:last-payment-id",
        simulation.payment_id,
      );

      if (isOrderCancellationDemo) {
        setReconciliationDemo(true);

        setTimeout(() => {
          reconciliationRef.current?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
        }, 150);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to simulate payment.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function runRecovery() {
    if (!response?.payment_id) return;

    setRecoveryLoading(true);
    setRecoveryError("");

    try {
      const recoveryResult = await processRecovery(
        response.payment_id,
      );

      setRecoveryResponse(recoveryResult);
    } catch (requestError) {
      setRecoveryError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to execute recovery workflow.",
      );
    } finally {
      setRecoveryLoading(false);
    }
  }

  function handleCopyPaymentId(id: string) {
    if (!navigator?.clipboard) return;

    navigator.clipboard.writeText(id);
    setCopiedId(true);

    setTimeout(() => {
      setCopiedId(false);
    }, 2000);
  }

  const responseVisual = (() => {
    if (!response) return null;

    if (
      isOrderCancellationDemo &&
      response.payment_status === "PAYMENT_SUCCESS"
    ) {
      return {
        badge:
          "border-violet-200 bg-violet-50 text-violet-700",
        label: "Reconciliation required",
        heading: "Payment succeeded",
        border: "border-violet-200",
        bg: "bg-violet-50/50",
        guidance:
          "The payment succeeded, but the platform has cancelled the order. Payment retry is prohibited; refund reconciliation is required.",
      };
    }

    if (response.payment_status === "PAYMENT_SUCCESS") {
      return {
        badge:
          "border-emerald-200 bg-emerald-50 text-emerald-700",
        label: "Payment successful",
        heading: "Payment completed successfully",
        border: "border-emerald-200",
        bg: "bg-emerald-50/50",
        guidance:
          "Payment completed successfully. No recovery action is required.",
      };
    }

    if (
      response.failure_category ===
      "CUSTOMER_CANCELLED_CHECKOUT"
    ) {
      return {
        badge:
          "border-blue-200 bg-blue-50 text-blue-700",
        label: "Checkout cancelled",
        heading: "Customer cancelled checkout",
        border: "border-blue-200",
        bg: "bg-blue-50/50",
        guidance:
          "The customer cancelled checkout before payment succeeded. Resume payment can be offered later. No refund is required.",
      };
    }

    if (
      response.failure_category ===
      "HIGH_RISK_FRAUD_BLOCK"
    ) {
      return {
        badge:
          "border-red-200 bg-red-50 text-red-700",
        label: "Blocked by policy",
        heading: "High-risk fraud block",
        border: "border-red-200",
        bg: "bg-red-50/50",
        guidance:
          "Automatic retry must remain blocked because the payment was stopped by risk controls.",
      };
    }

    return {
      badge:
        "border-amber-200 bg-amber-50 text-amber-700",
      label: currentScenario.badgeLabel,
      heading:
        scenarioLabels[response.failure_category ?? ""] ??
        "Payment authorization failed",
      border: "border-amber-200",
      bg: "bg-amber-50/50",
      guidance: currentScenario.guidance,
    };
  })();

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeading
        eyebrow="Sandbox / payment events"
        title="Payment simulator"
        description="Stage controlled payment events, inspect failure classifications, and test RecoverAI's safety-first recovery workflow."
        action={
          <span className="inline-flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-600" />
            Simulation only
          </span>
        }
      />

      {/* Sandbox notice */}
      <section className="panel p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-[#172033]">
              Controlled simulation environment
            </p>

            <p className="mt-1.5 max-w-3xl text-sm leading-6 text-[#66758a]">
              This simulator creates controlled payment events
              for testing. It does not process real money.
              Recovery recommendations remain subject to
              deterministic policy controls.
            </p>
          </div>

          <span className="shrink-0 rounded-md border border-[#d5dce5] bg-[#f8fafc] px-3 py-1.5 text-xs font-semibold text-[#526071]">
            Test environment
          </span>
        </div>
      </section>

      {/* Recommended scenarios */}
      <section className="panel p-5">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-semibold text-[#172033]">
              Recommended demo scenarios
            </p>

            <p className="mt-1 text-sm text-[#7a8797]">
              Select a scenario to populate the simulator.
            </p>
          </div>

          <span className="text-xs text-[#7a8797]">
            Five representative cases
          </span>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {PRESET_SCENARIOS.map((preset) => {
            const isSelected =
              result === preset.result;

            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset)}
                className={`group rounded-lg border p-4 text-left transition ${
                  isSelected
                    ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500"
                    : "border-[#e2e7ee] bg-white hover:border-[#c9d2df] hover:bg-[#fafbfc]"
                } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500`}
              >
                <span
                  className={`inline-flex rounded-md border px-2 py-1 text-[10px] font-bold uppercase tracking-wide ${preset.badgeClass}`}
                >
                  {preset.badge}
                </span>

                <p className="mt-3 text-sm font-semibold leading-5 text-[#172033]">
                  {preset.name}
                </p>

                <p className="mt-2 text-xs leading-5 text-[#7a8797]">
                  {preset.outcome}
                </p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Main simulator */}
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        {/* Input */}
        <section className="panel p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Input event</p>

              <h2 className="mt-2 text-xl font-bold text-[#172033]">
                Stage a payment
              </h2>
            </div>

            <span className="rounded-md border border-[#e2e7ee] bg-[#f8fafc] px-2.5 py-1 text-[11px] font-semibold text-[#66758a]">
              Order + payment
            </span>
          </div>

          <p className="mt-2 text-sm leading-6 text-[#66758a]">
            Configure the payment event that you want to send
            through the simulation.
          </p>

          <div className="mt-7 space-y-5">
            {/* Customer ID */}
            <label className="block">
              <div className="mb-2 flex items-center justify-between">
                <span className="field-label mb-0">
                  Customer ID
                </span>

                {touched.customerId &&
                  !isCustomerIdValid && (
                    <span className="text-xs font-medium text-red-600">
                      Required
                    </span>
                  )}
              </div>

              <input
                className={`field-control ${
                  touched.customerId &&
                  !isCustomerIdValid
                    ? "border-red-300"
                    : ""
                }`}
                placeholder="e.g. demo_customer_01"
                value={customerId}
                onBlur={() =>
                  setTouched((previous) => ({
                    ...previous,
                    customerId: true,
                  }))
                }
                onChange={(event) =>
                  setCustomerId(event.target.value)
                }
              />
            </label>

            {/* Amount */}
            <label className="block">
              <div className="mb-2 flex items-center justify-between">
                <span className="field-label mb-0">
                  Amount (INR)
                </span>

                {touched.amount &&
                  !isAmountValid && (
                    <span className="text-xs font-medium text-red-600">
                      Enter an amount greater than ₹0
                    </span>
                  )}
              </div>

              <input
                className={`field-control ${
                  touched.amount &&
                  !isAmountValid
                    ? "border-red-300"
                    : ""
                }`}
                type="number"
                min="1"
                step="1"
                value={amount}
                onBlur={() =>
                  setTouched((previous) => ({
                    ...previous,
                    amount: true,
                  }))
                }
                onChange={(event) =>
                  setAmount(event.target.value)
                }
              />
            </label>

            {/* Payment method */}
            <label className="block">
              <span className="field-label">
                Payment method
              </span>

              <select
                className="field-control"
                value={method}
                onChange={(event) =>
                  setMethod(event.target.value)
                }
              >
                <option value="card">Card</option>
                <option value="upi">UPI</option>
                <option value="netbanking">
                  Netbanking
                </option>
                <option value="wallet">Wallet</option>
              </select>
            </label>

            {/* Simulated result */}
            <label className="block">
              <span className="field-label">
                Simulated result
              </span>

              <select
                className="field-control"
                value={result}
                onChange={(event) =>
                  setResult(event.target.value)
                }
              >
                <optgroup label="Successful payment">
                  <option value="SUCCESS">
                    Successful payment
                  </option>
                </optgroup>

                <optgroup label="Recoverable failures">
                  <option value="TEMPORARY_FAILURE">
                    Temporary payment failure
                  </option>

                  <option value="PAYMENT_TIMEOUT">
                    Provider timeout
                  </option>

                  <option value="INSUFFICIENT_FUNDS">
                    Insufficient funds
                  </option>

                  <option value="CUSTOMER_CORRECTABLE">
                    Customer correction required
                  </option>
                </optgroup>

                <optgroup label="Blocked cases">
                  <option value="HIGH_RISK_FRAUD_BLOCK">
                    High-risk fraud block
                  </option>
                </optgroup>

                <optgroup label="Checkout">
                  <option value="CUSTOMER_CANCELLED">
                    Customer cancelled checkout
                  </option>
                </optgroup>

                <optgroup label="Post-payment reconciliation">
                  <option value="ORDER_CANCELLED_AFTER_PAYMENT">
                    Payment successful → platform cancelled order
                  </option>
                </optgroup>
              </select>
            </label>

            {/* Scenario context */}
            <div className="rounded-lg border border-[#e2e7ee] bg-[#f8fafc] p-4">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-xs font-semibold text-[#526071]">
                  Scenario context
                </span>

                <span className="font-mono text-[10px] text-[#7a8797]">
                  {currentScenario.value}
                </span>
              </div>

              <p className="mt-2 text-sm leading-5 text-[#66758a]">
                {currentScenario.description}
              </p>

              {currentScenario.category ===
                "checkout_cancel" && (
                <div className="mt-3 rounded-md border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
                  <strong>Important:</strong> No successful
                  payment was recorded. This is a checkout
                  cancellation event. No refund should be
                  initiated.
                </div>
              )}

              {currentScenario.category === "blocked" && (
                <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-xs leading-5 text-red-800">
                  <strong>Policy guard:</strong> Automatic
                  retry should remain blocked for this event.
                </div>
              )}

              {currentScenario.category ===
                "reconciliation" && (
                <div className="mt-3 rounded-md border border-violet-200 bg-violet-50 p-3 text-xs leading-5 text-violet-800">
                  <strong>Post-payment scenario:</strong> The
                  payment succeeds first, then the platform
                  cancels the order. Retry is prohibited and
                  refund reconciliation is required.
                </div>
              )}
            </div>
          </div>

          <div className="mt-7 border-t border-[#e2e7ee] pt-5">
            <button
              type="button"
              className="primary-button w-full"
              disabled={loading || !isFormValid}
              onClick={submit}
            >
              {loading ? (
                <>
                  <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Creating order + payment…
                </>
              ) : (
                "Create order + payment"
              )}
            </button>

            <p className="mt-2 text-center text-xs text-[#7a8797]">
              Creates a local order and simulated gateway event.
            </p>
          </div>
        </section>

        {/* Response */}
        <section className="panel min-h-[600px] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Response</p>

              <h2 className="mt-2 text-xl font-bold text-[#172033]">
                Payment event
              </h2>
            </div>

            {response && responseVisual && (
              <span
                className={`rounded-md border px-3 py-1.5 text-xs font-semibold ${responseVisual.badge}`}
              >
                {responseVisual.label}
              </span>
            )}
          </div>

          {error && (
            <div className="error-box mt-6 p-4 text-sm">
              {error}
            </div>
          )}

          {!response && !error && (
            <div className="mt-6 grid min-h-[430px] place-items-center rounded-lg border border-dashed border-[#d5dce5] bg-[#fafbfc] p-8 text-center">
              <div className="max-w-sm">
                <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full border border-[#d5dce5] bg-white text-lg text-[#66758a]">
                  +
                </div>

                <p className="mt-4 text-sm font-semibold text-[#526071]">
                  Ready to stage payment
                </p>

                <p className="mt-2 text-sm leading-6 text-[#7a8797]">
                  Select a scenario and create a payment.
                  The structured gateway response and recovery
                  controls will appear here.
                </p>
              </div>
            </div>
          )}

          {response && responseVisual && (
            <div className="mt-6 space-y-5">
              {/* Payment response */}
              <div
                className={`rounded-lg border p-5 ${responseVisual.border} ${responseVisual.bg}`}
              >
                <p className="text-xs font-bold uppercase tracking-wide text-[#66758a]">
                  {response.payment_status}
                </p>

                <h3 className="mt-2 text-2xl font-bold text-[#172033]">
                  {responseVisual.heading}
                </h3>

                <p className="mt-2 text-sm leading-6 text-[#66758a]">
                  {responseVisual.guidance}
                </p>

                <dl className="mt-5 divide-y divide-[#e2e7ee] border-t border-[#e2e7ee]">
                  <div className="flex items-center justify-between gap-4 py-3">
                    <dt className="text-xs font-medium text-[#7a8797]">
                      Payment ID
                    </dt>

                    <dd className="flex max-w-[65%] items-center gap-2 font-mono text-xs text-[#526071]">
                      <span className="truncate">
                        {response.payment_id}
                      </span>

                      <button
                        type="button"
                        onClick={() =>
                          handleCopyPaymentId(
                            response.payment_id,
                          )
                        }
                        className="shrink-0 rounded border border-[#d5dce5] bg-white px-2 py-1 text-[10px] font-semibold text-[#526071] hover:bg-[#f8fafc]"
                      >
                        {copiedId ? "Copied" : "Copy"}
                      </button>
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4 py-3">
                    <dt className="text-xs font-medium text-[#7a8797]">
                      Order ID
                    </dt>

                    <dd className="max-w-[65%] truncate font-mono text-xs text-[#526071]">
                      {response.order_id}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4 py-3">
                    <dt className="text-xs font-medium text-[#7a8797]">
                      Failure category
                    </dt>

                    <dd className="text-right text-xs font-medium text-[#526071]">
                      {response.failure_category
                        ? scenarioLabels[
                            response.failure_category
                          ] ??
                          response.failure_category.replaceAll(
                            "_",
                            " ",
                          )
                        : "None — payment succeeded"}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4 py-3">
                    <dt className="text-xs font-medium text-[#7a8797]">
                      Failure source
                    </dt>

                    <dd className="text-xs text-[#526071]">
                      {response.failure_source ?? "—"}
                    </dd>
                  </div>

                  <div className="flex justify-between gap-4 py-3">
                    <dt className="text-xs font-medium text-[#7a8797]">
                      Failure step
                    </dt>

                    <dd className="text-xs text-[#526071]">
                      {response.failure_step ?? "—"}
                    </dd>
                  </div>
                </dl>

                {response.failure_reason && (
                  <div className="mt-4 border-t border-[#e2e7ee] pt-4">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                      Gateway reason
                    </p>

                    <p className="mt-1.5 text-sm leading-5 text-[#526071]">
                      {response.failure_reason}
                    </p>
                  </div>
                )}
              </div>

              {/* Recovery workflow */}
              {response.payment_status !==
                "PAYMENT_SUCCESS" && (
                <div className="rounded-lg border border-[#e2e7ee] bg-white p-5">
                  <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                    <div>
                      <p className="text-sm font-semibold text-[#172033]">
                        Recovery workflow
                      </p>

                      <p className="mt-1 text-xs leading-5 text-[#7a8797]">
                        Run AI classification and deterministic
                        policy evaluation for this payment.
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={runRecovery}
                      disabled={
                        recoveryLoading ||
                        !!recoveryResponse
                      }
                      className="secondary-button shrink-0"
                    >
                      {recoveryLoading
                        ? "Evaluating…"
                        : recoveryResponse
                          ? "Workflow completed"
                          : "Run recovery workflow"}
                    </button>
                  </div>

                  {recoveryError && (
                    <div className="error-box mt-4 p-3 text-xs">
                      {recoveryError}
                    </div>
                  )}

                  {recoveryResponse && (
                    <div className="mt-5">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div className="rounded-lg border border-[#e2e7ee] bg-[#f8fafc] p-4">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                            Final policy action
                          </p>

                          <p className="mt-2 text-sm font-bold text-[#172033]">
                            {humanizeAction(
                              recoveryResponse.final_policy_action,
                            )}
                          </p>
                        </div>

                        <div className="rounded-lg border border-[#e2e7ee] bg-[#f8fafc] p-4">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                            ML probability
                          </p>

                          <p className="mt-2 text-sm font-bold text-[#172033]">
                            {recoveryResponse.recovery_probability !==
                            null
                              ? `${Math.round(
                                  recoveryResponse.recovery_probability *
                                    100,
                                )}%`
                              : "—"}
                          </p>
                        </div>

                        <div className="rounded-lg border border-[#e2e7ee] bg-[#f8fafc] p-4">
                          <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                            Execution status
                          </p>

                          <p className="mt-2 text-sm font-bold text-[#172033]">
                            {recoveryResponse.execution_status}
                          </p>
                        </div>
                      </div>

                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div className="rounded-lg border border-[#e2e7ee] p-3">
                          <span className="text-xs text-[#7a8797]">
                            AI recommendation
                          </span>

                          <p className="mt-1 text-sm font-semibold text-[#172033]">
                            {humanizeAction(
                              recoveryResponse.ai_recommended_action,
                            )}
                          </p>
                        </div>

                        <div className="rounded-lg border border-[#e2e7ee] p-3">
                          <span className="text-xs text-[#7a8797]">
                            Retry allowed
                          </span>

                          <p
                            className={`mt-1 text-sm font-semibold ${
                              recoveryResponse.retry_allowed
                                ? "text-emerald-700"
                                : "text-red-700"
                            }`}
                          >
                            {recoveryResponse.retry_allowed
                              ? "Yes"
                              : "No"}
                          </p>
                        </div>

                        <div className="rounded-lg border border-[#e2e7ee] p-3">
                          <span className="text-xs text-[#7a8797]">
                            Safety override
                          </span>

                          <p className="mt-1 text-sm font-semibold text-[#172033]">
                            {recoveryResponse.safety_override
                              ? "Yes"
                              : "No"}
                          </p>
                        </div>

                        <div className="rounded-lg border border-[#e2e7ee] p-3">
                          <span className="text-xs text-[#7a8797]">
                            Audit reference
                          </span>

                          <p className="mt-1 truncate font-mono text-xs text-[#526071]">
                            {recoveryResponse.audit_id ?? "—"}
                          </p>
                        </div>
                      </div>

                      {recoveryResponse.policy_reason && (
                        <div className="mt-4 rounded-lg bg-[#f8fafc] p-4">
                          <p className="text-xs font-semibold text-[#526071]">
                            Policy reason
                          </p>

                          <p className="mt-1.5 text-sm leading-5 text-[#66758a]">
                            {recoveryResponse.policy_reason}
                          </p>
                        </div>
                      )}

                      <div className="mt-4 flex flex-wrap gap-4 border-t border-[#e2e7ee] pt-4">
                        <Link
                          href="/recovery-cases"
                          className="text-xs font-semibold text-blue-600 hover:text-blue-700"
                        >
                          Open recovery cases →
                        </Link>

                        <Link
                          href="/audit-logs"
                          className="text-xs font-semibold text-blue-600 hover:text-blue-700"
                        >
                          View audit log →
                        </Link>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Post-payment reconciliation result */}
              {reconciliationDemo && (
                <div className="rounded-lg border border-violet-200 bg-violet-50 p-5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wide text-violet-700">
                        Post-payment reconciliation
                      </p>

                      <h3 className="mt-2 text-xl font-bold text-[#172033]">
                        Order cancelled after successful payment
                      </h3>

                      <p className="mt-2 text-sm leading-6 text-[#526071]">
                        The payment succeeded, but the shopping
                        platform subsequently cancelled the order.
                        RecoverAI must not retry the payment.
                      </p>
                    </div>

                    <span className="shrink-0 rounded-md border border-violet-200 bg-white px-3 py-1.5 text-xs font-semibold text-violet-700">
                      Refund reconciliation
                    </span>
                  </div>

                  <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-lg border border-[#e2e7ee] bg-white p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                        Payment
                      </p>

                      <p className="mt-2 text-sm font-bold text-emerald-700">
                        Successful
                      </p>
                    </div>

                    <div className="rounded-lg border border-[#e2e7ee] bg-white p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                        Order
                      </p>

                      <p className="mt-2 text-sm font-bold text-red-700">
                        Cancelled
                      </p>
                    </div>

                    <div className="rounded-lg border border-[#e2e7ee] bg-white p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                        Payment retry
                      </p>

                      <p className="mt-2 text-sm font-bold text-red-700">
                        Blocked
                      </p>
                    </div>

                    <div className="rounded-lg border border-[#e2e7ee] bg-white p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
                        Refund
                      </p>

                      <p className="mt-2 text-sm font-bold text-violet-700">
                        Initiation simulated
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 rounded-md border border-violet-200 bg-white p-4">
                    <p className="text-xs font-semibold text-violet-900">
                      Recovery policy
                    </p>

                    <p className="mt-1 text-sm leading-5 text-violet-800">
                      A successful payment is never retried because
                      an order was later cancelled. The correct
                      workflow is refund reconciliation followed by
                      refund tracking.
                    </p>

                    <p className="mt-2 text-xs text-violet-700">
                      Demo status: refund initiation is simulated
                      locally. No real refund is sent by this
                      scenario.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="mt-6 flex items-center justify-between gap-4 border-t border-[#e2e7ee] pt-4">
            <span className="text-xs text-[#7a8797]">
              Payment ID is automatically cached for Recovery Cases.
            </span>

            <Link
              href="/recovery-cases"
              className="shrink-0 text-xs font-semibold text-blue-600 hover:text-blue-700"
            >
              Go to cases →
            </Link>
          </div>
        </section>
      </div>

      {/* Architecture demonstration */}
      <section
        ref={reconciliationRef}
        className="panel p-6"
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="eyebrow">
              Architecture demonstration
            </p>

            <h2 className="mt-2 text-xl font-bold text-[#172033]">
              Successful payment, cancelled order
            </h2>

            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#66758a]">
              This scenario demonstrates the distinction between
              payment recovery and post-payment reconciliation.
              Once a payment has succeeded, it must not be retried
              merely because the shopping platform later cancels
              the order.
            </p>
          </div>

          <span className="shrink-0 rounded-md border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700">
            Reconciliation preview
          </span>
        </div>

        {/* Lifecycle */}
        <div className="mt-6 rounded-lg border border-[#e2e7ee] bg-[#f8fafc] p-5">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
            Lifecycle state progression
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-semibold">
            <span className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-700">
              Payment successful
            </span>

            <span className="text-[#9aa5b5]">→</span>

            <span className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">
              Order cancelled
            </span>

            <span className="text-[#9aa5b5]">→</span>

            <span className="rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-violet-700">
              Refund reconciliation
            </span>

            <span className="text-[#9aa5b5]">→</span>

            <span className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-blue-700">
              Track refund
            </span>
          </div>
        </div>

        {/* Invariants */}
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-[#e2e7ee] p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
              Payment status
            </p>

            <p className="mt-2 text-sm font-bold text-emerald-700">
              Successful
            </p>

            <p className="mt-1 text-xs leading-5 text-[#7a8797]">
              Payment has already completed.
            </p>
          </div>

          <div className="rounded-lg border border-[#e2e7ee] p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
              Order status
            </p>

            <p className="mt-2 text-sm font-bold text-red-700">
              Cancelled
            </p>

            <p className="mt-1 text-xs leading-5 text-[#7a8797]">
              Shopping platform cancelled the order.
            </p>
          </div>

          <div className="rounded-lg border border-[#e2e7ee] p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
              Payment retry
            </p>

            <p className="mt-2 text-sm font-bold text-red-700">
              Blocked
            </p>

            <p className="mt-1 text-xs leading-5 text-[#7a8797]">
              A successful payment must not be retried.
            </p>
          </div>

          <div className="rounded-lg border border-[#e2e7ee] p-4">
            <p className="text-[10px] font-bold uppercase tracking-wide text-[#7a8797]">
              Next action
            </p>

            <p className="mt-2 text-sm font-bold text-violet-700">
              Refund reconciliation
            </p>

            <p className="mt-1 text-xs leading-5 text-[#7a8797]">
              Initiate and track the refund workflow.
            </p>
          </div>
        </div>

        {/* Safety invariant */}
        <div className="mt-5 rounded-lg border border-violet-200 bg-violet-50 p-4">
          <p className="text-sm font-semibold text-violet-900">
            RecoverAI safety policy invariant
          </p>

          <p className="mt-1.5 text-sm leading-6 text-violet-800">
            Payment succeeded, but the order was later cancelled
            by the shopping platform. Automatic payment retry is
            prohibited. Refund reconciliation is required.
          </p>

          <p className="mt-2 text-xs leading-5 text-violet-700">
            This scenario is currently simulated on the frontend
            after a successful payment event. No real refund is
            initiated from this demo.
          </p>
        </div>
      </section>
    </div>
  );
}