# Ecosystem Mock Application Policy — upi_dispute_resolution

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED,
HIGH_VOLUME_ENGINEERING_REQUIRED, MOCK_BOUNDARY, SYNTHETIC_DATA

The factory must generate ecosystem mock applications or adapters where needed
to simulate realistic upstream and downstream behavior.

Required mock ecosystem categories:

- transaction source simulator
- bank/issuer/acquirer response simulator
- NPCI-like response simulator
- merchant response simulator
- ledger/accounting simulator
- evidence document simulator
- notification simulator
- ODR or case workflow simulator
- operations incident simulator
- SLA and escalation simulator

Each mock must support deterministic scenarios, high-volume synthetic data,
fault injection, latency injection, timeout simulation, and replay.
