# High Availability, Failover, and Failback Design Policy — upi_dispute_resolution

Labels: HA_FAILOVER_FAILBACK_DESIGN_REQUIRED, REALISTIC_MOCK_REQUIRED,
MOCK_BOUNDARY

Architecture and design artifacts must include:

- active-active and active-passive deployment considerations
- stateless service boundary where practical
- durable state boundary
- idempotent retry behavior
- checkpoint and replay behavior
- failover simulation tests
- failback simulation tests
- partial dependency outage behavior
- degraded-mode behavior
- duplicate event protection
- recovery runbooks
- data consistency notes

Local implementation may simulate these with mock services, temporary state,
synthetic events, and deterministic fault-injection tests.
