from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from tools.transformation_controller import phase46a

SCHEMA_VERSION = 1
DEFAULT_POLICY = Path("policies/identity_migration_policy.json")


class MigrationPlanningError(RuntimeError):
    """Raised when a deterministic migration-planning boundary is crossed."""


@dataclass(frozen=True)
class MigrationDecision:
    decision_id: str
    finding_id: str
    path: str
    line: int
    category: str
    classification: str
    decision: str
    rationale: str
    wave: str
    mutation_allowed: bool
    compatibility_required: bool
    requires_human_approval: bool


def canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_policy(root: Path) -> dict[str, Any]:
    path = root / DEFAULT_POLICY
    raw_policy: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_policy, dict):
        raise MigrationPlanningError(
            "Phase 46C policy must be a JSON object"
        )
    policy: dict[str, Any] = {
        str(key): value for key, value in raw_policy.items()
    }
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise MigrationPlanningError(
            "Unsupported Phase 46C policy schema"
        )
    llm_policy = policy.get("llm")
    if (
        not isinstance(llm_policy, dict)
        or llm_policy.get("enabled") is not False
        or llm_policy.get("allowed_calls") != 0
    ):
        raise MigrationPlanningError(
            "Phase 46C requires zero-LLM deterministic planning"
        )
    if policy.get("mode") != "planning_only":
        raise MigrationPlanningError(
            "Phase 46C must remain planning-only"
        )
    prohibited = policy.get("prohibited_actions")
    if not isinstance(prohibited, list) or not prohibited:
        raise MigrationPlanningError(
            "Phase 46C prohibited actions are required"
        )
    return policy


def normalized_relative(path_text: str) -> PurePosixPath:
    relative = PurePosixPath(path_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise MigrationPlanningError(
            f"Unsafe repository path: {path_text}"
        )
    return relative


def string_set(policy: dict[str, Any], key: str) -> set[str]:
    raw = policy.get(key)
    if not isinstance(raw, list):
        raise MigrationPlanningError(f"{key} must be a list")
    result: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            raise MigrationPlanningError(
                f"{key} entries must be strings"
            )
        result.add(item)
    return result


def path_has_prefix(path_text: str, prefixes: set[str]) -> bool:
    return any(
        path_text == prefix.rstrip("/")
        or path_text.startswith(prefix)
        for prefix in prefixes
    )


def decision_identifier(
    finding: phase46a.Finding,
    decision: str,
    wave: str,
) -> str:
    payload = (
        f"{finding.finding_id}|{finding.path}|{finding.line}|"
        f"{decision}|{wave}"
    )
    return f"D-{sha256_bytes(payload.encode('utf-8'))[:16]}"


def classify_finding(
    finding: phase46a.Finding,
    policy: dict[str, Any],
) -> MigrationDecision:
    normalized_relative(finding.path)
    generated_prefixes = string_set(
        policy,
        "generated_application_prefixes",
    )
    historical_classifications = string_set(
        policy,
        "historical_classifications",
    )
    technical_categories = string_set(
        policy,
        "technical_identity_categories",
    )
    display_categories = string_set(
        policy,
        "display_identity_categories",
    )
    path_categories = string_set(
        policy,
        "path_reference_categories",
    )

    if path_has_prefix(finding.path, generated_prefixes):
        decision = "EXCLUDE_GENERATED_APPLICATION"
        rationale = (
            "Generated application identity is independently governed and "
            "must not be changed by factory-identity migration."
        )
        wave = "W0"
        compatibility_required = False
        requires_human_approval = False
    elif finding.classification in historical_classifications:
        decision = "PRESERVE_HISTORICAL_EVIDENCE"
        rationale = (
            "Historical evidence remains immutable for provenance and audit."
        )
        wave = "W0"
        compatibility_required = False
        requires_human_approval = False
    elif finding.path.startswith("tests/"):
        decision = "PRESERVE_TEST_CONTRACT_AND_PLAN_UPDATE"
        rationale = (
            "Tests are contract evidence; update them only together with the "
            "governed contract and compatibility seam."
        )
        wave = "W1"
        compatibility_required = True
        requires_human_approval = False
    elif finding.category in technical_categories:
        decision = "ADD_COMPATIBILITY_ALIAS_BEFORE_MIGRATION"
        rationale = (
            "Technical identifiers require an additive compatibility alias "
            "before any namespace or import migration."
        )
        wave = "W3"
        compatibility_required = True
        requires_human_approval = False
    elif finding.category in display_categories:
        decision = "PLAN_CONTRACT_FIRST_DISPLAY_MIGRATION"
        rationale = (
            "Current display identity must be migrated with its validators, "
            "tests, documentation contracts, and rollback evidence."
        )
        wave = "W1"
        compatibility_required = True
        requires_human_approval = False
    elif finding.category in path_categories:
        decision = "PLAN_PATH_NEUTRALITY_MIGRATION"
        rationale = (
            "Path references must move to repository-relative or XDG-derived "
            "locations while preserving compatibility."
        )
        wave = "W2"
        compatibility_required = True
        requires_human_approval = False
    else:
        decision = "DETERMINISTIC_REVIEW_REQUIRED"
        rationale = (
            "The finding is retained for deterministic review because no "
            "approved migration catalog rule applies."
        )
        wave = "W0"
        compatibility_required = False
        requires_human_approval = False

    return MigrationDecision(
        decision_id=decision_identifier(finding, decision, wave),
        finding_id=finding.finding_id,
        path=finding.path,
        line=finding.line,
        category=finding.category,
        classification=finding.classification,
        decision=decision,
        rationale=rationale,
        wave=wave,
        mutation_allowed=False,
        compatibility_required=compatibility_required,
        requires_human_approval=requires_human_approval,
    )


def task_gate_decisions(
    task_graph: dict[str, Any],
) -> list[dict[str, Any]]:
    mapping = {
        "T-001": (
            "SATISFIED",
            "Canonical product identity registry already exists.",
            False,
        ),
        "T-002": (
            "SATISFIED",
            "Path-neutral policy and local state roots already exist.",
            False,
        ),
        "T-003": (
            "PLAN_COMPATIBILITY_SEAM",
            "Technical namespace migration requires additive aliases first.",
            False,
        ),
        "T-004": (
            "PLAN_CONTRACT_FIRST_MIGRATION",
            "Display identity changes require validators and tests together.",
            False,
        ),
        "T-005": (
            "PLAN_SERVICE_IDENTITY_WAVE",
            "Service and report identity require a bounded migration wave.",
            False,
        ),
        "T-006": (
            "DEFER_UNTIL_COMPATIBILITY_EXISTS",
            "Portable replay follows compatibility and path migration.",
            False,
        ),
        "T-007": (
            "HUMAN_GATE",
            "Checkout and remote repository rename remain human-only.",
            True,
        ),
    }
    decisions: list[dict[str, Any]] = []
    for task in task_graph["tasks"]:
        decision, rationale, protected = mapping.get(
            task["task_id"],
            (
                "DETERMINISTIC_REVIEW_REQUIRED",
                "No approved Phase 46C task rule applies.",
                bool(task["protected_action"]),
            ),
        )
        decisions.append(
            {
                "task_id": task["task_id"],
                "task_name": task["name"],
                "decision": decision,
                "rationale": rationale,
                "protected_action": (
                    protected
                    or bool(task["protected_action"])
                    or decision == "HUMAN_GATE"
                ),
                "mutation_allowed": False,
                "llm_eligible": False,
            }
        )
    return decisions


def build_migration_plan(
    findings: Sequence[phase46a.Finding],
    task_graph: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    max_findings = policy.get("max_findings")
    if not isinstance(max_findings, int) or max_findings < 1:
        raise MigrationPlanningError(
            "max_findings must be a positive integer"
        )
    if len(findings) > max_findings:
        raise MigrationPlanningError(
            f"Finding count {len(findings)} exceeds {max_findings}"
        )

    decisions = [
        classify_finding(finding, policy)
        for finding in sorted(
            findings,
            key=lambda item: (
                item.path,
                item.line,
                item.category,
                item.finding_id,
            ),
        )
    ]
    decision_counts: dict[str, int] = {}
    wave_counts: dict[str, int] = {}
    compatibility_count = 0
    for item in decisions:
        decision_counts[item.decision] = (
            decision_counts.get(item.decision, 0) + 1
        )
        wave_counts[item.wave] = wave_counts.get(item.wave, 0) + 1
        if item.compatibility_required:
            compatibility_count += 1

    waves = policy.get("migration_waves")
    aliases = policy.get("compatibility_aliases")
    human_gates = policy.get("human_gates")
    if not isinstance(waves, list):
        raise MigrationPlanningError("migration_waves must be a list")
    if not isinstance(aliases, list):
        raise MigrationPlanningError(
            "compatibility_aliases must be a list"
        )
    if not isinstance(human_gates, list):
        raise MigrationPlanningError("human_gates must be a list")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": phase46a.utc_now(),
        "phase": "46C",
        "mode": "planning_only",
        "status": "PLANNED",
        "finding_count": len(findings),
        "decision_count": len(decisions),
        "compatibility_required_count": compatibility_count,
        "decision_counts": dict(sorted(decision_counts.items())),
        "wave_counts": dict(sorted(wave_counts.items())),
        "decisions": [asdict(item) for item in decisions],
        "migration_waves": waves,
        "compatibility_aliases": aliases,
        "human_gates": human_gates,
        "task_gate_decisions": task_gate_decisions(task_graph),
        "mutation_allowed": False,
        "llm_calls": 0,
        "protected_actions_performed": [],
    }


def evidence_manifest(run_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if (
            path.is_file()
            and path.name != "phase46c_evidence_manifest.json"
        ):
            files.append(
                {
                    "path": path.relative_to(run_dir).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": phase46a.sha256_file(path),
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": phase46a.utc_now(),
        "phase": "46C",
        "llm_calls": 0,
        "files": files,
    }


def create_review_bundle(run_dir: Path) -> Path:
    destination = (
        phase46a.export_root() / f"{run_dir.name}_review_bundle.tar.gz"
    )
    phase46a.create_bundle(run_dir, destination)
    return destination


def create_plan(root: Path) -> tuple[Path, Path]:
    root = root.resolve()
    phase46a.git(root, "rev-parse", "--git-dir")
    branch = phase46a.git(root, "branch", "--show-current")
    if branch in {"", "main"}:
        raise MigrationPlanningError(
            "Phase 46C planning must run in an isolated non-main branch"
        )
    if phase46a.git(root, "diff", "--cached", "--name-only"):
        raise MigrationPlanningError(
            "Staged changes are not permitted during planning"
        )

    policy = load_policy(root)
    findings = phase46a.scan_patterns(root)
    task_graph = phase46a.create_task_graph(findings)
    plan = build_migration_plan(findings, task_graph, policy)

    run_id = dt.datetime.now().strftime("phase46c-%Y%m%d-%H%M%S")
    run_dir = phase46a.state_root() / "migration_plans" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    run = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "phase": "46C",
        "status": "PLANNED_AND_EVIDENCED",
        "branch": branch,
        "head": phase46a.git(root, "rev-parse", "HEAD"),
        "created_at": phase46a.utc_now(),
        "finding_count": plan["finding_count"],
        "decision_count": plan["decision_count"],
        "mutation_allowed": False,
        "llm_calls": 0,
        "protected_actions_performed": [],
    }
    phase46a.write_json(run_dir / "run.json", run)
    phase46a.write_json(
        run_dir / "identity_migration_plan.json",
        plan,
    )
    phase46a.write_json(
        run_dir / "compatibility_alias_snapshot.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": phase46a.utc_now(),
            "aliases": plan["compatibility_aliases"],
            "mutation_allowed": False,
        },
    )
    phase46a.write_json(
        run_dir / "task_gate_decisions.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": phase46a.utc_now(),
            "decisions": plan["task_gate_decisions"],
        },
    )
    plan_digest = sha256_bytes(
        canonical_json(
            json.loads(
                (run_dir / "identity_migration_plan.json").read_text(
                    encoding="utf-8"
                )
            )
        )
    )
    phase46a.write_json(
        run_dir / "plan_digest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "algorithm": "sha256-canonical-json",
            "digest": plan_digest,
        },
    )
    phase46a.write_json(
        run_dir / "phase46c_evidence_manifest.json",
        evidence_manifest(run_dir),
    )
    bundle = create_review_bundle(run_dir)
    return run_dir, bundle


def verify_plan(run_id: str) -> dict[str, Any]:
    run_dir = phase46a.state_root() / "migration_plans" / run_id
    if not run_dir.is_dir():
        raise MigrationPlanningError(
            f"Phase 46C run not found: {run_id}"
        )

    manifest = json.loads(
        (run_dir / "phase46c_evidence_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    mismatches: list[str] = []
    for item in manifest["files"]:
        path = run_dir / item["path"]
        if not path.is_file():
            mismatches.append(item["path"])
            continue
        if (
            path.stat().st_size != item["size"]
            or phase46a.sha256_file(path) != item["sha256"]
        ):
            mismatches.append(item["path"])
    if mismatches:
        raise MigrationPlanningError(
            f"Evidence mismatch count: {len(mismatches)}"
        )

    plan: object = json.loads(
        (run_dir / "identity_migration_plan.json").read_text(
            encoding="utf-8"
        )
    )
    digest_record = json.loads(
        (run_dir / "plan_digest.json").read_text(encoding="utf-8")
    )
    actual_digest = sha256_bytes(canonical_json(plan))
    if actual_digest != digest_record["digest"]:
        raise MigrationPlanningError("Migration plan digest mismatch")

    return {
        "status": "PASSED",
        "run_id": run_id,
        "evidence_files_verified": len(manifest["files"]),
        "plan_digest": actual_digest,
        "mutation_allowed": False,
        "llm_calls": 0,
    }


def latest_run_dir() -> Path | None:
    root = phase46a.state_root() / "migration_plans"
    if not root.exists():
        return None
    runs = sorted(
        (path for path in root.iterdir() if path.is_dir()),
        reverse=True,
    )
    return runs[0] if runs else None


def status(run_id: str | None) -> int:
    run_dir = (
        phase46a.state_root() / "migration_plans" / run_id
        if run_id
        else latest_run_dir()
    )
    if run_dir is None or not (run_dir / "run.json").is_file():
        print("No Phase 46C migration plans found.")
        return 0
    print((run_dir / "run.json").read_text(encoding="utf-8"), end="")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="upi-app-factory")
    subparsers = parser.add_subparsers(dest="area", required=True)
    transform = subparsers.add_parser("transform")
    actions = transform.add_subparsers(dest="action", required=True)

    plan_parser = actions.add_parser("plan-identity-migration")
    plan_parser.add_argument("--project-root", default=".")

    status_parser = actions.add_parser("migration-plan-status")
    status_parser.add_argument("--run-id")

    verify_parser = actions.add_parser("verify-migration-plan")
    verify_parser.add_argument("--run-id", required=True)

    arguments = parser.parse_args(argv)
    if arguments.action == "plan-identity-migration":
        run_dir, bundle = create_plan(Path(arguments.project_root))
        print(f"Phase 46C migration plan created: {run_dir}")
        print(f"Review bundle: {bundle}")
        print("Plan status: PLANNED_AND_EVIDENCED")
        print("Repository mutations performed: none")
        print("LLM calls: 0")
        return 0
    if arguments.action == "migration-plan-status":
        return status(arguments.run_id)
    if arguments.action == "verify-migration-plan":
        print(
            json.dumps(
                verify_plan(arguments.run_id),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

