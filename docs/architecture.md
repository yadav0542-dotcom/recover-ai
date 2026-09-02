# RecoverAI planned architecture

The foundation currently implements only the Next.js dashboard shell, FastAPI
health endpoint, and PostgreSQL connection/migration configuration.

```text
Customer
  ↓
Checkout                         [planned]
  ↓
Razorpay                         [planned]
  ↓
Payment / Event                  [planned]
  ↓
Failure Classifier               [planned]
  ↓
Recovery Prediction              [planned]
  ↓
AI Recovery Agent                [planned]
  ↓
Policy Engine                    [planned]
  ↓
Retry / Wait / Alternate / Refund / Escalate  [planned]
  ↓
Action Executor                  [planned]
  ↓
Audit + Metrics                  [planned]
  ↓
Merchant Dashboard               [shell only]
```

The intended runtime path is `Next.js frontend → FastAPI backend → PostgreSQL`.
When later stages add recommendations, deterministic policy must authorize all
financial actions; an LLM must never execute those actions directly.
