# Security Policy

UPI App Factory is a local-first, mock-safe engineering project. It is not a production payment system and must not be tested with real customer data, payment credentials, bank/PSP/NPCI secrets or production provider access.

## Reporting a vulnerability

Please avoid publishing exploit details, secrets or sensitive reproduction data in a public issue.

- If GitHub offers **Report a vulnerability** for this repository, use that private reporting route.
- If private vulnerability reporting is unavailable, open a minimal public issue stating that you have a security concern and need a private contact path. Do not include exploit details or secrets.

Include, when safe:
- affected revision;
- affected component/path;
- impact;
- minimal non-sensitive reproduction steps;
- whether the issue could expose secrets, escape loopback/mock boundaries, bypass approval, weaken provenance, or enable live provider/payment behavior.

## Supported security posture

The accepted public route is local/mock only. Real payment calls and live LLM/provider execution are disabled or separately gated. Production IAM, internet-facing hardening, regulatory certification and live payment integration are not claimed.

See `docs/security/SECURITY_ARCHITECTURE_AND_THREAT_MODEL.md`.
