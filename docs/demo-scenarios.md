# Planned demo scenarios

These demonstrations are planned for later stages and are not implemented in
the foundation stage.

## Scenario 1 — Bank outage

Payment fails → bank is down → RecoverAI waits → bank becomes healthy → Resume
Payment → payment succeeds → recovered revenue recorded.

## Scenario 2 — High-risk payment

Payment receives risk/fraud block → AI may recommend an action → policy engine
blocks automatic retry → customer is safely informed → audit log records the
decision.

## Scenario 3 — Payment successful but order cancelled

Payment succeeds → order is cancelled → RecoverAI detects payment/order
mismatch → retry is blocked → refund/reconciliation workflow is created →
customer is informed.
