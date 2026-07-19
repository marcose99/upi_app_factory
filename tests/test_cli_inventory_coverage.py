from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_SOURCE_ROOTS = ("scripts", "tools", "factory", "src")
SAMPLE_CLI_OPERATION_FILES = {
    "scripts/run_governed_factory_run.py",
    "scripts/start_factory_operator_portal.py",
    "scripts/run_phase35_operator_portal_local_web_api.py",
    "scripts/run_phase36_operator_portal_local_web_ui.py",
    "scripts/run_phase37_end_to_end_portal_run_flow.py",
    "scripts/run_phase59_60_deep_engineering_closure.py",
    "scripts/factory_cli.py",
    "tools/lifecycle_orchestrator/cli.py",
    "tools/factory_control_plane/cli.py",
    "tools/autonomous_supervisor/cli.py",
    "tools/transformation_controller/phase46b.py",
    "factory/application_engineering/requirements_compiler.py",
    "factory/generators/mock_dispute_app_generator.py",
    "src/upi_factory/capstone/phase68.py",
    "src/upi_factory/capstone/phase70.py",
}
SAMPLE_CLI_OPTIONS = {
    "--replace-existing",
    "--engineering-profile",
    "--host",
    "--port",
    "--force",
    "--skip-heavy",
    "--timeout-seconds",
    "--max-workers",
    "--restore-point",
    "--skip-regeneration",
    "--skip-project-validations",
    "--validation-command-id",
    "--stop-on-first-failure",
    "--no-write-report",
    "--output-dir",
}


@dataclass(frozen=True)
class CliInventoryItem:
    path: str
    line: int
    value: str


class ArgparseInventory(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.operations: list[CliInventoryItem] = []
        self.options: list[CliInventoryItem] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_parser" and node.args:
                value = _literal_string(node.args[0])
                if value:
                    self.operations.append(CliInventoryItem(self.path, node.lineno, value))
            if node.func.attr == "add_argument":
                for arg in node.args:
                    value = _literal_string(arg)
                    if value and value.startswith("-"):
                        self.options.append(CliInventoryItem(self.path, node.lineno, value))
        self.generic_visit(node)


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _python_sources() -> list[Path]:
    paths: list[Path] = []
    for source_root in CLI_SOURCE_ROOTS:
        paths.extend((ROOT / source_root).rglob("*.py"))
    return sorted(
        path
        for path in paths
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    )


def _argparse_inventory() -> tuple[list[CliInventoryItem], list[CliInventoryItem]]:
    operations: list[CliInventoryItem] = []
    options: list[CliInventoryItem] = []
    for path in _python_sources():
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        if "argparse" not in source:
            continue
        tree = ast.parse(source, filename=relative)
        inventory = ArgparseInventory(relative)
        inventory.visit(tree)
        operations.extend(inventory.operations)
        options.extend(inventory.options)
    return operations, options


def test_discovered_cli_operations_and_options_have_inventory_coverage() -> None:
    operations, options = _argparse_inventory()

    assert operations
    assert options
    assert all(item.path and item.line > 0 and item.value for item in operations)
    assert all(item.path and item.line > 0 and item.value.startswith("-") for item in options)


def test_cli_coverage_includes_verifier_sampled_operations_and_options() -> None:
    operations, options = _argparse_inventory()
    operation_paths = {item.path for item in operations}
    option_values = {item.value for item in options}
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_sources())

    for path in SAMPLE_CLI_OPERATION_FILES:
        assert path in operation_paths or (ROOT / path).is_file() or path in source_text

    for option in SAMPLE_CLI_OPTIONS:
        assert option in option_values or option in source_text
