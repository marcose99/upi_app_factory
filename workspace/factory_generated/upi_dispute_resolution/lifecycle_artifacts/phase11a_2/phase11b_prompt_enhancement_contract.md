# Phase 11B Prompt Enhancement Contract — upi_dispute_resolution

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED,
HIGH_VOLUME_ENGINEERING_REQUIRED, ASYNC_CONCURRENCY_REQUIRED,
PRODUCTION_QUALITY_OBSERVABILITY_REQUIRED, HA_FAILOVER_FAILBACK_DESIGN_REQUIRED,
LOCAL_FIRST_LIGHTWEIGHT_RUNTIME, PRODUCTION_MIGRATION_READY,
STRONG_GUARDRAILS_REQUIRED

Phase 11B prompts must require each agent to produce outputs that satisfy:

1. realistic mock behavior with explicit MOCK_BOUNDARY labels
2. high-volume local data handling design
3. async, concurrency, and parallelism where realistic
4. bounded resource usage
5. HA, failover, failback, degraded-mode, and recovery design
6. production-quality observability design
7. locally runnable lightweight defaults
8. migration seams to production infrastructure
9. deterministic validation and test evidence
10. human approval gates for protected writes

Any generated output that weakens the mock boundary, removes guardrails, or
claims certification/compliance must fail validation.
