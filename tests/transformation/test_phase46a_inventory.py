from __future__ import annotations

from pathlib import Path

from tools.transformation_controller.phase46a import (
    create_task_graph,
    protected_action_matrix,
    scan_patterns,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_current_source_legacy_identity_is_current_product_identity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "factory" / "module.py"
    write(source, 'NAME = "upi_dispute_resolution\x5ffactory"\n')
    findings = scan_patterns(tmp_path)
    assert len(findings) == 1
    assert findings[0].classification == "CURRENT_PRODUCT_IDENTITY"


def test_historical_lifecycle_evidence_is_preserved(tmp_path: Path) -> None:
    evidence = tmp_path / "lifecycle_artifacts" / "release.md"
    write(evidence, "upi_dispute_resolution\x5ffactory\n")
    assert scan_patterns(tmp_path)[0].classification == "HISTORICAL_EVIDENCE"


def test_current_document_path_is_a_current_defect(tmp_path: Path) -> None:
    document = tmp_path / "docs" / "operator_guide.md"
    write(
        document,
        "cd /home/marcose/projects/upi_dispute_resolution\x5ffactory\n",
    )
    classifications = {item.classification for item in scan_patterns(tmp_path)}
    assert classifications == {
        "CURRENT_PATH_DEFECT",
        "CURRENT_PRODUCT_IDENTITY",
    }


def test_numbered_phase_document_is_historical(tmp_path: Path) -> None:
    document = tmp_path / "docs" / "phase13c" / "old.md"
    write(document, "Factory\x46romNothing /home/marcose/project\n")
    classifications = {item.classification for item in scan_patterns(tmp_path)}
    assert classifications == {"HISTORICAL_EVIDENCE"}


def test_path_policy_examples_are_migration_references(tmp_path: Path) -> None:
    policy = tmp_path / "policies" / "path_neutrality.yaml"
    write(policy, "- /home/marcose/Downloads\n")
    classifications = {item.classification for item in scan_patterns(tmp_path)}
    assert classifications == {"MIGRATION_REFERENCE"}


def test_detector_patterns_are_detection_rule_references(tmp_path: Path) -> None:
    detector = tmp_path / "tools" / "transformation_controller" / "phase46a.py"
    write(detector, 'PATTERN = r"/home/marcose"\n')
    assert scan_patterns(tmp_path)[0].classification == "DETECTION_RULE_REFERENCE"


def test_current_test_assertions_require_migration(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "test_branding.py"
    write(test_file, 'assert "Factory\x46romNothing" in text\n')
    assert scan_patterns(tmp_path)[0].classification == "CURRENT_TEST_EXPECTATION"


def test_generated_application_current_content_requires_migration(
    tmp_path: Path,
) -> None:
    generated = (
        tmp_path / "workspace" / "factory_generated" / "app" / "generated_application" / "README.md"
    )
    write(
        generated,
        "/home/marcose/projects/upi_dispute_resolution\x5ffactory\n",
    )
    classifications = {item.classification for item in scan_patterns(tmp_path)}
    assert classifications == {"CURRENT_GENERATED_CONTENT"}


def test_original_observed_path_is_historical_provenance(
    tmp_path: Path,
) -> None:
    provenance = tmp_path / "factory_governance" / "baseline_provenance_manifest.json"
    write(
        provenance,
        '"original_path_observed": "/home/marcose/Downloads/a.zip"\n',
    )
    classifications = {item.classification for item in scan_patterns(tmp_path)}
    assert classifications == {"HISTORICAL_EVIDENCE"}


def test_task_graph_uses_zero_llm_by_default() -> None:
    graph = create_task_graph([])
    assert graph["llm_default"] == "disabled"
    assert all(task["llm_eligible"] is False for task in graph["tasks"])


def test_task_graph_preserves_human_rename_boundaries() -> None:
    graph = create_task_graph([])
    protected = {task["task_id"] for task in graph["tasks"] if task["protected_action"]}
    assert protected == {"T-012", "T-013"}


def test_protected_matrix_includes_all_critical_boundaries() -> None:
    actions = {item["action"] for item in protected_action_matrix()["actions"]}
    assert {
        "commit",
        "compatibility_layer_removal",
        "local_checkout_rename",
        "remote_repository_rename",
        "merge",
        "tag",
        "push",
        "release",
    } <= actions
