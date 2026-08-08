# Recipient Operator Runbook

> **Status:** Canonical current-state documentation
> **Purpose:** Provide the current recipient startup, health, evidence and escalation workflow.
> **Audience:** recipients and local operators
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC 20000-1:2018 and SRE practices
- ISO/IEC/IEEE 26514:2022

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Start

```bash
./run_factory.sh
```

or:

```bash
./run_factory.sh --no-browser
```

## Verify

1. Use the launcher-reported URL only after health succeeds.
2. Open `/operator-ui/`.
3. Use local health/evidence/validation/runtime surfaces.
4. Preserve state-root logs/evidence for failures.

## Docker alternative

```bash
docker compose up --build
# later
docker compose down
```

## Escalate

Escalate any request/failure involving real customer data, live payment rails, live LLM/provider enablement, new dependencies/capabilities, security-control weakening, test/governance weakening or protected Git/release actions outside the current authorization.

See [Operating Model](../operations/OPERATING_MODEL.md) and [Incident and Recovery](../operations/INCIDENT_AND_RECOVERY.md).
