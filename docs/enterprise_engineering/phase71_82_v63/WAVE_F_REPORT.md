# Wave F Report

Date: 2026-07-26

Campaign: `phase71-82-enterprise-engineering-v63-corrected`

Baseline: `5373b9bdd04ccd7760e65345d311362c5bc9a48f`

## Scope Completed

Wave F implemented confirmed lightweight enterprise control-plane gaps through
the deterministic generated-application template and the existing local
operator portfolio surface.

Implemented:

- Typed `ALLOW`/`DENY` policy decisions with deterministic decision hashes and
  fail-closed denial paths.
- Generated approval scope binding with nonce, expiry and replay rejection.
- Generated policy engine now consumes accepted approval nonces and returns the
  consumed nonce as the persistence/update contract for surrounding stores.
- Portal portfolio approval grants now persist `expires_at_utc` and fail closed
  when missing, invalid, expired, consumed or scope-digest tampered.
- Generated `AgentContract` schemas with bounded loops, least-privilege local
  actions and independent verification requirements.
- Explicit generated denials for silent prompt, model, policy and test
  self-modification.
- Explicit generated denials for merge, push, release, deployment,
  certification claims and destructive actions.
- Generated isolation binding for application, version, process, loopback port,
  state root and evidence root.
- Recommendation-only generated portfolio assessment evidence.

Fresh generated evidence:

- Command: `python scripts/validate_phase71_82_wave_f_control_plane.py`
- Fresh run ids:
  - `phase71_82_wave_f_control_plane_a`
  - `phase71_82_wave_f_control_plane_b`
- Generated file count: 78
- New generated files:
  - `generated_application/app/control_plane/policy.py`
  - `generated_application/app/tests/security/test_control_plane_policy.py`
  - `generated_application/evidence/assurance/control_plane_governance.json`

## Validation

Passed:

- `PYTHONDONTWRITEBYTECODE=1 python scripts/validate_phase71_82_wave_f_control_plane.py`
- `PYTHONDONTWRITEBYTECODE=1 python scripts/validate_phase71_82_wave_e_assurance_supply_chain.py`
- `PYTHONDONTWRITEBYTECODE=1 python scripts/validate_phase71_82_wave_b_generated_output.py`
- `PYTHONPYCACHEPREFIX=/tmp/upi_app_factory_wave_f_pycache python -m compileall -q factory/application_engineering/portfolio.py factory/templates/mock_dispute_app/generated_application/app/control_plane/policy.py factory/templates/mock_dispute_app/generated_application/app/tests/security/test_control_plane_policy.py scripts/validate_phase71_82_wave_f_control_plane.py tests/test_phase71_82_wave_f_control_plane.py`
- Direct Python smoke for portfolio approval expiry and replay rejection.
- Direct Python smoke for portfolio approval scope-digest tamper rejection.

Current canonical-venv validation:

- `PYTHONDONTWRITEBYTECODE=1 /home/marcose/projects/upi_app_factory/.venv/bin/python scripts/validate_phase71_82_wave_f_control_plane.py` passed with two-build 78-file comparison and policy-engine same-nonce replay rejection.
- V73 repair validation: `PYTHONDONTWRITEBYTECODE=1 <canonical-venv>/bin/python scripts/validate_phase71_82_wave_f_control_plane.py` passed after runtime and portfolio approval-token lookup was changed to fail closed when the approval-token environment variable is absent. Deterministic approval-token constants are now test fixtures only through explicit pytest environment setup.

The Wave F validator redirects Python bytecode cache to a temporary directory,
runs two fresh temporary generations, compares generated template-file hashes
and sizes, imports the fresh generated control-plane policy, and proves scoped
unexpired approval acceptance plus consumed-nonce replay, expired approval,
human-gated action, self-modification action and state/evidence root collision
denials.

## Boundary

No live bank, PSP, NPCI, RBI, payment rail, identity-provider, OpenAI
application, deployment, Kubernetes control plane, tenant billing or shared SaaS
tenancy integration was introduced. No merge, push, release, deployment,
certification, regulatory approval or production-readiness claim is made.
