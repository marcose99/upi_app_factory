# Governance, Audit and Self-Correction Guide

> **Status:** Canonical current-state documentation
> **Purpose:** Explain bounded autonomous repair and protected escalation.
> **Audience:** operators, reviewers and maintainers
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 15289:2019
- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


Bounded self-correction may repair deterministic harness/documentation/evidence defects inside an explicitly authorized boundary. It must not add product capabilities/dependencies, weaken security/tests/governance, enable live payment/LLM/provider behavior, force-push, merge, tag, release, deploy or claim certification without the relevant protected authorization.

Every repair cycle must re-run the affected gate and broader qualification; repeated or semantic failures escalate.

## Legacy Phase 13C compatibility contract

**Every warning and error** must be triaged rather than hidden merely to obtain a green result. **Human approval required** remains the rule whenever a repair crosses a protected action or changes semantics. A **Blocked** result is correct when the requested fix lies outside the current authorization.
