from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from typing import Any


class CleanSlateReplayError(RuntimeError):
    """Raised when isolated clean-slate replay cannot prove success."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=True,
        shell=False,
    )
    return {
        "argv": argv,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def copy_prerequisites(
    source_root: Path,
    target_root: Path,
    manifest_path: Path,
) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise CleanSlateReplayError(
            "Prerequisite manifest must be an object"
        )
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise CleanSlateReplayError(
            "Prerequisite artifacts must be a list"
        )
    records: list[dict[str, Any]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            raise CleanSlateReplayError(
                "Prerequisite entry must be an object"
            )
        relative = item.get("path")
        expected = item.get("sha256")
        if not isinstance(relative, str) or not isinstance(
            expected,
            str,
        ):
            raise CleanSlateReplayError(
                "Prerequisite path and hash are required"
            )
        source = source_root / relative
        target = target_root / relative
        if not source.is_file() or sha256(source) != expected:
            raise CleanSlateReplayError(
                f"Invalid prerequisite source: {relative}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha256(target) != expected:
            raise CleanSlateReplayError(
                f"Invalid prerequisite copy: {relative}"
            )
        records.append(
            {
                "path": relative,
                "sha256": expected,
                "size": target.stat().st_size,
            }
        )
    return records


def discover_generation_command(
    sandbox_root: Path,
    python: Path,
) -> list[str]:
    candidates = (
        "scripts/run_phase30_deep_generated_application_regeneration.py",
        "factory/generators/mock_dispute_app_generator.py",
    )
    for relative in candidates:
        if (sandbox_root / relative).is_file():
            return [str(python), relative]
    raise CleanSlateReplayError(
        "No governed local generation command was found"
    )


def remove_generated_outputs(sandbox_root: Path) -> list[str]:
    base = (
        sandbox_root
        / "workspace/factory_generated/upi_dispute_resolution"
    )
    names = (
        "generated_application",
        "generated_app",
        "application",
        "export_bundles",
        "generation_runs",
    )
    removed: list[str] = []
    for name in names:
        path = base / name
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(str(path.relative_to(sandbox_root)))
        elif path.is_file():
            path.unlink()
            removed.append(str(path.relative_to(sandbox_root)))
    return removed


def replay(
    *,
    project_root: Path,
    state_root: Path,
    python: Path,
) -> dict[str, Any]:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = (
        state_root
        / "clean_slate_replays"
        / f"phase46n-{stamp}"
    )
    sandbox = run_root / "repository"
    run_root.mkdir(parents=True, exist_ok=True)

    common_raw = subprocess.check_output(
        [
            "git",
            "-C",
            str(project_root),
            "rev-parse",
            "--git-common-dir",
        ],
        text=True,
    ).strip()
    common = Path(common_raw)
    if not common.is_absolute():
        common = (project_root / common).resolve()
    clone = subprocess.run(
        [
            "git",
            "clone",
            "--local",
            "--no-hardlinks",
            str(common),
            str(sandbox),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if clone.returncode != 0:
        raise CleanSlateReplayError(clone.stderr)

    prerequisites = copy_prerequisites(
        project_root,
        sandbox,
        project_root
        / "config/autonomous/prerequisite_artifact_manifest.json",
    )
    removed = remove_generated_outputs(sandbox)

    env = os.environ.copy()
    env["UPI_APP_FACTORY_STATE_DIR"] = str(run_root / "state")
    env["UPI_APP_FACTORY_EXPORT_DIR"] = str(run_root / "exports")
    env["PYTHONPATH"] = (
        str(sandbox)
        + (
            os.pathsep + env["PYTHONPATH"]
            if env.get("PYTHONPATH")
            else ""
        )
    )
    generation = run(
        discover_generation_command(sandbox, python),
        cwd=sandbox,
        env=env,
    )
    if generation["return_code"] != 0:
        raise CleanSlateReplayError(
            "Generation command failed: "
            + str(generation["stderr"])
        )

    validators = (
        "scripts/validate_phase30_deep_generated_application_regeneration.py",
        "scripts/validate_phase31_deep_generated_application_export_download_center.py",
        "scripts/validate_phase32_operator_portal_download_center.py",
        "scripts/validate_phase37_end_to_end_portal_run_flow.py",
    )
    validation_results: list[dict[str, Any]] = []
    for relative in validators:
        path = sandbox / relative
        if not path.is_file():
            continue
        result = run(
            [str(python), relative],
            cwd=sandbox,
            env=env,
        )
        validation_results.append(result)
        if result["return_code"] != 0:
            raise CleanSlateReplayError(
                f"Replay validator failed: {relative}"
            )

    generated_root = (
        sandbox
        / "workspace/factory_generated/upi_dispute_resolution"
    )
    if not generated_root.is_dir():
        raise CleanSlateReplayError(
            "Generated workspace was not recreated"
        )

    report = {
        "status": "PASSED",
        "mode": "ISOLATED_CLEAN_SLATE_REPLAY",
        "sandbox": str(sandbox),
        "removed_paths": removed,
        "prerequisite_count": len(prerequisites),
        "generation": generation,
        "validation_results": validation_results,
        "certification_posture": (
            "CERTIFICATION_READY_NOT_CERTIFIED"
        ),
        "live_provider_calls": 0,
        "production_deployment": False,
    }
    report_path = run_root / "replay_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    package = run_root / "handoff_evidence.tar.gz"
    with tarfile.open(package, "w:gz") as archive:
        archive.add(report_path, arcname="replay_report.json")
        export_root = generated_root / "export_bundles"
        if export_root.is_dir():
            archive.add(export_root, arcname="export_bundles")
    checksum = package.with_suffix(package.suffix + ".sha256")
    checksum.write_text(
        f"{sha256(package)}  {package.name}\n",
        encoding="utf-8",
    )
    report["handoff_package"] = str(package)
    report["handoff_checksum"] = str(checksum)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
