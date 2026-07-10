from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import tarfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

SCHEMA_VERSION = 1
TEXT_SUFFIXES = {
    ".py", ".pyi", ".sh", ".bash", ".zsh", ".fish", ".md", ".rst", ".txt",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".html", ".htm", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx", ".xml",
    ".sql", ".dockerfile", ".service",
}
EXACT_TEXT_NAMES = {
    "Dockerfile", "Makefile", "AGENTS.md", ".gitignore", ".dockerignore",
    "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml",
}
IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".tox", ".nox", "dist", "build",
}
MAX_TEXT_BYTES = 2_000_000

IDENTITY_PATTERNS = [
    ("IDENTITY_FACTORYFROMNOTHING", re.compile(r"\bFactoryFromNothing\b")),
    ("IDENTITY_LEGACY_TECHNICAL", re.compile(r"\bupi_dispute_resolution_factory\b")),
    ("IDENTITY_LEGACY_DISPLAY", re.compile(r"\bUPI Dispute Resolution Factory\b")),
]
PATH_PATTERNS = [
    ("PATH_USER_MARCOSE", re.compile(r"/home/marcose(?:/[\w.\-]+)*")),
    ("PATH_HOME_ABSOLUTE", re.compile(r"/home/[A-Za-z0-9_.-]+(?:/[\w.\-]+)+")),
    ("PATH_DOWNLOADS", re.compile(r"(?:/|~/?)[A-Za-z0-9_.-]*/?Downloads(?:/[\w.\-]+)*")),
]
PORTABILITY_PATTERNS = [
    ("PORTABILITY_APT", re.compile(r"(?<![\w-])(?:apt|apt-get)\s+(?:install|update|upgrade)\b")),
    ("PORTABILITY_SYSTEMCTL", re.compile(r"(?<![\w-])systemctl\s+\w+")),
    ("PORTABILITY_UBUNTU", re.compile(r"\bUbuntu(?:\s+\d+(?:\.\d+)*)?\b", re.IGNORECASE)),
]

HISTORICAL_PARTS = {
    "lifecycle_artifacts", "evidence", "audit", "historical", "history",
    "release_evidence", "logs",
}
MIGRATION_PARTS = {"migration", "migrations", "phase46a", "transformation"}
FIXTURE_PARTS = {"fixtures", "snapshots", "golden", "testdata", "test_data"}

@dataclass(frozen=True)
class Finding:
    finding_id: str
    category: str
    classification: str
    path: str
    line: int
    matched_text: str
    context: str
    rule_id: str

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def run_command(
    args: Sequence[str], cwd: Path, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=str(cwd), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=check,
    )

def git(root: Path, *args: str) -> str:
    return run_command(["git", *args], root).stdout.strip()

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)

def state_root() -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "upi_app_factory").resolve()
    return (Path.home() / ".local" / "state" / "upi_app_factory").resolve()

def export_root() -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_EXPORT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "upi_app_factory" / "exports").resolve()
    return (Path.home() / ".local" / "share" / "upi_app_factory" / "exports").resolve()

def iter_text_files(root: Path) -> Iterator[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS)
        current_path = Path(current)
        for name in sorted(files):
            path = current_path / name
            try:
                if path.stat().st_size > MAX_TEXT_BYTES:
                    continue
            except OSError:
                continue
            if name in EXACT_TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES:
                yield path

def path_parts_lower(relative: Path) -> set[str]:
    return {part.lower() for part in relative.parts}

def _is_numbered_phase_part(part: str) -> bool:
    return re.fullmatch(r"phase(?:[_-]?\d).+", part) is not None

def _is_historical_path(relative: Path, line: str) -> bool:
    parts = path_parts_lower(relative)
    text_path = relative.as_posix().lower()
    if "original_path_observed" in line:
        return True
    if parts & HISTORICAL_PARTS:
        return True
    if "docs" in parts and ("adr" in parts or any(_is_numbered_phase_part(part) for part in parts)):
        return True
    historical_names = {
        "baseline_provenance_manifest.json",
        "baseline_provenance_audit.md",
    }
    if relative.name.lower() in historical_names:
        return True
    return any(token in text_path for token in ("/archive/", "/historical/"))

def _is_generated_current_content(relative: Path) -> bool:
    parts = path_parts_lower(relative)
    return (
        "workspace" in parts
        and "factory_generated" in parts
        and "lifecycle_artifacts" not in parts
    )

def classify(relative: Path, category: str, line: str = "") -> str:
    parts = path_parts_lower(relative)
    text_path = relative.as_posix().lower()
    managed_migration_files = {
        "agents.md",
        "config/product_identity.yaml",
        "policies/path_neutrality.yaml",
        "policies/llm_usage_policy.yaml",
        "policies/protected_actions.yaml",
        "requirements/master_consolidated_requirements.md",
    }

    if text_path in managed_migration_files:
        return "MIGRATION_REFERENCE"
    if text_path == "tools/transformation_controller/phase46a.py":
        return "DETECTION_RULE_REFERENCE"
    if parts & MIGRATION_PARTS:
        return "MIGRATION_REFERENCE"
    if _is_historical_path(relative, line):
        return "HISTORICAL_EVIDENCE"
    if _is_generated_current_content(relative):
        return "CURRENT_GENERATED_CONTENT"
    if parts & FIXTURE_PARTS:
        return "TEST_FIXTURE"
    if "tests" in parts:
        return "CURRENT_TEST_EXPECTATION"
    if category.startswith("PATH_"):
        return "CURRENT_PATH_DEFECT"
    if category.startswith("PORTABILITY_"):
        return "CURRENT_PORTABILITY_DEFECT"
    if category.startswith("IDENTITY_"):
        return "CURRENT_PRODUCT_IDENTITY"
    return "AMBIGUOUS"

def line_context(line: str, limit: int = 220) -> str:
    collapsed = " ".join(line.strip().split())
    return collapsed[:limit]

def scan_patterns(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    counter = 0
    pattern_groups = [
        *IDENTITY_PATTERNS,
        *PATH_PATTERNS,
        *PORTABILITY_PATTERNS,
    ]
    for path in iter_text_files(root):
        relative = path.relative_to(root)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for category, pattern in pattern_groups:
                for match in pattern.finditer(line):
                    counter += 1
                    findings.append(Finding(
                        finding_id=f"F-{counter:06d}",
                        category=category,
                        classification=classify(relative, category, line),
                        path=relative.as_posix(),
                        line=line_number,
                        matched_text=match.group(0)[:300],
                        context=line_context(line),
                        rule_id=category,
                    ))
    return findings

def python_inventory(root: Path) -> dict[str, Any]:
    imports: list[dict[str, object]] = []
    parse_errors: list[dict[str, object]] = []
    packages: set[str] = set()
    for path in iter_text_files(root):
        if path.suffix != ".py":
            continue
        relative = path.relative_to(root)
        if path.name == "__init__.py":
            packages.add(relative.parent.as_posix())
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        except (SyntaxError, OSError, UnicodeError) as exc:
            parse_errors.append({"path": relative.as_posix(), "error": str(exc)})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "path": relative.as_posix(), "line": node.lineno,
                        "kind": "import", "module": alias.name,
                    })
            elif isinstance(node, ast.ImportFrom):
                imports.append({
                    "path": relative.as_posix(), "line": node.lineno,
                    "kind": "from", "module": node.module or "",
                    "level": node.level,
                })
    return {
        "packages": sorted(packages),
        "imports": imports,
        "parse_errors": parse_errors,
    }

def portal_inventory(root: Path) -> dict[str, Any]:
    route_pattern = re.compile(
        r"""@(?:app|router)\.(get|post|put|patch|delete|options|head)\(\s*["']([^"']+)["']"""
    )
    routes: list[dict[str, object]] = []
    portal_files: list[str] = []
    for path in iter_text_files(root):
        relative = path.relative_to(root)
        lowered = relative.as_posix().lower()
        if "portal" not in lowered:
            continue
        portal_files.append(relative.as_posix())
        if path.suffix != ".py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in route_pattern.finditer(text):
            routes.append({
                "method": match.group(1).upper(),
                "path": match.group(2),
                "source": relative.as_posix(),
            })
    return {"portal_files": sorted(set(portal_files)), "static_routes": routes}

def operational_inventory(root: Path) -> dict[str, Any]:
    categories: dict[str, list[str]] = defaultdict(list)
    for path in iter_text_files(root):
        relative = path.relative_to(root).as_posix()
        lower = relative.lower()
        name = path.name.lower()
        if path.suffix == ".sh":
            categories["shell_scripts"].append(relative)
        container_names = {
            "dockerfile", "compose.yml", "compose.yaml",
            "docker-compose.yml", "docker-compose.yaml",
        }
        if name in container_names:
            categories["container_files"].append(relative)
        service_markers = ("systemd", "openrc", "supervisor")
        if path.suffix == ".service" or any(marker in lower for marker in service_markers):
            categories["service_files"].append(relative)
        if "report" in lower:
            categories["report_files"].append(relative)
        if "handoff" in lower or "handover" in lower:
            categories["handoff_files"].append(relative)
    return {key: sorted(set(value)) for key, value in sorted(categories.items())}

def create_task_graph(findings: list[Finding]) -> dict[str, Any]:
    counts = Counter(item.classification for item in findings)
    tasks: list[dict[str, Any]] = [
        {
            "task_id": "T-001",
            "name": "Establish canonical product identity registry",
            "depends_on": [],
            "execution": "deterministic",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["identity_registry_schema", "identity_reference_tests"],
        },
        {
            "task_id": "T-002",
            "name": "Establish Linux-neutral path and platform settings",
            "depends_on": ["T-001"],
            "execution": "deterministic",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["path_policy_tests", "platform_capability_tests"],
        },
        {
            "task_id": "T-003",
            "name": "Create approved current-versus-historical migration manifest",
            "depends_on": ["T-001", "T-002"],
            "execution": "deterministic",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["classification_semantic_tests", "manifest_schema"],
        },
        {
            "task_id": "T-004",
            "name": "Migrate current documentation, prompts, policies, and test expectations",
            "depends_on": ["T-003"],
            "execution": "deterministic_codemod",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["identity_reference_tests", "prompt_policy_tests", "targeted_pytest"],
        },
        {
            "task_id": "T-005",
            "name": "Refactor runtime paths, configuration, and scripts",
            "depends_on": ["T-002", "T-003"],
            "execution": "deterministic_codemod",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["path_neutrality_tests", "shell_static_checks", "targeted_pytest"],
        },
        {
            "task_id": "T-006",
            "name": "Perform Python namespace and entry-point impact analysis",
            "depends_on": ["T-003"],
            "execution": "deterministic_ast_analysis",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["import_graph_validation", "entry_point_inventory"],
        },
        {
            "task_id": "T-007",
            "name": "Apply approved Python namespace and import migration",
            "depends_on": ["T-006"],
            "execution": "deterministic_codemod_with_exception_escalation",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["import_tests", "ruff", "mypy", "targeted_pytest"],
        },
        {
            "task_id": "T-008",
            "name": "Migrate portal branding, API metadata, and configuration",
            "depends_on": ["T-003", "T-004", "T-005"],
            "execution": "deterministic_codemod_with_exception_escalation",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["portal_contract_tests", "openapi_metadata_tests", "frontend_tests"],
        },
        {
            "task_id": "T-009",
            "name": "Migrate generated-application templates and current generated content",
            "depends_on": ["T-003", "T-004", "T-005"],
            "execution": "deterministic_regeneration_or_codemod",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["generated_application_tests", "mock_boundary_tests"],
        },
        {
            "task_id": "T-010",
            "name": "Migrate service, container, report, evidence, and handoff identity",
            "depends_on": ["T-004", "T-005", "T-007", "T-008", "T-009"],
            "execution": "deterministic_codemod",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["service_tests", "artifact_manifest_tests", "handoff_tests"],
        },
        {
            "task_id": "T-011",
            "name": "Validate arbitrary checkout directory and Linux portability",
            "depends_on": ["T-007", "T-008", "T-009", "T-010"],
            "execution": "deterministic",
            "llm_eligible": False,
            "protected_action": False,
            "validators": ["portable_checkout_replay", "full_regression", "evidence_review"],
        },
        {
            "task_id": "T-012",
            "name": "Perform human-approved local checkout rename",
            "depends_on": ["T-011"],
            "execution": "human_approved",
            "llm_eligible": False,
            "protected_action": True,
            "validators": ["local_rename_validation", "service_restart_validation"],
        },
        {
            "task_id": "T-013",
            "name": "Perform human-approved remote repository rename",
            "depends_on": ["T-011"],
            "execution": "human_approved",
            "llm_eligible": False,
            "protected_action": True,
            "validators": ["remote_configuration_validation", "recipient_replay"],
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "finding_classification_counts": dict(sorted(counts.items())),
        "llm_default": "disabled",
        "llm_exception_policy": "separate_explicit_authorization_required",
        "tasks": tasks,
        "edges": [
            {"from": dependency, "to": task["task_id"]}
            for task in tasks for dependency in task["depends_on"]
        ],
    }

def validation_matrix() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "stages": [
            {"order": 1, "name": "changed_file_syntax_and_schema", "mandatory": True},
            {"order": 2, "name": "targeted_unit_tests", "mandatory": True},
            {"order": 3, "name": "package_lint_and_type_checks", "mandatory": True},
            {"order": 4, "name": "package_integration_tests", "mandatory": True},
            {"order": 5, "name": "portal_and_runtime_contract_tests", "mandatory": True},
            {"order": 6, "name": "security_governance_path_checks", "mandatory": True},
            {"order": 7, "name": "full_ruff", "mandatory": True},
            {"order": 8, "name": "full_mypy", "mandatory": True},
            {"order": 9, "name": "full_pytest", "mandatory": True},
            {"order": 10, "name": "evidence_review", "mandatory": True},
            {
                "order": 11,
                "name": "recipient_replay",
                "mandatory": True,
                "release_boundary_only": True,
            },
        ],
    }

def protected_action_matrix() -> dict[str, Any]:
    protected_actions = [
        "apply_high_risk_patch",
        "commit",
        "compatibility_layer_removal",
        "destructive_delete",
        "destructive_overwrite",
        "governance_weakening",
        "live_provider_enablement",
        "local_checkout_rename",
        "merge",
        "production_deployment_authorization",
        "protected_policy_change",
        "push",
        "real_payment_integration_enablement",
        "release",
        "remote_repository_rename",
        "safety_weakening",
        "tag",
        "unrestricted_network_enablement",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "actions": [
            {"action": name, "human_approval_required": True}
            for name in protected_actions
        ],
    }

def markdown_report(
    root: Path, run_id: str, findings: list[Finding], task_graph: dict[str, Any],
    python_data: dict[str, Any], portal_data: dict[str, Any],
) -> str:
    by_class = Counter(item.classification for item in findings)
    by_category = Counter(item.category for item in findings)
    ambiguous = [item for item in findings if item.classification == "AMBIGUOUS"]
    unique_occurrences = {(item.path, item.line, item.matched_text) for item in findings}
    affected_files = {item.path for item in findings}
    lines = [
        "# Phase 46A Deterministic Transformation Plan",
        "",
        f"- Run ID: `{run_id}`",
        f"- Generated: `{utc_now()}`",
        f"- Repository evidence root: `{root}`",
        "- LLM calls: **0**",
        "- Product source rename performed: **No**",
        "- Physical checkout rename performed: **No**",
        "- Commit/merge/tag/push/release performed: **No**",
        "",
        "## Finding summary",
        "",
        f"- Raw pattern matches: **{len(findings)}**",
        f"- Unique source occurrences: **{len(unique_occurrences)}**",
        f"- Affected files: **{len(affected_files)}**",
        f"- Ambiguous findings: **{len(ambiguous)}**",
        f"- Python packages discovered: **{len(python_data['packages'])}**",
        f"- Python imports discovered: **{len(python_data['imports'])}**",
        f"- Portal files discovered: **{len(portal_data['portal_files'])}**",
        f"- Static portal routes discovered: **{len(portal_data['static_routes'])}**",
        "",
        "### By classification",
        "",
    ]
    for key, value in sorted(by_class.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "### By category", ""])
    for key, value in sorted(by_category.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Proposed task sequence", ""])
    for task in task_graph["tasks"]:
        dependencies = ", ".join(task["depends_on"]) or "none"
        lines.append(
            f"1. **{task['task_id']} — {task['name']}**  \n"
            f"   Dependencies: {dependencies}; execution: `{task['execution']}`; "
            f"protected: `{str(task['protected_action']).lower()}`."
        )
    lines.extend([
        "",
        "## Operator decision",
        "",
        "Review this plan and the machine-readable evidence before authorizing any "
        "identity, namespace, path, service, local checkout, or remote repository migration.",
        "",
        "The next permitted action is a bounded Phase 46B implementation plan. "
        "Protected Git and remote actions remain human-approved.",
        "",
    ])
    return "\n".join(lines)

def build_manifest(run_dir: Path) -> dict[str, Any]:
    files = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file() and path.name != "phase46a_evidence_manifest.json":
            files.append({
                "path": path.relative_to(run_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "llm_calls": 0,
        "files": files,
    }

def create_bundle(run_dir: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as archive:
        archive.add(run_dir, arcname=run_dir.name)

def execute_plan(root: Path) -> tuple[Path, Path]:
    root = root.resolve()
    if not (root / ".git").exists():
        try:
            git(root, "rev-parse", "--git-dir")
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f"Not a Git repository: {root}") from exc

    run_id = dt.datetime.now().strftime("phase46a-%Y%m%d-%H%M%S")
    run_dir = state_root() / "transformation_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    run_state = {
        "run_id": run_id,
        "schema_version": SCHEMA_VERSION,
        "status": "CREATED",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "current_stage": "BASELINE_VERIFIED",
        "llm_calls": 0,
        "evidence": [],
    }
    write_json(run_dir / "run.json", run_state)

    baseline = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": utc_now(),
        "branch": git(root, "branch", "--show-current"),
        "head": git(root, "rev-parse", "HEAD"),
        "status_porcelain": git(root, "status", "--porcelain").splitlines(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "llm_calls": 0,
    }
    write_json(run_dir / "baseline_report.json", baseline)

    run_state["status"] = "READ_ONLY_INVENTORY"
    run_state["current_stage"] = "READ_ONLY_INVENTORY"
    run_state["updated_at"] = utc_now()
    write_json(run_dir / "run.json", run_state)

    findings = scan_patterns(root)
    finding_payload = [asdict(item) for item in findings]
    write_json(run_dir / "finding_classification.json", {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "findings": finding_payload,
    })

    unique_occurrences = {
        (item.path, item.line, item.matched_text) for item in findings
    }
    unique_files = {item.path for item in findings}
    class_raw = Counter(item.classification for item in findings)
    class_unique = Counter(
        classification
        for _, _, _, classification in {
            (item.path, item.line, item.matched_text, item.classification)
            for item in findings
        }
    )
    write_json(run_dir / "finding_summary.json", {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "raw_pattern_matches": len(findings),
        "unique_source_occurrences": len(unique_occurrences),
        "affected_files": len(unique_files),
        "raw_by_classification": dict(sorted(class_raw.items())),
        "unique_by_classification": dict(sorted(class_unique.items())),
    })

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in findings:
        if item.category.startswith("IDENTITY_FACTORYFROMNOTHING"):
            grouped["factoryfromnothing_removal_inventory.json"].append(asdict(item))
        elif item.category.startswith("IDENTITY_"):
            grouped["legacy_name_inventory.json"].append(asdict(item))
        elif item.category.startswith("PATH_"):
            grouped["path_neutrality_inventory.json"].append(asdict(item))
        elif item.category.startswith("PORTABILITY_"):
            grouped["linux_portability_inventory.json"].append(asdict(item))
    for filename, items in grouped.items():
        write_json(run_dir / filename, {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "findings": items,
        })

    python_data = python_inventory(root)
    portal_data = portal_inventory(root)
    operational_data = operational_inventory(root)
    write_json(run_dir / "python_namespace_inventory.json", python_data)
    write_json(run_dir / "portal_inventory.json", portal_data)
    write_json(run_dir / "operational_inventory.json", operational_data)

    graph = create_task_graph(findings)
    write_json(run_dir / "transformation_task_graph.json", graph)
    write_json(run_dir / "validation_matrix.json", validation_matrix())
    write_json(run_dir / "protected_action_matrix.json", protected_action_matrix())
    write_json(run_dir / "llm_usage_report.json", {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "calls_permitted_by_this_execution": 0,
        "calls_attempted": 0,
        "calls_completed": 0,
        "calls_from_cache": 0,
        "tokens_used": 0,
        "estimated_cost": 0,
        "reason": "Deterministic analysis was sufficient and LLM mode remained disabled.",
    })

    report = markdown_report(root, run_id, findings, graph, python_data, portal_data)
    write_text(run_dir / "transformation_plan.md", report)

    run_state["status"] = "AWAITING_RUN_AUTHORIZATION"
    run_state["current_stage"] = "AWAITING_RUN_AUTHORIZATION"
    run_state["updated_at"] = utc_now()
    run_state["evidence"] = [
        path.relative_to(run_dir).as_posix()
        for path in sorted(run_dir.iterdir()) if path.is_file()
    ]
    write_json(run_dir / "run.json", run_state)

    manifest = build_manifest(run_dir)
    write_json(run_dir / "phase46a_evidence_manifest.json", manifest)

    destination = export_root() / f"{run_id}_review_bundle.tar.gz"
    create_bundle(run_dir, destination)
    return run_dir, destination

def command_status() -> int:
    runs = state_root() / "transformation_runs"
    if not runs.exists():
        print("No transformation runs found.")
        return 0
    run_files = sorted(runs.glob("*/run.json"), reverse=True)
    if not run_files:
        print("No transformation runs found.")
        return 0
    payload = json.loads(run_files[0].read_text(encoding="utf-8"))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="upi-app-factory")
    subparsers = parser.add_subparsers(dest="area", required=True)
    transform = subparsers.add_parser("transform")
    transform_sub = transform.add_subparsers(dest="action", required=True)
    plan = transform_sub.add_parser("plan")
    plan.add_argument("--project-root", default=".")
    transform_sub.add_parser("status")
    arguments = parser.parse_args(argv)

    if arguments.area == "transform" and arguments.action == "plan":
        run_dir, bundle = execute_plan(Path(arguments.project_root))
        print(f"Phase 46A plan created: {run_dir}")
        print(f"Review bundle: {bundle}")
        print("LLM calls: 0")
        return 0
    if arguments.area == "transform" and arguments.action == "status":
        return command_status()
    return 2

if __name__ == "__main__":
    raise SystemExit(main())