# Wave E Traceability

| Gap | Implementation Evidence | Test/Evidence |
| --- | --- | --- |
| `GAP-SUPPLY-CHAIN` | `factory/templates/mock_dispute_app/generated_application/evidence/assurance/dependency_license_inventory.json`, `factory/templates/mock_dispute_app/generated_application/evidence/assurance/cyclonedx_1_7_sbom.json`, `factory/templates/mock_dispute_app/generated_application/evidence/assurance/spdx_3_0_sbom.json`, `factory/templates/mock_dispute_app/generated_application/evidence/assurance/slsa_1_2_provenance_verification.json` | `scripts/validate_phase71_82_wave_e_assurance_supply_chain.py`, `factory/templates/mock_dispute_app/generated_application/app/tests/audit/test_assurance_supply_chain_evidence.py`, `tests/test_phase71_82_wave_e_assurance_supply_chain.py` |
| `GAP-FRESH-GENERATED-OUTPUT` | `factory/templates/mock_dispute_app/template_manifest.v1.json`, `factory/generators/mock_dispute_app_generator.py` | Two fresh temporary generations from `scripts/validate_phase71_82_wave_e_assurance_supply_chain.py` compare generated template-file hashes and sizes |
| ASVS/API/SAMM assurance mapping | `factory/templates/mock_dispute_app/generated_application/evidence/assurance/asvs_5_0_l2_mapping.json`, `factory/templates/mock_dispute_app/generated_application/evidence/assurance/owasp_api_security_checks.json`, `factory/templates/mock_dispute_app/generated_application/evidence/assurance/samm_maturity_evidence.json` | Wave E validator structural checks and generated audit test |
| Threat model and abuse cases | `factory/templates/mock_dispute_app/generated_application/evidence/assurance/threat_model_abuse_cases.json` | Wave E validator requires abuse cases and unresolved-risk ownership |
| OpenSSF baseline and Scorecard orientation | `factory/templates/mock_dispute_app/generated_application/evidence/assurance/openssf_scorecard_assessment.json` | Wave E validator requires no numeric Scorecard claim and owners for unresolved findings |
| Generated test families | Existing generated tests under `factory/templates/mock_dispute_app/generated_application/app/tests/` plus `app/tests/audit/test_assurance_supply_chain_evidence.py` | Migration, contract, authz, concurrency, event replay, restart, security, performance and audit evidence are preserved in the template manifest |

Boundary: all evidence is local-first, deterministic-first and mock-only.
Standards are used as benchmarks only; this wave makes no certification,
regulatory approval, production-readiness, production-capacity, formal SBOM
schema certification, numeric OpenSSF Scorecard or attained SLSA-level claim.
