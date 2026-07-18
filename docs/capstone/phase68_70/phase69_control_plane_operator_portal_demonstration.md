# Phase 69 Control-Plane Operator Portal Demonstration

Phase 69 makes the repository-owned control plane the source of truth for the consolidated capstone portal. The portal reads the Phase 68 recipient replay, Phase 70 multi-domain portfolio validation, control-plane campaign events, policy decisions, activity results, checkpoints, incidents, repair-budget state and sealed evidence.

The local demonstration path is:

1. Requirements intake is represented by `factory_governance/phase68_70/recipient_fixture/requirements_intake.json`.
2. The control-plane manifest `config/control_plane/campaigns/phase68_70_consolidated_capstone.json` runs the governed local campaign.
3. Phase 68 produces and verifies the recipient handoff bundle in `factory_governance/phase68_70/recipient_replay_output/`.
4. Phase 70 validates the fictional multi-domain generated-application portfolio.
5. Phase 69 assembles portal status from durable control-plane state and evidence hashes.

The portal exposes safe source and evidence browsing only for bounded capstone and portal roots. OpenAPI discovery remains available through `/openapi.json`, including the Phase 69 routes under `/operator-portal/api/capstone/phase69/`.

Boundaries remain unchanged: fictional data only, local deterministic execution, no external integrations, no live payment calls, no release/deploy actions and no official certification claim.
