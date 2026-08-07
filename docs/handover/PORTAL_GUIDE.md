# Operator Portal Guide

Start the governed local portal with:

```bash
./run_factory.sh
```

The operator workflow is: validate fictional requirements -> create governed run -> inspect plan -> explicitly approve application engineering -> execute -> inspect generated source/tests/OpenAPI/evidence -> select `app_id`/`version_id` -> approve runtime start -> inspect health/scenarios/logs/metrics -> download handover -> approve stop.

Reviewers should verify identities, approvals, generated-test execution evidence, OpenAPI, runtime health, mock boundaries, logs/metrics/evidence, blocked findings, downloadable artifacts, Charts and visuals, and audit/self-correction evidence where those portal surfaces are available.

The downloaded authoritative generated application is independently reproducible. See [Generated Application Handover](GENERATED_APPLICATION_HANDOVER.md).

The default workflow does not authorize real payment calls, real customer data, production deployment, certification claims or default live provider access.
