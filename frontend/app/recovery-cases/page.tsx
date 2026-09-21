"use client";

import { useEffect, useState } from "react";

import { PageHeading } from "@/components/page-heading";
import { processRecovery } from "@/lib/api";
import type { RecoveryWorkflowResponse } from "@/types/api";

function Detail({ label, value }: { label: string; value: string | number | boolean | null }) { return <div className="border-b border-white/10 py-3 last:border-0"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-slate-300">{value === null ? "—" : String(value)}</dd></div>; }

export default function RecoveryCasesPage() {
  const [paymentId, setPaymentId] = useState("");
  const [response, setResponse] = useState<RecoveryWorkflowResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const lastPaymentId = window.localStorage.getItem("recoverai:last-payment-id");
    if (lastPaymentId) setPaymentId(lastPaymentId);
  }, []);

  async function submit() { setLoading(true); setError(""); setResponse(null); try { setResponse(await processRecovery(paymentId.trim())); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Unable to process recovery."); } finally { setLoading(false); } }

  return <div className="mx-auto max-w-7xl"><PageHeading eyebrow="Workflow / policy-controlled" title="Recovery cases" description="Pass a failed payment through classification, prediction, recommendation, safety policy, and simulated execution." /><div className="grid gap-6 xl:grid-cols-[0.65fr_1.35fr]"><section className="panel h-fit p-6"><p className="eyebrow">Start a case</p><h2 className="mt-2 font-display text-2xl font-semibold text-white">Payment ID</h2><p className="mt-3 text-sm leading-6 text-slate-400">Use the ID returned by the Payment Simulator.</p><input className="field-control mt-6 font-mono text-xs" placeholder="e.g. 2f7…" value={paymentId} onChange={(event) => setPaymentId(event.target.value)} /><button className="primary-button mt-4 w-full" disabled={loading || !paymentId.trim()} onClick={submit}>{loading ? "Running workflow…" : "Run recovery workflow"}</button>{error && <div className="error-box mt-5 p-4 text-sm">{error}</div>}<div className="mt-8 border-t border-white/10 pt-5 text-xs leading-5 text-slate-500">The workflow is simulation-only. No live retry, refund, or payment action is sent.</div></section><section className="panel min-h-[430px] p-6"><p className="eyebrow">Case outcome</p><h2 className="mt-2 font-display text-2xl font-semibold text-white">Decision trace</h2>{!response && !error && <div className="mt-8 grid min-h-64 place-items-center rounded-xl border border-dashed border-white/10 text-center text-sm text-slate-500">Run a case to inspect the complete decision trace.</div>}{response && <><div className="mt-6 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-cyan-300/10 p-4"><p className="text-xs text-cyan-200/80">Final action</p><p className="mt-2 font-display text-xl text-cyan-200">{response.final_policy_action ?? "Skipped"}</p></div><div className="rounded-xl bg-orange-300/10 p-4"><p className="text-xs text-orange-100/70">Probability</p><p className="mt-2 font-display text-xl text-orange-100">{response.recovery_probability === null ? "—" : `${Math.round(response.recovery_probability * 100)}%`}</p></div><div className="rounded-xl bg-emerald-300/10 p-4"><p className="text-xs text-emerald-100/70">Execution</p><p className="mt-2 font-display text-xl text-emerald-100">{response.execution_status}</p></div></div><dl className="mt-6 grid gap-x-8 sm:grid-cols-2"><Detail label="Failure category" value={response.failure_category} /><Detail label="AI recommendation" value={response.ai_recommended_action} /><Detail label="Retry allowed" value={response.retry_allowed ? "Yes" : "No"} /><Detail label="Safety override" value={response.safety_override ? "Yes" : "No"} /><Detail label="Payment ID" value={response.payment_id} /><Detail label="Audit reference" value={response.audit_id} /></dl><div className="mt-6 rounded-xl border border-white/10 bg-black/10 p-4"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">Explanation</p><p className="mt-2 text-sm leading-6 text-slate-300">{response.explanation}</p><p className="mt-3 break-words text-sm leading-6 text-slate-400">{response.policy_reason}</p></div></>}</section></div></div>;
}
