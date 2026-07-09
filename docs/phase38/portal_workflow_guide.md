# Phase 38 Portal Workflow Guide

This guide describes the local operator portal panels and how to interpret their messages.

## Health

Health confirms the local FastAPI process is responding. `ok` means the process answered the request. It does not mean official certification or live payment capability.

## Evidence Dashboard

Evidence Dashboard reads local lifecycle artifacts and phase coverage. Use it to confirm the posture remains `certification_ready_not_certified`.

## Download Center

Download Center reads local export metadata and can trigger the governed local export path. It must not create deployment artifacts or publish anything outside the workspace.

## Validation

Dry run lists approved validation command IDs without execution. Run executes only allowlisted command IDs. The standard local self-check is `phase34_runner_self_check`.

## Operator Guides

Operator Guides lists the local guide files and the status taxonomy. If a guide is missing, run the Phase 38 validator and inspect the lifecycle artifact manifest.

## Latest Validation Report

Latest report loads the most recent local validation report. If it is missing, run dry-run first and then the safe self-check. If it is malformed, re-run the local validation runner and inspect the local report file.

## Boundary Messages

Every panel should preserve these boundaries:

- local-only operation;
- `certification_ready_not_certified`;
- no official certification claim;
- no broad readiness claim beyond local operator workflows;
- no live provider calls;
- no real credentials;
- no deployment, merge, tag, or push;
- external ecosystem integrations are mocked or simulated.
