from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any


DEBUG_PLAN_SCHEMA_VERSION = "upi-app-factory.debug-plan.v1"
FACTORY_PLAN_KIND = "factory"
GENERATED_PLAN_KIND = "generated_application"
REQUIRED_OBSERVABILITY_FIELDS = [
    "timestamp",
    "severity_text",
    "event_name",
    "service.name",
    "trace_id",
    "span_id",
    "trace_flags",
    "request_id",
    "correlation_id",
    "run_id",
    "app_id",
    "version_id",
    "duration_ms",
    "outcome",
]
STANDARD_REFERENCES = [
    "https://opentelemetry.io/docs/specs/otel/logs/data-model/",
    "https://opentelemetry.io/docs/specs/semconv/",
    "https://www.w3.org/TR/trace-context/",
    "https://www.rfc-editor.org/rfc/rfc9457",
    "https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html",
]
SECRET_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{16,}|"
    r"(?i:approval[_-]?token|api[_-]?key|secret|password)\s*[:=]\s*[A-Za-z0-9_./+=-]{12,}"
)
UNSAFE_ARG_RE = re.compile(r"[;&|`$<>]")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    plan_sha256: str


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_plan_sha256(plan: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json({key: value for key, value in plan.items() if key != "plan_sha256"}))


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _source_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _factory_source_paths(root: Path) -> list[str]:
    candidates = [
        "factory/operator_portal/local_web_api.py",
        "factory/operator_portal/debug_plan_api.py",
        "factory/operator_portal/documentation_api.py",
        "factory/operator_portal/web_ui/app.py",
        "factory/operator_portal/web_ui/static/index.html",
        "factory/operator_portal/web_ui/static/app.js",
        "factory/operator_portal/portfolio_api.py",
        "factory/operator_portal/runtime_api.py",
        "factory/operator_portal/browser_intake_orchestration.py",
        "factory/debugging/debug_plan.py",
        "factory/observability/structured_logging.py",
        "scripts/run_portal_requirements_driven_application_engineering.py",
        "scripts/build_operator_portal_exhaustive_ui_manifest.py",
        "scripts/build_factory_debug_plan.py",
        "scripts/validate_debug_plan.py",
        "scripts/build_factory_complete_documentation.py",
        "start_factory.sh",
        "stop_factory.sh",
    ]
    return [item for item in candidates if (root / item).is_file()]


def _openapi_routes(project_root: Path) -> list[dict[str, str]]:
    import sys

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from factory.operator_portal.web_ui.app import create_web_ui_app

    schema = create_web_ui_app(project_root=project_root).openapi()
    routes: list[dict[str, str]] = []
    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in path_item:
            if str(method).lower() in {"get", "post", "put", "patch", "delete"}:
                routes.append({"method": str(method).upper(), "path": str(path)})
    return sorted(routes, key=lambda item: (item["path"], item["method"]))


def _factory_state_machines() -> list[dict[str, Any]]:
    from factory.operator_portal.browser_intake_orchestration import VALID_TRANSITIONS

    transitions = [
        {"from": source, "to": target}
        for source, targets in VALID_TRANSITIONS.items()
        for target in sorted(targets)
    ]
    return [{"name": "browser_intake_run", "transitions": transitions}]


def _common_sections(*, app_id: str, version_id: str, requirements_sha256: str) -> dict[str, Any]:
    return {
        "architecture": {
            "style": "local deterministic FastAPI control surface",
            "trust_boundaries": [
                "operator browser to loopback portal",
                "portal to local workspace",
                "generated application to mocked payment ecosystem",
            ],
        },
        "end_to_end_flows": [
            {
                "name": "requirements_to_generated_application",
                "steps": [
                    "validate requirements",
                    "create run",
                    "generate deterministic plan",
                    "record run-scoped approval",
                    "execute local generator",
                    "validate gates",
                    "publish catalogue registration",
                    "download source and evidence archives",
                ],
            }
        ],
        "failure_taxonomy": [
            {"code": "validation_rejected", "description": "requirements, identity, command, or route contract rejected"},
            {"code": "approval_stale", "description": "approval subject no longer matches requirements or plan hash"},
            {"code": "generation_failed_closed", "description": "deterministic generator failed before a GO decision"},
        ],
        "observability": {
            "required_fields": REQUIRED_OBSERVABILITY_FIELDS,
            "redaction": "secret and PII-like fields are redacted by structured logging contracts",
            "standards": STANDARD_REFERENCES,
        },
        "diagnostic_workflows": [
            {
                "trigger": "operator run does not reach SUCCEEDED/GO",
                "prerequisites": ["loopback portal running", "run_id available", "real payments disabled"],
                "ordered_steps": [
                    ["python", "scripts/validate_debug_plan.py", "--plan", "evidence/debug_plan.json"],
                    ["python", "-m", "pytest", "-q"],
                    ["python", "scripts/build_operator_portal_exhaustive_ui_manifest.py", "--project-root", ".", "--output", "/tmp/operator_portal_ui_manifest.json"],
                ],
                "expected_signals": ["plan hash validates", "pytest returns 0", "manifest status PASS"],
                "failure_signals": ["plan hash drift", "missing route", "missing state transition", "unsafe command"],
                "evidence": ["evidence/debug_plan.json", "generation_manifest.json", "structured JSON logs"],
                "rollback": ["stop local runtime", "discard generated workspace candidate"],
                "escalation": ["human operator reviews evidence bundle"],
            }
        ],
        "symptom_matrix": [
            {
                "symptom": "download missing debug plan",
                "probable_causes": ["stale generated manifest", "generation interrupted before evidence write"],
                "checks": ["inspect generation_manifest.json", "validate evidence/debug_plan.json"],
                "evidence": ["generation_manifest.json", "evidence/debug_plan.json"],
                "safe_actions": [["python", "scripts/validate_debug_plan.py", "--plan", "evidence/debug_plan.json"]],
                "escalation": ["regenerate under a new approved run"],
            }
        ],
        "evidence_map": {
            "debug_plan": "evidence/debug_plan.json",
            "debug_plan_text": "docs/DEBUG_PLAN.md",
            "requirements_sha256": requirements_sha256,
        },
        "safety_boundaries": {
            "real_payment_calls": "disabled",
            "runtime_llm_calls": 0,
            "certification_claimed": False,
        },
        "rollback": {
            "commands": [["python", "-m", "pytest", "-q"]],
            "policy": "rollback only local generated workspace artifacts; do not merge, tag, push, deploy, or call live providers",
        },
        "escalation": {
            "owner": "operator",
            "criteria": ["secret leakage finding", "route drift", "state transition drift", "requirements identity drift"],
        },
        "validation_provenance": {
            "app_id": app_id,
            "version_id": version_id,
            "requirements_sha256": requirements_sha256,
            "validator": "scripts/validate_debug_plan.py",
        },
    }


def build_factory_debug_plan(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    source_files = [_source_record(root, relative) for relative in _factory_source_paths(root)]
    requirements_sha256 = (
        sha256_file(root / "requirements/master_consolidated_requirements.md")
        if (root / "requirements/master_consolidated_requirements.md").is_file()
        else "unavailable"
    )
    plan: dict[str, Any] = {
        "schema_version": DEBUG_PLAN_SCHEMA_VERSION,
        "plan_kind": FACTORY_PLAN_KIND,
        "app_id": "upi_app_factory",
        "version_id": "factory-source",
        "run_id": "factory-debug-plan",
        "requirements_sha256": requirements_sha256,
        "entrypoint": "factory.operator_portal.web_ui.app:create_web_ui_app",
        "source_files": source_files,
        "routes": _openapi_routes(root),
        "state_machines": _factory_state_machines(),
        "commands": [
            {
                "name": "build_factory_debug_plan",
                "argv": ["python", "scripts/build_factory_debug_plan.py", "--project-root", ".", "--json-out", "/tmp/factory_debug_plan.json", "--text-out", "/tmp/factory_debug_plan.md"],
                "expected_signals": ["schema_version upi-app-factory.debug-plan.v1", "plan_sha256 present"],
                "failure_signals": ["non-zero exit", "hash drift"],
            },
            {
                "name": "validate_factory_debug_plan",
                "argv": ["python", "scripts/validate_debug_plan.py", "--plan", "/tmp/factory_debug_plan.json", "--project-root", "."],
                "expected_signals": ["valid true"],
                "failure_signals": ["missing route", "missing state transition", "source hash drift"],
            },
        ],
        **_common_sections(app_id="upi_app_factory", version_id="factory-source", requirements_sha256=requirements_sha256),
    }
    plan["plan_sha256"] = canonical_plan_sha256(plan)
    return plan


def _generated_routes(app_id: str) -> list[dict[str, str]]:
    return [
        {"method": "GET", "path": "/health"},
        {"method": "GET", "path": "/ready"},
        {"method": "GET", "path": "/runtime/health"},
        {"method": "GET", "path": "/capabilities"},
        {"method": "POST", "path": "/scenario/echo"},
        {"method": "GET", "path": "/missing"},
        {"method": "POST", "path": "/v1/disputes"},
        {"method": "GET", "path": "/v1/disputes/{dispute_id}"},
    ]


def build_generated_application_debug_plan(
    app_root: Path,
    *,
    app_id: str,
    version_id: str,
    run_id: str,
    requirements_sha256: str,
    requirements_path: str = "requirements.md",
    source_commit: str | None = None,
) -> dict[str, Any]:
    root = app_root.resolve()
    source_relatives = [
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    source_files = [_source_record(root, relative) for relative in source_relatives]
    plan: dict[str, Any] = {
        "schema_version": DEBUG_PLAN_SCHEMA_VERSION,
        "plan_kind": GENERATED_PLAN_KIND,
        "app_id": app_id,
        "version_id": version_id,
        "run_id": run_id,
        "requirements_sha256": requirements_sha256,
        "requirements_path": requirements_path,
        "entrypoint": f"app.{app_id}.interfaces.api.main:app",
        "source_commit": source_commit or "unavailable",
        "source_files": source_files,
        "routes": _generated_routes(app_id),
        "domain_flow": [
            "POST /v1/disputes validates fictional dispute request",
            "idempotency key returns existing dispute on replay",
            "GET /v1/disputes/{dispute_id} returns stored local dispute or 404",
        ],
        "state_machines": [
            {
                "name": "generated_dispute_case",
                "transitions": [
                    {"from": "new", "to": "received"},
                    {"from": "received", "to": "under_review"},
                    {"from": "under_review", "to": "resolved"},
                ],
            }
        ],
        "logs": {
            "startup": "generated_application.startup",
            "shutdown": "generated_application.shutdown",
            "request": "http.request.completed",
        },
        "commands": [
            {
                "name": "run_tests",
                "argv": ["python", "-m", "pytest", "-q"],
                "expected_signals": ["exit code 0"],
                "failure_signals": ["pytest failure", "import error", "route contract mismatch"],
            },
            {
                "name": "serve_local",
                "argv": ["python", "-m", "uvicorn", f"app.{app_id}.interfaces.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
                "expected_signals": ["GET /health returns ok", "GET /ready reports real_payment_calls disabled"],
                "failure_signals": ["non-loopback bind", "real payment boundary not disabled"],
            },
        ],
        **_common_sections(app_id=app_id, version_id=version_id, requirements_sha256=requirements_sha256),
    }
    plan["plan_sha256"] = canonical_plan_sha256(plan)
    return plan


def render_debug_plan_markdown(plan: dict[str, Any]) -> str:
    routes = "\n".join(f"- {route['method']} {route['path']}" for route in plan["routes"])
    transitions = "\n".join(
        f"- {machine['name']}: {transition['from']} -> {transition['to']}"
        for machine in plan["state_machines"]
        for transition in machine["transitions"]
    )
    commands = "\n".join(
        f"- {command['name']}: `{' '.join(command['argv'])}`"
        for command in plan["commands"]
    )
    return (
        f"# Debug Plan\n\n"
        f"Schema: {plan['schema_version']}\n\n"
        f"Plan kind: {plan['plan_kind']}\n\n"
        f"Application: {plan['app_id']}\n\n"
        f"Version/run: {plan['version_id']} / {plan['run_id']}\n\n"
        f"Requirements SHA-256: {plan['requirements_sha256']}\n\n"
        f"Plan SHA-256: {plan['plan_sha256']}\n\n"
        "## Routes\n\n"
        f"{routes}\n\n"
        "## State Machines\n\n"
        f"{transitions}\n\n"
        "## Diagnostics\n\n"
        f"{commands}\n"
    )


def write_generated_application_debug_plan(
    app_root: Path,
    *,
    app_id: str,
    version_id: str,
    run_id: str,
    requirements_sha256: str,
    source_commit: str | None = None,
) -> dict[str, Any]:
    plan = build_generated_application_debug_plan(
        app_root,
        app_id=app_id,
        version_id=version_id,
        run_id=run_id,
        requirements_sha256=requirements_sha256,
        source_commit=source_commit,
    )
    evidence_path = app_root / "evidence" / "debug_plan.json"
    docs_path = app_root / "docs" / "DEBUG_PLAN.md"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    docs_path.write_text(render_debug_plan_markdown(plan), encoding="utf-8")
    return plan


def _expected_factory_routes(root: Path) -> set[tuple[str, str]]:
    return {(route["method"], route["path"]) for route in _openapi_routes(root)}


def _expected_generated_routes() -> set[tuple[str, str]]:
    return {(route["method"], route["path"]) for route in _generated_routes("app")}


def validate_debug_plan(plan_path: Path, *, project_root: Path | None = None, app_root: Path | None = None) -> ValidationResult:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ValidationResult(False, ["plan must be a JSON object"], "")
    if plan.get("schema_version") != DEBUG_PLAN_SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    actual_sha = canonical_plan_sha256(plan)
    if plan.get("plan_sha256") != actual_sha:
        errors.append("plan_sha256 drift")
    root = (project_root or app_root or plan_path.parent).resolve()
    if plan.get("plan_kind") == GENERATED_PLAN_KIND:
        root = (app_root or plan_path.parents[1]).resolve()
        app_id = str(plan.get("app_id", ""))
        if not app_id or not (root / "app" / app_id / "interfaces" / "api" / "main.py").is_file():
            errors.append("wrong app identity")
        requirements_path = root / str(plan.get("requirements_path", "requirements.md"))
        if requirements_path.is_file() and plan.get("requirements_sha256") != sha256_file(requirements_path):
            errors.append("requirements identity drift")
        routes = {(item.get("method"), item.get("path")) for item in plan.get("routes", [])}
        missing = sorted(_expected_generated_routes() - routes)
        if missing:
            errors.append("route inventory drift: " + repr(missing[:5]))
        expected_transitions = {("new", "received"), ("received", "under_review"), ("under_review", "resolved")}
        observed_transitions = {
            (transition.get("from"), transition.get("to"))
            for machine in plan.get("state_machines", [])
            for transition in machine.get("transitions", [])
        }
        if expected_transitions - observed_transitions:
            errors.append("state-machine inventory drift")
    elif plan.get("plan_kind") == FACTORY_PLAN_KIND:
        root = (project_root or Path.cwd()).resolve()
        routes = {(item.get("method"), item.get("path")) for item in plan.get("routes", [])}
        missing = sorted(_expected_factory_routes(root) - routes)
        if missing:
            errors.append("route inventory drift: " + repr(missing[:5]))
        expected_transitions = {
            (transition["from"], transition["to"])
            for machine in _factory_state_machines()
            for transition in machine["transitions"]
        }
        observed_transitions = {
            (transition.get("from"), transition.get("to"))
            for machine in plan.get("state_machines", [])
            for transition in machine.get("transitions", [])
        }
        if expected_transitions - observed_transitions:
            errors.append("state-machine inventory drift")
    for source in plan.get("source_files", []):
        path = root / str(source.get("path", ""))
        if not path.is_file() or source.get("sha256") != sha256_file(path):
            errors.append(f"source hash drift: {source.get('path')}")
    for route in plan.get("routes", []):
        if set(route) != {"method", "path"}:
            errors.append("route entries must use {method,path}")
    for machine in plan.get("state_machines", []):
        for transition in machine.get("transitions", []):
            if set(transition) != {"from", "to"}:
                errors.append("state transitions must use {from,to}")
    for field in REQUIRED_OBSERVABILITY_FIELDS:
        if field not in plan.get("observability", {}).get("required_fields", []):
            errors.append(f"missing observability field: {field}")
    safety = plan.get("safety_boundaries", {})
    if safety.get("real_payment_calls") != "disabled" or safety.get("runtime_llm_calls") != 0 or safety.get("certification_claimed") is not False:
        errors.append("safety boundary mismatch")
    text = json.dumps(plan, sort_keys=True)
    if SECRET_RE.search(text):
        errors.append("secret-like material leaked into plan")
    for command in plan.get("commands", []):
        argv = command.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            errors.append("command argv must be a non-empty string array")
            continue
        if any(UNSAFE_ARG_RE.search(item) for item in argv):
            errors.append("unsafe command argument detected")
    return ValidationResult(not errors, errors, actual_sha)
