# Clean-clone test evidence

This directory contains deterministic, tracked fixtures needed to exercise
historical lifecycle validators from a clean Git checkout.

Eight audited historical command entries contained a retired local virtual
environment path. Only those command executable entries were normalized to
the portable token `python`. No policy decision, governance boundary,
certification posture or business result was changed.

The fixtures are local test and validation inputs only. They do not represent
official certification, production deployment, live-provider integration or
external attestation.

Materialization is performed by:

```text
scripts/bootstrap_clean_clone_test_evidence.py
```

The bootstrap verifies every fixture against the SHA-256 manifest and fails
closed rather than replacing conflicting destination content.
