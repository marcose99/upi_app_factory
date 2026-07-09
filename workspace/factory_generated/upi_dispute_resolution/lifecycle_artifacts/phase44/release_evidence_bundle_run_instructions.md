# Phase 44 release evidence bundle run instructions

From the repository root, review the bundle in this order:

1. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_index.json`
2. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_manifest.json`
3. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_policy_summary.json`
4. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_validation_summary.json`
5. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_boundary_statement.md`
6. `workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase44/release_evidence_bundle_supply_chain.json`

Minimum local validation:

```bash
python scripts/validate_phase44_release_evidence_bundle.py
python -m pytest tests/test_phase44_release_evidence_bundle.py
```

The wider release review should also run the inherited Phase 28 through Phase 34
and Phase 43 validators and tests listed in the validation summary.

This bundle is local evidence only. It does not start live integrations, create
real secrets, deploy, merge, tag, push, or claim official certification.
