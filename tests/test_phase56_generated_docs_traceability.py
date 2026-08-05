from __future__ import annotations

import json
from pathlib import Path
import shutil

from factory.application_engineering.deep_composer import DeepApplicationComposer, GOLDEN_APP_ID
from factory.application_engineering.requirements_compiler import compile_requirements


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "phase53" / "failed_debit_requirements.md"


def _workspace_output(name: str) -> Path:
    path = ROOT / "workspace" / "deep_engineering_campaign" / "phase56_test_runs" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def test_generated_traceability_maps_requirements_to_code_and_tests() -> None:
    output = _workspace_output("traceability_docs")
    requirements_ir = compile_requirements([FIXTURE], ROOT)
    DeepApplicationComposer(ROOT).compose(requirements_ir=requirements_ir, output_root=output, app_id=GOLDEN_APP_ID)

    trace = json.loads((output / GOLDEN_APP_ID / "evidence" / "requirements_trace.json").read_text(encoding="utf-8"))

    assert trace["generated_application"]["app_id"] == GOLDEN_APP_ID
    assert trace["generated_application"]["runtime_llm_calls"] == 0
    assert trace["summary"]["requirement_count"] == len(requirements_ir["traceability"])
    assert trace["source_documents"]
    first = trace["mappings"][0]
    assert first["code_paths"]
    assert first["test_paths"]
    assert first["generated_artifacts"]


def test_generated_runbook_and_test_plan_are_operator_usable() -> None:
    output = _workspace_output("operator_docs")
    requirements_ir = compile_requirements([FIXTURE], ROOT)
    DeepApplicationComposer(ROOT).compose(requirements_ir=requirements_ir, output_root=output, app_id=GOLDEN_APP_ID)

    runbook = (output / GOLDEN_APP_ID / "docs" / "operations_runbook.md").read_text(encoding="utf-8")
    test_plan = (output / GOLDEN_APP_ID / "docs" / "test_plan.md").read_text(encoding="utf-8")

    assert "loopback only" in runbook
    assert "Real payment/provider calls: `disabled`" in runbook
    assert "GET /health" in runbook
    assert "evidence/requirements_trace.json" in runbook
    assert "python -m pytest -q tests/test_service.py" in test_plan
    assert "Lifecycle states" in test_plan
    assert "no live-provider dependency" in test_plan
