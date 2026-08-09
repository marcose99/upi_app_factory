# Incident and Recovery

> **Status:** Canonical current-state documentation<br>
> **Purpose:** Define local failure classes, safe recovery actions, escalation and protected boundaries.<br>
> **Audience:** operators, support engineers, developers, security reviewers and release engineers<br>
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC 20000-1:2018 and SRE practices
- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference
- ISO/IEC/IEEE 26514:2022

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Failure classes

| Class | Example | Safe response | Escalate? |
|---|---|---|---|
| Dependency/environment | exact-lock mismatch, `pip check` failure | rebuild from exact lock route and reverify | if lock/product change required |
| Startup/health | port collision, failed `/health` | inspect logs, choose free/auto port, retry | if persistent implementation defect |
| Documentation contract | broken current link, stale command, checksum drift | bounded doc/evidence reconciliation and rerun | if product semantics would change |
| Generated runtime | child startup/scenario failure | guarded stop/restart, inspect evidence | if code/capability change required |
| Security | secret leakage, unsafe exposure, live escape | stop affected runtime, preserve evidence | yes |
| Governance | branch/main/tag/CI identity mismatch | fail closed; no protected write | yes |

## Recovery principles

1. Preserve the first authoritative failure and evidence.
2. Do not weaken tests, security controls or governance to make a gate green.
3. Prefer deterministic reconstruction from source/locks over manual environment mutation.
4. Keep historical evidence separate from current canonical guidance.
5. Re-run the focused gate and broader qualification after repair.

## Rollback/revert boundary

The public baseline may already have been delivered to `main`. Any rollback or revert is a separately governed Git operation: prefer an additive revert/corrective commit with fresh qualification, and do not use force-push rollback as the default strategy.
