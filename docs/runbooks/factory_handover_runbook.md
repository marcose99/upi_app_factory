# Factory Handover Runbook

## Objective

Transfer the factory to another person so they can run it, regenerate the app,
validate it, and inspect evidence.

## Steps

1. Confirm latest stable tag.
2. Confirm all validators pass.
3. Confirm portals are generated.
4. Confirm no untriaged self-correction findings.
5. Create handover package.
6. Provide recipient quickstart.
7. Recipient runs doctor/bootstrap/generate/validate/portal.
8. Recipient confirms generated app and evidence portals.

## Exit criteria

- recipient can regenerate generated_application
- recipient can run generated app tests
- recipient can run factory validators
- recipient can open portals
- recipient understands mock/live boundary
