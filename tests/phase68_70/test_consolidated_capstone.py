from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from upi_factory.capstone.consolidated import (
    CAMPAIGN_ID,
    run_consolidated_capstone,
    validate_consolidated_capstone,
)


ROOT = Path(__file__).resolve().parents[2]


def test_consolidated_runner_writes_truthful_isolated_summary(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    summary = run_consolidated_capstone(project_root=ROOT, runtime_root=runtime)

    assert summary["status"] == "PASS"
    assert summary["campaign_id"] == CAMPAIGN_ID
    assert summary["runtime_llm_calls"] == 0
    assert summary["official_certification_claimed"] is False
    assert summary["production_readiness_claimed"] is False
    assert summary["trust_boundaries"]["recipient_replay_requires_ignored_workspace"] is False
    assert summary["trust_boundaries"]["portal_progress_source"] == "control-plane-events"
    assert summary["phase_contracts"]["phase68"]["status"] == "PASS"
    assert summary["phase_contracts"]["phase69"]["status"] == "PASS"
    assert summary["phase_contracts"]["phase70"]["profile_count"] == 6
    assert (runtime / "events.json").is_file()
    assert (runtime / "evidence_integrity.json").is_file()
    assert (runtime / "final_summary.json").is_file()


def test_consolidated_validator_accepts_clean_runtime_and_rejects_tamper(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    run_consolidated_capstone(project_root=ROOT, runtime_root=runtime)

    clean = validate_consolidated_capstone(project_root=ROOT, runtime_root=runtime)
    assert clean["status"] == "PASS", clean["errors"]

    summary_path = runtime / "final_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["runtime_llm_calls"] = 1
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tampered = validate_consolidated_capstone(project_root=ROOT, runtime_root=runtime)
    assert tampered["status"] == "FAIL"
    assert any("summary hash mismatch" in error or "LLM calls" in error for error in tampered["errors"])


def test_consolidated_cli_and_bin_pass(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    run = subprocess.run(
        [sys.executable, "scripts/run_phase68_70_consolidated_capstone.py", "--runtime-root", str(runtime)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["status"] == "PASS"

    validate = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase68_70_consolidated_capstone.py",
            "--runtime-root",
            str(runtime),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    assert json.loads(validate.stdout)["status"] == "PASS"

    bin_run = subprocess.run(
        ["bin/upi-app-factory-capstone", "--runtime-root", str(tmp_path / "bin-runtime")],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert bin_run.returncode == 0, bin_run.stdout + bin_run.stderr
    assert json.loads(bin_run.stdout)["status"] == "PASS"
