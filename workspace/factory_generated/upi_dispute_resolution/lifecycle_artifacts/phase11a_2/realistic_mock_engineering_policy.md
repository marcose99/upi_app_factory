# Realistic Mock Engineering Policy — upi_dispute_resolution

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED, MOCK_BOUNDARY,
SYNTHETIC_DATA, STRONG_GUARDRAILS_REQUIRED

The generated system must simulate realistic enterprise payment-dispute behavior
without connecting to live external systems.

Required realistic mock capabilities:

- bank and PSP response simulators
- NPCI-like switch response simulator
- ledger event simulator
- merchant/acquirer response simulator
- customer notification simulator
- ODR/case-management simulator
- synthetic dispute, transaction, evidence, and SLA datasets
- deterministic positive, negative, timeout, duplicate, replay, and partial
  failure scenarios
- clear mock-boundary documentation for every dependency

Forbidden:

- live bank calls
- live NPCI calls
- live PSP calls
- live customer data
- live account data
- certification or compliance claims
