# Phase 45 final local demo instructions

Run from the repository root with the project virtual environment activated.

```bash
python scripts/validate_phase45_final_v1_candidate_consolidation.py
python -m pytest tests/test_phase45_final_v1_candidate_consolidation.py
python scripts/validate_phase43_one_command_demo_reviewer_pack.py
python scripts/validate_phase44_release_evidence_bundle.py
```

For generated application local checks, use the committed local run-pack scripts
under `workspace/factory_generated/upi_dispute_resolution/generated_application/`.

This demo is local only. It does not call live providers, create real secrets,
deploy, merge, create release labels, push, or enable live payment rails.
External ecosystem integrations remain mocked or simulated.
