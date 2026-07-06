# Factory Handover Guide

This guide explains how a recipient should take over the FactoryFromNothing
UPI dispute-resolution factory, run it on their own machine, regenerate the
generated application, validate the result, and inspect the evidence portals.

## What is handed over

The repository contains:
- governed factory prompts, policies, validators, and runtime scaffolding
- a resettable generated-application workspace
- local generated UPI dispute-resolution application artifacts
- mock/simulated external ecosystem adapters
- audit, self-correction, and progress portals
- run logs and evidence ledgers

## Truth boundary

Primary generated application:
- real locally runnable UPI/payment dispute-resolution application

External ecosystem:
- strictly mock/simulated only

Not claimed:
- production readiness
- RBI approval
- NPCI certification
- regulatory compliance certification
- live UPI/payment rail integration
- real customer data handling

## Recipient quick path

```bash
git clone <repo-url>
cd upi_dispute_resolution_factory
git checkout <validated-release-tag>

./factory doctor
./factory bootstrap
./factory generate
./factory validate
./factory portal
```

Until the unified `./factory` CLI is implemented, use the phase scripts listed in
`COMMAND_REFERENCE.md`.
