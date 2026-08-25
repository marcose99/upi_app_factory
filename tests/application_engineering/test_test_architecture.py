from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from factory.application_engineering.runtime_architecture import render_runtime_architecture_files
from factory.application_engineering.semantic_realization import (
    build_semantic_model,
    render_semantic_files,
)
from factory.application_engineering.test_architecture import (
    collect_test_inventory,
    render_executable_tests,
    validate_trace_paths,
)


PYTHON = sys.executable


def _package(root: Path) -> None:
    model = build_semantic_model(
        {
            "actors": [{"id": "ACT-1", "name": "operator"}],
            "apis": [{"id": "API-1", "method": "POST", "path": "/cases"}],
            "workflows": [
                {
                    "id": "WF-1",
                    "from": "received",
                    "to": "reviewed",
                    "signal": "review",
                    "deadline": "P1D",
                    "reentry": "retry",
                    "human_review": True,
                }
            ],
            "security": [{"id": "SEC-1", "description": "local only"}],
        }
    )
    files = {
        "app/__init__.py": "",
        "app/sample_app/__init__.py": "",
        "app/sample_app/application/__init__.py": "",
        "app/sample_app/infrastructure/__init__.py": "",
    }
    files.update(render_semantic_files(model, "sample_app"))
    files.update(render_runtime_architecture_files(model, "sample_app"))
    files.update(render_executable_tests(model, "sample_app"))
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_trace_integrity_and_inventory_are_raw_measurements(tmp_path: Path) -> None:
    _package(tmp_path)
    trace = validate_trace_paths(tmp_path)
    inventory = collect_test_inventory(tmp_path)
    assert trace["status"] == "PASS" and trace["missing_test_path_count"] == 0
    assert inventory["collected_test_count"] >= 14
    assert inventory["score_eligible"] is True
    assert inventory["testing_depth_score"] is None


def test_trace_validator_rejects_missing_and_escaping_paths(tmp_path: Path) -> None:
    _package(tmp_path)
    trace_path = tmp_path / "evidence/executable_test_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace["test_paths"].extend(["tests/test_missing.py", "../outside/test_escape.py"])
    result = validate_trace_paths(tmp_path, trace)
    assert result["status"] == "FAIL"
    assert result["missing_paths"] == ["tests/test_missing.py"]
    assert result["unsafe_paths"] == ["../outside/test_escape.py"]


def test_extracted_package_pytest_is_hermetic_from_ancestor_conftest(tmp_path: Path) -> None:
    ancestor = tmp_path / "ancestor"
    package = ancestor / "extracted" / "application"
    package.mkdir(parents=True)
    (ancestor / "conftest.py").write_text(
        'raise RuntimeError("ancestor conftest loaded")\n', encoding="utf-8"
    )
    _package(package)
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [PYTHON, "-m", "pytest", "-q", "-c", "pytest.ini", "--rootdir=.", "--confcutdir=."],
        cwd=package,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout
    assert "passed" in result.stdout


def test_deep_runtime_tests_do_not_module_skip_non_workflow_architectures() -> None:
    model = build_semantic_model(
        {
            "actors": [{"id": "ACT-1", "name": "operator"}],
            "apis": [{"id": "API-1", "method": "GET", "path": "/health"}],
            "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
            "security": [{"id": "SEC-1", "description": "local only"}],
        }
    )
    source = render_executable_tests(model, "sample_app")["tests/test_generated_runtime_depth.py"]
    assert 'pytest.importorskip("app.sample_app.application.workflows.dispute_workflow")' not in source
    assert "test_event_driven_service_and_aggregate_branches_are_executable" in source
    assert "test_hexagonal_service_and_aggregate_branches_are_executable" in source
    assert 'pytest.skip("hexagonal adapter is not selected")' in source
    assert 'build_runtime_adapters("unknown")' in source

def test_generated_contract_separates_optional_architecture_depth_and_openapi_self_endpoint() -> None:
    model = build_semantic_model(
        {
            "actors": [{"id": "ACT-1", "name": "operator"}],
            "apis": [{"id": "API-1", "method": "POST", "path": "/cases"}],
            "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
            "security": [{"id": "SEC-1", "description": "local only"}],
        }
    )
    files = render_executable_tests(model, "sample_app")
    depth = files["tests/test_generated_runtime_depth.py"]
    api = files["tests/test_api_contract.py"]
    assert 'pytest.importorskip("app.sample_app.infrastructure.runtime_adapters")' in depth
    assert 'framework_runtime_only = {"GET /openapi.json"}' in api
    assert "app.routes" not in api
