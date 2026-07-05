# Phase 10.1 Source Usage Policy — upi_dispute_resolution

## Allowed

The factory may use official source references to:

- shape mock requirements
- improve architecture prompts
- improve dispute-domain vocabulary
- identify source-backed design concerns
- identify economics source gaps
- create traceability from source to requirement
- prevent hallucinated regulatory or monetary claims

## Not allowed

The factory must not use source references to claim:

- RBI certification
- NPCI certification
- official regulatory compliance
- production readiness
- legal advice
- real UPI integration
- real bank integration
- real customer-dispute processing
- exact ROI without measured or user-provided data
- live UPI statistics without capture date

## Economics usage

Economic statements must be classified as one of:

- SOURCE_BACKED_REFERENCE
- USER_PROVIDED_VALUE
- SYNTHETIC_DATA
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- MISSING_OFFICIAL_SOURCE

If none applies, the statement is not allowed.

## Prompting rule

Future agents must prefer this sequence:

1. Use deterministic source-backed fact when available.
2. Use USER_PROVIDED_VALUE when supplied and labelled.
3. Use SYNTHETIC_DATA only for demos.
4. Use MISSING_OFFICIAL_SOURCE rather than guessing.
5. Escalate to human review when the consequence is regulatory, financial,
   customer-impacting, or production-like.
