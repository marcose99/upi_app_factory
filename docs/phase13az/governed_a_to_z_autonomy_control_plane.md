# Phase 13AZ — Governed A-to-Z Autonomy Control Plane

## Purpose

Phase 13AZ initiates full A-to-Z autonomy as a governed control plane.

This phase does not introduce unrestricted autonomy. It introduces policy-backed autonomy decisions for the complete lifecycle.

## Autonomy target

```text
A-to-Z lifecycle execution under policy gates, evidence capture, sandbox-first execution, rollback requirements, human approval boundaries, and release gates.
```

## Autonomy levels

```text
LEVEL_0_MANUAL
LEVEL_1_GUIDED
LEVEL_2_READ_ONLY_VALIDATION
LEVEL_3_SANDBOX_AUTONOMOUS
LEVEL_4_HUMAN_GATED_WORKTREE_AUTONOMOUS
LEVEL_5_RELEASE_GATED_AUTONOMOUS
LEVEL_6_ENTERPRISE_AUTONOMOUS_REFERENCE
```

## Phase 13AZ safety boundary

Phase 13AZ is control-plane-only.

Phase 13AZ does not execute arbitrary shell commands.

Phase 13AZ does not delete the real generated application.

Phase 13AZ does not overwrite the real generated application.

Phase 13AZ does not mutate the real worktree.

Phase 13AZ does not run application engineering.

Phase 13AZ does not call live providers.

Phase 13AZ does not call external systems.

Phase 13AZ does not apply factory self-modifications.

Phase 13AZ does not merge, tag, or release automatically.

## What the control plane decides

```text
APPROVED
BLOCKED
HUMAN_APPROVAL_REQUIRED
SANDBOX_EVIDENCE_REQUIRED
POLICY_EVIDENCE_REQUIRED
```

## Covered lifecycle activities

```text
requirement_intake
domain_analysis
architecture_design
planning
prompt_pack_generation
sandbox_generation
sandbox_validation
security_validation
governance_validation
self_healing
evidence_packaging
handover_replay
worktree_promotion
release_candidate_preparation
merge_tag_release
```

## Governance improvement introduced

Phase 13AY made evidence and governance state visible through local dashboards. Phase 13AZ now formalizes the A-to-Z autonomy decision layer so later phases can safely execute lifecycle activities under strict policy, evidence, sandbox, rollback, and human-approval gates.
