from __future__ import annotations

from pathlib import Path

import pytest

from tools.governed_repairs.contracts import (
    RepairContext,
    RepairDecision,
    RepairResult,
)
from tools.governed_repairs.registry import (
    GovernedRepairRegistry,
    RepairRegistryError,
)
from tools.governed_repairs.rollback import capture_files, restore_files


class ExampleRepair:
    repair_id = "EXAMPLE"

    def assess(self, context: RepairContext) -> RepairDecision:
        return RepairDecision(
            repair_id=self.repair_id,
            eligible=context.attempt <= context.max_attempts,
            reason="bounded",
        )

    def apply(
        self,
        context: RepairContext,
        decision: RepairDecision,
    ) -> RepairResult:
        return RepairResult(
            repair_id=self.repair_id,
            status="APPLIED",
            changed_paths=(),
            evidence_paths=(),
            validation={"passed": True},
            rollback_available=True,
        )


def context(tmp_path: Path) -> RepairContext:
    return RepairContext(
        phase="46Q",
        repair_id="EXAMPLE",
        project_root=tmp_path,
        worktree=tmp_path,
        run_dir=tmp_path,
        manifest_path=tmp_path / "manifest.json",
        candidate_paths=(),
        diagnostics="",
        attempt=1,
        max_attempts=2,
        python="python",
    )


def test_registry_is_explicit_and_duplicate_safe(tmp_path: Path) -> None:
    registry = GovernedRepairRegistry()
    repair = ExampleRepair()
    registry.register(repair)
    assert registry.ids() == ("EXAMPLE",)
    assert registry.assess("EXAMPLE", context(tmp_path)).eligible is True
    with pytest.raises(RepairRegistryError):
        registry.register(repair)


def test_file_snapshot_restores_exact_content(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("before\n", encoding="utf-8")
    snapshot = capture_files(tmp_path, ("sample.txt", "absent.txt"))
    target.write_text("after\n", encoding="utf-8")
    (tmp_path / "absent.txt").write_text("new\n", encoding="utf-8")
    restore_files(tmp_path, snapshot)
    assert target.read_text(encoding="utf-8") == "before\n"
    assert not (tmp_path / "absent.txt").exists()
