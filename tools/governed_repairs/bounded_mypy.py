from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from tools.governed_repairs.contracts import (
    RepairContext,
    RepairDecision,
    RepairResult,
)
from tools.governed_repairs.evidence import write_evidence
from tools.governed_repairs.rollback import capture_files, restore_files
from tools.governed_repairs.scope import verify_exact_candidate_scope

REPAIR_ID = "MYPY_FASTAPI_APIROUTE_NARROWING"
DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<path>tests/[^:\n]+\.py):(?P<line>\d+): error: "
    r'"BaseRoute" has no attribute "path" \[attr-defined\]$',
    re.MULTILINE,
)


class BoundedMyPyRepairError(RuntimeError):
    pass


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _candidate_from_diagnostics(
    diagnostics: str,
    candidate_paths: tuple[str, ...],
) -> tuple[str, int]:
    matches = list(DIAGNOSTIC_PATTERN.finditer(diagnostics.strip()))
    if len(matches) != 1:
        raise BoundedMyPyRepairError("Exactly one approved BaseRoute.path diagnostic is required")
    remaining = DIAGNOSTIC_PATTERN.sub("", diagnostics.strip()).strip()
    if remaining:
        raise BoundedMyPyRepairError("Unknown or additional MyPy diagnostics are not repairable")
    relative = matches[0].group("path")
    if relative not in candidate_paths:
        raise BoundedMyPyRepairError(f"MyPy diagnostic escaped candidate scope: {relative}")
    return relative, int(matches[0].group("line"))


def _find_target(source: str, line: int) -> tuple[str, str]:
    tree = ast.parse(source)
    candidates: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.SetComp, ast.ListComp, ast.GeneratorExp)):
            continue
        if not (node.lineno <= line <= (node.end_lineno or node.lineno)):
            continue
        if len(node.generators) != 1 or node.generators[0].ifs:
            continue
        generator = node.generators[0]
        if not isinstance(generator.target, ast.Name):
            continue
        variable = generator.target.id
        iterable = ast.get_source_segment(source, generator.iter)
        element = ast.get_source_segment(source, node.elt)
        if iterable is None or element is None:
            continue
        if iterable.endswith(".routes") and element == f"{variable}.path":
            candidates.append((variable, iterable))
    if len(candidates) != 1:
        raise BoundedMyPyRepairError("Expected exactly one unfiltered route-path comprehension")
    return candidates[0]


def _ensure_api_route_import(source: str) -> str:
    if re.search(
        r"from\s+fastapi\.routing\s+import\s+.*\bAPIRoute\b",
        source,
    ):
        return source
    lines = source.splitlines()
    tree = ast.parse(source)
    import_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    insertion = max(
        (node.end_lineno or node.lineno for node in import_nodes),
        default=0,
    )
    lines.insert(insertion, "from fastapi.routing import APIRoute")
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def _apply_narrowing(source: str, variable: str, iterable: str) -> str:
    pattern = re.compile(
        rf"(?P<prefix>[\[\{{\(]\s*{re.escape(variable)}\.path\s+for\s+"
        rf"{re.escape(variable)}\s+in\s+{re.escape(iterable)})"
        rf"(?P<suffix>\s*[\]\}}\)])",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise BoundedMyPyRepairError("Unable to locate exactly one approved comprehension")
    replacement = (
        matches[0].group("prefix")
        + f" if isinstance({variable}, APIRoute)"
        + matches[0].group("suffix")
    )
    return source[: matches[0].start()] + replacement + source[matches[0].end() :]


class FastAPIRouteNarrowingRepair:
    repair_id = REPAIR_ID

    def assess(self, context: RepairContext) -> RepairDecision:
        if context.attempt > context.max_attempts:
            return RepairDecision(
                repair_id=self.repair_id,
                eligible=False,
                reason="repair attempt limit exceeded",
            )
        try:
            relative, line = _candidate_from_diagnostics(
                context.diagnostics,
                context.candidate_paths,
            )
            source = (context.worktree / relative).read_text(encoding="utf-8")
            variable, iterable = _find_target(source, line)
        except (OSError, SyntaxError, BoundedMyPyRepairError) as exc:
            return RepairDecision(
                repair_id=self.repair_id,
                eligible=False,
                reason=str(exc),
            )
        return RepairDecision(
            repair_id=self.repair_id,
            eligible=True,
            reason="exact FastAPI APIRoute narrowing is eligible",
            affected_paths=(relative,),
            diagnostic_fingerprint=_fingerprint(context.diagnostics),
            metadata={"line": line, "variable": variable, "iterable": iterable},
        )

    def apply(
        self,
        context: RepairContext,
        decision: RepairDecision,
    ) -> RepairResult:
        if not decision.eligible or len(decision.affected_paths) != 1:
            raise BoundedMyPyRepairError(f"Repair decision is not eligible: {decision.reason}")
        relative = decision.affected_paths[0]
        target = context.worktree / relative
        snapshot = capture_files(context.worktree, (relative,))
        before = target.read_text(encoding="utf-8")
        try:
            updated = _apply_narrowing(
                before,
                str(decision.metadata["variable"]),
                str(decision.metadata["iterable"]),
            )
            updated = _ensure_api_route_import(updated)
            ast.parse(updated)
            compile(updated, str(target), "exec")
            target.write_text(updated, encoding="utf-8")
            commands = [
                [context.python, "-m", "mypy", relative],
                [context.python, "-m", "pytest", "-q", relative],
                [context.python, "-m", "ruff", "check", relative],
            ]
            results: list[dict[str, Any]] = []
            for argv in commands:
                completed = subprocess.run(
                    argv,
                    cwd=context.worktree,
                    text=True,
                    capture_output=True,
                    check=False,
                    env={
                        **os.environ,
                        "PYTHONDONTWRITEBYTECODE": "1",
                    },
                )
                results.append(
                    {
                        "argv": argv,
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    }
                )
                if completed.returncode != 0:
                    raise BoundedMyPyRepairError(f"Validation failed: {' '.join(argv)}")
            verify_exact_candidate_scope(
                context.worktree,
                set(context.candidate_paths),
            )
        except Exception:
            restore_files(context.worktree, snapshot)
            raise

        report_path = (
            context.run_dir
            / "repairs"
            / (f"attempt_{context.attempt:02d}_{self.repair_id.lower()}")
            / "repair_report.json"
        )
        write_evidence(
            report_path,
            {
                "schema_version": 1,
                "phase": context.phase,
                "repair_id": self.repair_id,
                "attempt": context.attempt,
                "diagnostic_fingerprint": decision.diagnostic_fingerprint,
                "changed_paths": [relative],
                "validation": results,
                "rollback_available": True,
                "llm_calls": 0,
            },
        )
        return RepairResult(
            repair_id=self.repair_id,
            status="APPLIED_AND_VALIDATED",
            changed_paths=(relative,),
            evidence_paths=(str(report_path),),
            validation={"passed": True, "commands": results},
            rollback_available=True,
        )


def apply_bounded_mypy_repair(
    *,
    phase: str,
    manifest_path: Path,
    run_dir: Path,
    python: str,
    attempt: int,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    manifest_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_value: object = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if not isinstance(manifest_value, dict) or not isinstance(run_value, dict):
        raise BoundedMyPyRepairError("Manifest and run must be objects")
    candidate_raw = manifest_value.get("candidate_paths")
    if not isinstance(candidate_raw, list) or not all(
        isinstance(item, str) for item in candidate_raw
    ):
        raise BoundedMyPyRepairError("candidate_paths must be strings")
    worktree_raw = run_value.get("worktree")
    failure = run_value.get("failure")
    if not isinstance(worktree_raw, str) or not isinstance(failure, dict):
        raise BoundedMyPyRepairError("Run worktree/failure is invalid")
    diagnostics = str(failure.get("message", ""))
    log_match = re.search(r"see\s+(?P<path>/\S+\.log)", diagnostics)
    if log_match:
        log_path = Path(log_match.group("path"))
        if log_path.is_file():
            log_text = log_path.read_text(encoding="utf-8")
            stdout_match = re.search(
                r"\[stdout\]\n(?P<body>.*?)(?:\n\[stderr\]|\Z)",
                log_text,
                re.DOTALL,
            )
            diagnostics = stdout_match.group("body").strip() if stdout_match else log_text.strip()
    context = RepairContext(
        phase=phase,
        repair_id=REPAIR_ID,
        project_root=Path(str(run_value.get("project_root", "."))),
        worktree=Path(worktree_raw),
        run_dir=run_dir,
        manifest_path=manifest_path,
        candidate_paths=tuple(candidate_raw),
        diagnostics=diagnostics,
        attempt=attempt,
        max_attempts=2,
        python=python,
    )
    repair = FastAPIRouteNarrowingRepair()
    decision = repair.assess(context)
    if not decision.eligible:
        raise BoundedMyPyRepairError(decision.reason)
    result = repair.apply(context, decision)
    report = {
        "repair_id": result.repair_id,
        "status": result.status,
        "changed_paths": list(result.changed_paths),
        "evidence_paths": list(result.evidence_paths),
        "validation": result.validation,
        "rollback_available": result.rollback_available,
        "diagnostic": decision.reason,
    }
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        write_evidence(evidence_dir / "repair_result.json", report)
    return report
