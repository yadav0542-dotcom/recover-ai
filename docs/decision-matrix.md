# Planned decision matrix

This document records future decision categories only. No classifier, policy,
or automated financial action exists in the foundation stage.

| Category | Planned handling direction |
| --- | --- |
| Temporary payment failure | Consider controlled retry after deterministic checks. |
| UPI timeout | Assess status before any resume or retry path. |
| Insufficient funds | Do not blindly retry; consider alternate customer path. |
| Incorrect CVV | Prompt for corrected details; no automatic recovery. |
| Incorrect UPI details | Prompt for corrected details; no automatic recovery. |
| Expired card | Offer a safe alternate payment method. |
| Bank restriction | Delay or offer an alternate method after validation. |
| Customer cancellation | Respect cancellation; do not retry automatically. |
| High-risk/fraud block | Block automatic retry and escalate safely. |
| Business/configuration failure | Escalate for merchant or configuration review. |
| Payment timeout/session expiry | Reconcile status before offering checkout resume. |
| Payment successful + order cancelled | Block retry; reconcile payment and order. |
| Payment successful + order status unknown | Block retry; reconcile before any action. |
| Refund pending | Track and communicate pending state. |
| Refund exception | Escalate for safe resolution. |

## Safety rule

If a payment succeeded but its order is cancelled or unresolved, automatic
payment retry must be blocked until reconciliation is complete.
