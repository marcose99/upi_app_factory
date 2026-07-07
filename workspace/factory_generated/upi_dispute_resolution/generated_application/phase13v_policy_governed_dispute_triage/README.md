# Phase 13V Policy-Governed Dispute Triage

This generated capability demonstrates policy-governed self-repair.

The first generated service draft intentionally misses the regulatory-complaint
escalation rule. The LangGraph runner validates the generated behavior,
diagnoses the mismatch, checks the repair against the policy file, applies a
bounded repair only to generated application files, reruns validation, and writes
audit evidence.

No OpenAI API key is required for this phase. The diagnosis and repair are
deterministic and local. Future LLM-backed diagnosis can be enabled only through
explicit provider configuration and secret injection outside the repository.
