from __future__ import annotations

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts/run_portal_requirements_driven_application_engineering.py"


def _assigned_names(target: ast.expr) -> set[str]:
    names: set[str] = set()
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            names.update(_assigned_names(item))
    return names


class PortalAdapterTypingContractTest(unittest.TestCase):
    def test_run_does_not_reannotate_existing_local_names(self) -> None:
        module = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
        run_function = next(
            node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "run"
        )

        seen_assignments: set[str] = set()
        reannotated_names: list[str] = []
        for node in ast.walk(run_function):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    seen_assignments.update(_assigned_names(target))
            elif isinstance(node, ast.AnnAssign):
                annotated_names = _assigned_names(node.target)
                reannotated_names.extend(sorted(annotated_names & seen_assignments))
                seen_assignments.update(annotated_names)

        self.assertEqual(
            reannotated_names,
            [],
            f"reannotated local names in run(): {reannotated_names}",
        )
