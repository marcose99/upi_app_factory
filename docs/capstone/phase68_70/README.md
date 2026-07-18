# Phase 68-70 Consolidated Capstone

This capstone integrates the completed Phase 68 recipient replay, Phase 69 control-plane portal demonstration, and Phase 70 multi-domain application-engineering portfolio into one repository-native offline flow for UPI App Factory.

## Architecture

The capstone entry point is `bin/upi-app-factory-capstone`, which calls `scripts/run_phase68_70_consolidated_capstone.py` and the reusable module `src/upi_factory/capstone/consolidated.py`. The runner uses the committed control-plane campaign manifest at `config/control_plane/campaigns/phase68_70_consolidated_capstone.json` as the campaign source of truth, then executes each phase in an isolated runtime root.

Phase 68 copies fictional recipient fixtures into a replay payload, writes a content manifest, creates a zip handoff bundle, and verifies exact payload hashes. Phase 69 runs the repository control plane in a local state root and renders portal status from control-plane events, policy decisions, activities, incidents and evidence records. Phase 70 validates six deterministic application profiles across UPI and card-dispute domains and composes temporary reference applications under the runtime root.

## Operator Flow

Run the full local demonstration:

```bash
bin/upi-app-factory-capstone --runtime-root /tmp/upi-phase68-70-capstone
```

The command writes `events.json`, `evidence_integrity.json`, phase runtime evidence, and `final_summary.json` under the chosen runtime root. The summary states the certification-ready-not-certified posture, zero runtime LLM calls, disabled live integrations, evidence checksums, and residual risk boundaries.

## Evaluator Flow

Run the consolidated validator after the demonstration:

```bash
python3 scripts/validate_phase68_70_consolidated_capstone.py --runtime-root /tmp/upi-phase68-70-capstone
```

The validator checks the three phase contracts, control-plane linkage, no ignored-workspace dependency for recipient replay, control-plane-derived portal progress, multi-domain depth, mock boundaries, absence of production or certification claims, and exact evidence integrity.

## Trust Boundaries

All payment, bank, PSP, NPCI, RBI and card-network behavior is mocked or simulated with fictional data. Normal runtime LLM calls remain zero. Archives, downloads and generated files are written only through traversal-safe and symlink-safe path checks. Recipient replay uses committed fixtures and does not require ignored `workspace/` content.

## Human Accountability

The manifest explicitly protects production deployment, public release, real payment rail access, real customer data access, certification claims and live runtime LLM use. Any such action remains outside this capstone and requires human accountability outside the automated local demo.

## Residual Risks

The portfolio is representative rather than exhaustive. Mock timing, rail responses, acquirer evidence, card-network reason codes, fraud signals and reconciliation outputs do not prove live ecosystem readiness. The capstone does not claim official certification, regulatory approval, live integration approval, or production readiness.
