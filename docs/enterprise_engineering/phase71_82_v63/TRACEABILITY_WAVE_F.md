# Wave F Traceability

| Gap | Implementation Evidence | Test/Evidence |
| --- | --- | --- |
| `GAP-CONTROL-PLANE-POLICY` | `factory/templates/mock_dispute_app/generated_application/app/control_plane/policy.py`, `factory/generators/mock_dispute_app_generator.py` manifest `control_plane_policy` | `scripts/validate_phase71_82_wave_f_control_plane.py`, `factory/templates/mock_dispute_app/generated_application/app/tests/security/test_control_plane_policy.py`, `tests/test_phase71_82_wave_f_control_plane.py` |
| `GAP-APPROVAL-REPLAY-EXPIRY` | `factory/application_engineering/portfolio.py`, generated `ApprovalGrant` in `app/control_plane/policy.py` | Wave F validator scoped nonce, replay and expiry checks; direct portfolio smoke for replay and expired approvals |
| `GAP-AGENT-GOVERNANCE` | `AgentContract` with bounded iterations, least-privilege action set and independent verification in generated control-plane policy | Wave F validator and generated security test deny over-privileged or self-modifying actions |
| `GAP-ISOLATION-CONTROLS` | `IsolationBinding` binds application, version, process, port, state root and evidence root | Wave F validator and generated security test deny state/evidence root collisions |
| `GAP-PORTFOLIO-RECOMMENDATION-ONLY` | `control_plane_governance.json`, `PolicyDecision.recommendation_only`, existing `PortfolioComparator` non-production recommendation posture | Wave F validator requires recommendation-only portfolio assessment and no deployment/certification claim |
| `GAP-FRESH-GENERATED-OUTPUT` | `factory/templates/mock_dispute_app/template_manifest.v1.json`, `factory/generators/mock_dispute_app_generator.py` | Two fresh temporary generations from `scripts/validate_phase71_82_wave_f_control_plane.py` compare 78 generated template-file hashes and sizes |

Boundary: all controls are local-first, deterministic-first and mock-only. Wave F
adds no tenant billing, SaaS tenancy, Kubernetes control plane, live payment
rail, live identity-provider, OpenAI application call, deployment action or
certification claim.
