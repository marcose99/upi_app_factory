from __future__ import annotations

import sys
from pathlib import Path

from tools.governed_repairs.bounded_mypy import FastAPIRouteNarrowingRepair
from tools.governed_repairs.contracts import RepairContext


def test_exact_route_narrowing_is_assessed_and_applied(tmp_path: Path) -> None:
    test_path = tmp_path / "tests/test_routes.py"
    test_path.parent.mkdir()
    test_path.write_text(
        "from fastapi import APIRouter\n\n"
        "def test_routes() -> None:\n"
        "    router = APIRouter()\n"
        "    paths = {route.path for route in router.routes}\n"
        "    assert isinstance(paths, set)\n",
        encoding="utf-8",
    )
    context = RepairContext(
        phase="46R",
        repair_id="MYPY_FASTAPI_APIROUTE_NARROWING",
        project_root=tmp_path,
        worktree=tmp_path,
        run_dir=tmp_path / "run",
        manifest_path=tmp_path / "manifest.json",
        candidate_paths=("tests/test_routes.py",),
        diagnostics=(
            'tests/test_routes.py:5: error: "BaseRoute" has no attribute "path" [attr-defined]'
        ),
        attempt=1,
        max_attempts=2,
        python=sys.executable,
    )
    repair = FastAPIRouteNarrowingRepair()
    decision = repair.assess(context)
    assert decision.eligible is True
    result = repair.apply(context, decision)
    assert result.status == "APPLIED_AND_VALIDATED"
    updated = test_path.read_text(encoding="utf-8")
    assert "from fastapi.routing import APIRoute" in updated
    assert "if isinstance(route, APIRoute)" in updated


def test_unknown_diagnostic_fails_closed(tmp_path: Path) -> None:
    context = RepairContext(
        phase="46R",
        repair_id="MYPY_FASTAPI_APIROUTE_NARROWING",
        project_root=tmp_path,
        worktree=tmp_path,
        run_dir=tmp_path,
        manifest_path=tmp_path / "manifest.json",
        candidate_paths=("tests/test_routes.py",),
        diagnostics="tests/test_routes.py:1: error: unknown [misc]",
        attempt=1,
        max_attempts=2,
        python=sys.executable,
    )
    assert FastAPIRouteNarrowingRepair().assess(context).eligible is False
