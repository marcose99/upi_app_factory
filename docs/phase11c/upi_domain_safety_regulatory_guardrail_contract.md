# Phase 11C UPI Domain Safety and Regulatory Guardrail Contract

Boundary: real locally runnable primary UPI/payment application with mock/simulated external ecosystem.

Run-log timestamp policy: scripts created from this point use Asia/Kolkata local timestamp with an `IST` suffix.

Required reference-awareness areas:
- RBI, NPCI, UPI procedural requirements, ODR, failed transaction TAT, customer compensation, unauthorised electronic banking transaction handling, RB-IOS, and DPDP/privacy.

Prohibited claims:
- do not claim regulatory compliance, RBI certification, NPCI certification, regulator approval, bank approval, production compliance, full compliance, legal completeness, or live payment capability.

Prohibited data/connectivity:
- no real customer UPI ID, real customer bank account, real PII, production secrets, or live NPCI/RBI/bank/PSP/ODR/payment-rail calls.

Required evidence:
- requirement traceability, policy/source category mapping, unit tests, integration tests, scenario coverage, security review evidence, audit evidence, and release-readiness evidence.
