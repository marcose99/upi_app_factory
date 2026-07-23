# Factory Handover Guide

This guide explains how a recipient should take over the UPI App Factory
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
cd upi_app_factory
git checkout <validated-release-tag>

./run_factory.sh --no-browser
```

Open the verified `/operator-ui/` URL printed by the command. The default path
is deterministic, mock-safe, stores runtime state under `.var/upi_app_factory`,
and requires no OpenAI API key. The former `./factory ...` quick path is only a
future CLI concept; this repository must not create a root file named `factory`
because `factory/` is already the Python package directory.
