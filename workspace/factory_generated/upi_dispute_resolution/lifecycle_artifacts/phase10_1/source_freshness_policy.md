# Phase 10.1 Source Freshness Policy — upi_dispute_resolution

## Purpose

Prevent stale or unsupported regulatory and economics claims from entering
future prompts, generated artifacts, or demo narratives.

## Freshness classes

| Class | Meaning | Required action |
|---|---|---|
| stable_circular_verify_before_release | Official circular-like reference that changes slowly | Re-check before release/demo/capstone submission |
| dynamic_verify_before_demo_or_release | Official dynamic page | Capture source date before use |
| dynamic_verify_on_every_release | Dynamic values such as product statistics | Re-capture every release if used |
| user_provided_value | Value supplied by the user | Record date, owner, and assumption |
| synthetic_demo_value | Demo-only value | Mark SYNTHETIC_DATA and never present as real |

## Rules

1. Dynamic values cannot be embedded without a capture date.
2. Real ROI cannot be claimed without measured or user-provided values.
3. Real bank cost cannot be claimed without user-provided internal data.
4. Official source titles and URLs may be stored as references.
5. Any current operational rule must be reviewed before production-like claims.
6. MISSING_OFFICIAL_SOURCE is the correct label when evidence is absent.
7. No artifact may claim RBI/NPCI certification or production compliance.

## Release gate

Before any future release that uses a source-backed claim:

- verify the source URL is still accessible
- verify title and publication date
- verify no known supersession has been introduced
- update gap report if the claim is unsupported
- keep all live integrations under MOCK_BOUNDARY
