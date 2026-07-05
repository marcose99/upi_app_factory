# Low-Level Design — Phase 10 Planning Pipeline

## Python module

`src/upi_factory/phase10_lifecycle_planner.py`

## Public functions

### generate_lifecycle_artifacts(output_dir: Path, app_id: str) -> list[Path]

Creates all required Phase 10 lifecycle artifacts in deterministic order.

### validate_lifecycle_artifacts(output_dir: Path) -> dict[str, Any]

Validates required files, JSON structure, traceability, architecture content,
and honesty labels.

## Artifact contracts

### requirements_analysis.json

Required keys:

- artifact
- app_id
- phase
- safety_boundary
- official_reference_candidates
- requirements
- economics_guidance
- required_honesty_labels

Each requirement needs:

- id
- title
- type
- priority
- description
- acceptance_criteria
- honesty_labels

### work_breakdown_structure.json

Each task needs:

- id
- sequence
- title
- requirement_ids
- design_refs
- validation_refs
- relative_effort_points
- relative_risk_points
- economics_notes
- done_when

### traceability_matrix.json

Each row needs:

- requirement_id
- requirement_title
- design_artifacts
- wbs_task_ids
- validation_refs
- economics_refs
- honesty_labels

### planning_validation_report.json

Required keys:

- passed
- errors
- warnings
- checked_artifacts
- checked_honesty_labels
- checked_traceability

## Failure modes and handling

| Failure mode | Handling |
|---|---|
| Missing artifact | Validator returns passed=false and lists file |
| Broken JSON | Validator returns exact JSON parse error |
| Requirement without task | Validator fails traceability |
| Missing honesty label | Validator fails content check |
| Architecture options missing pros/cons | Validator fails design completeness |
| Selected architecture absent | Validator fails ADR completeness |
| Official source missing | Do not guess; use MISSING_OFFICIAL_SOURCE |

## Debug guide

1. Run `python scripts/generate_phase10_lifecycle_artifacts.py`.
2. Run `python scripts/validate_phase10_lifecycle_artifacts.py`.
3. If validation fails, open `planning_validation_report.json`.
4. Fix the named artifact.
5. Re-run validator before committing.

## Economics implementation detail

The current implementation stores economic reasoning as structured text and
relative planning points. It does not compute real ROI, regulatory penalties,
bank fees, NPCI charges, model prices, or support costs. Those require
official or user-provided data.

## Security and privacy detail

The planner uses only local files and synthetic content. No live credentials,
payment identifiers, customer PII, or external API calls are required.

Honesty labels: MISSING_OFFICIAL_SOURCE,
SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA.
