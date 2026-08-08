from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


IR_VERSION = "requirements-ir/v1"
CANONICAL_APP_ID = "upi_app_factory"
CANONICAL_NAME = "UPI App Factory"
REPOSITORY_ID = "upi_app_factory"
APP_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
ENTRY_PATTERN = re.compile(r"^\s*[-*]\s+(?P<body>.+?)\s*$")
SIMPLE_REQUIREMENT_PATTERN = re.compile(r"^\s*(?P<id>[A-Z]{2,10}-\d{3,5})\s*:\s*(?P<text>.+?)\s*$")
HEADING_PATTERN = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")

SUPPORTED_SECTIONS = {
    "actors": "actors",
    "use cases": "use_cases",
    "bounded contexts": "bounded_contexts",
    "commands": "commands",
    "queries": "queries",
    "events": "events",
    "aggregates": "aggregates",
    "invariants": "invariants",
    "workflows": "workflows",
    "apis": "apis",
    "api": "apis",
    "data": "data",
    "security": "security",
    "operations": "operations",
    "evidence": "evidence",
    "dependencies": "dependencies",
}
REQUIRED_COLLECTIONS = tuple(key for key in SUPPORTED_SECTIONS.values() if key != "dependencies")
FORBIDDEN_DEPENDENCIES = {
    "postgresql",
    "postgres",
    "mysql",
    "redis",
    "kafka",
    "rabbitmq",
    "elasticsearch",
    "kubernetes",
    "terraform",
    "docker",
    "sqlalchemy",
    "django orm",
    "orm",
}
AMBIGUITY_TERMS = ("tbd", "todo", "as needed", "best effort", "etc.", "later")


@dataclass(frozen=True)
class SourceLocation:
    source_id: str
    path: str
    line: int
    heading: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "path": self.path,
            "line": self.line,
            "heading": self.heading,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def parse_scalar(raw: str) -> Any:
    value = raw.strip().strip('"').strip("'")
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in inner.split(",")]
    return value


def parse_front_matter(text: str) -> tuple[dict[str, Any], int]:
    if not text.startswith("---\n"):
        return {}, 1
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, 1
    front_matter: dict[str, Any] = {}
    for line in text[4:end].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, raw = stripped.split(":", 1)
        front_matter[key.strip()] = parse_scalar(raw)
    return front_matter, text[: end + 5].count("\n") + 1


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def normalize_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").lower()


def parse_entry_body(body: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for part in body.split(";"):
        if ":" not in part:
            fields.setdefault("description", normalize_text(part))
            continue
        key, raw = part.split(":", 1)
        normalized_key = normalize_id(key)
        raw_value = raw.strip()
        if "," in raw_value and normalized_key in {"actors", "commands", "queries", "events", "depends_on", "permissions"}:
            fields[normalized_key] = [normalize_text(item) for item in raw_value.split(",") if item.strip()]
        else:
            fields[normalized_key] = parse_scalar(raw_value)
    return fields


def diagnostic(
    severity: str,
    code: str,
    message: str,
    location: SourceLocation | None,
    remediation: str,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "location": location.as_dict() if location else None,
        "remediation": remediation,
    }


def _source_id(relative_path: str) -> str:
    # Source identity must be independent of machine or clone location.
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:12]


def parse_markdown(path: Path, root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = path.as_posix()
    source_id = _source_id(relative)
    front_matter, body_start_line = parse_front_matter(text)
    collections: dict[str, list[dict[str, Any]]] = {name: [] for name in REQUIRED_COLLECTIONS}
    collections["dependencies"] = []
    diagnostics: list[dict[str, Any]] = []
    current_section = ""
    current_key = ""
    seen_ids: dict[str, SourceLocation] = {}
    in_structured_section = False

    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if index < body_start_line:
            continue
        heading = HEADING_PATTERN.match(line)
        if heading:
            current_section = normalize_text(heading.group("title")).lower()
            current_key = SUPPORTED_SECTIONS.get(current_section, "")
            in_structured_section = bool(current_key)
            continue
        loc = SourceLocation(source_id, relative, index, current_section)
        entry_match = ENTRY_PATTERN.match(line)
        if entry_match and in_structured_section:
            entry = parse_entry_body(entry_match.group("body"))
            if "id" not in entry:
                entry["id"] = f"{current_key}_{len(collections[current_key]) + 1:03d}"
                diagnostics.append(
                    diagnostic(
                        "error",
                        "REQ_MISSING_ID",
                        f"{current_section} entry is missing an explicit id.",
                        loc,
                        "Add a stable `id` field to the entry.",
                    )
                )
            entry_id = str(entry["id"])
            entry["id"] = entry_id
            entry["source"] = loc.as_dict()
            if entry_id in seen_ids:
                diagnostics.append(
                    diagnostic(
                        "error",
                        "REQ_DUPLICATE_ID",
                        f"Duplicate requirement id `{entry_id}`.",
                        loc,
                        "Use one globally unique id and update traceability references.",
                    )
                )
            else:
                seen_ids[entry_id] = loc
            if not any(key in entry for key in ("name", "title", "description", "path")):
                diagnostics.append(
                    diagnostic(
                        "error",
                        "REQ_MISSING_FIELD",
                        f"Entry `{entry_id}` is missing a name, title, description, or path.",
                        loc,
                        "Add a concise name/title and a testable description.",
                    )
                )
            collections[current_key].append(entry)
            continue
        simple = SIMPLE_REQUIREMENT_PATTERN.match(line)
        if simple:
            req_id = simple.group("id")
            entry = {
                "id": req_id,
                "description": normalize_text(simple.group("text")),
                "compatibility_import": True,
                "source": loc.as_dict(),
            }
            if req_id in seen_ids:
                diagnostics.append(
                    diagnostic(
                        "error",
                        "REQ_DUPLICATE_ID",
                        f"Duplicate simple requirement id `{req_id}`.",
                        loc,
                        "Use one globally unique id in the legacy requirements document.",
                    )
                )
            else:
                seen_ids[req_id] = loc
            collections["evidence"].append(entry)
        elif line.strip() and current_section and not in_structured_section and line.lstrip().startswith("-"):
            diagnostics.append(
                diagnostic(
                    "warning",
                    "REQ_UNSUPPORTED_SECTION",
                    f"Unsupported structured section `{current_section}` was ignored.",
                    loc,
                    "Move this content into a supported Phase 53 section.",
                )
            )

    return {
        "source_id": source_id,
        "path": relative,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "front_matter": front_matter,
        "collections": collections,
    }, diagnostics


def validate_semantics(ir: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    app = ir["application"]
    if app["product_name"] != CANONICAL_NAME or app["repository_id"] != REPOSITORY_ID:
        diagnostics.append(
            diagnostic(
                "critical",
                "REQ_APP_IDENTITY_MISMATCH",
                "Requirements must preserve UPI App Factory identity.",
                None,
                "Set product_name to UPI App Factory and repository_id to upi_app_factory.",
            )
        )
    if app["app_id"] != CANONICAL_APP_ID or not APP_ID_PATTERN.fullmatch(app["app_id"]):
        diagnostics.append(
            diagnostic(
                "critical",
                "REQ_INVALID_APP_ID",
                "Requirements app_id must be the canonical `upi_app_factory`.",
                None,
                "Use app_id: upi_app_factory in front matter.",
            )
        )
    for collection in REQUIRED_COLLECTIONS:
        if not ir["requirements"][collection]:
            diagnostics.append(
                diagnostic(
                    "error",
                    "REQ_EMPTY_COLLECTION",
                    f"Required collection `{collection}` is empty.",
                    None,
                    f"Add at least one structured `{collection}` entry.",
                )
            )

    all_text = _canonical_json(ir["requirements"]).lower()
    for term in AMBIGUITY_TERMS:
        if term in all_text:
            diagnostics.append(
                diagnostic(
                    "warning",
                    "REQ_AMBIGUITY",
                    f"Ambiguous term `{term}` appears in requirements.",
                    None,
                    "Replace ambiguous language with measurable acceptance criteria.",
                )
            )
    dependency_text = _canonical_json(ir["requirements"].get("dependencies", [])).lower() + all_text
    for dependency in sorted(FORBIDDEN_DEPENDENCIES):
        if dependency in dependency_text:
            diagnostics.append(
                diagnostic(
                    "error",
                    "REQ_UNSUPPORTED_DEPENDENCY",
                    f"Unsupported dependency `{dependency}` appears in requirements.",
                    None,
                    "Use standard-library SQLite and local deterministic adapters.",
                )
            )
    if "real_payment_calls" in all_text and "enabled" in all_text:
        diagnostics.append(
            diagnostic(
                "critical",
                "REQ_LIVE_PAYMENT_CONTRADICTION",
                "Requirements enable real payment calls despite governed mock-only controls.",
                None,
                "Keep real payment/provider calls disabled and model providers as fictional local adapters.",
            )
        )
    return diagnostics


def build_traceability(requirements: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for collection, entries in requirements.items():
        for entry in entries:
            rows.append(
                {
                    "requirement_id": entry["id"],
                    "collection": collection,
                    "source": entry.get("source"),
                    "canonical_hash": sha256_json(
                        {key: value for key, value in entry.items() if key != "source"}
                    ),
                }
            )
    return sorted(rows, key=lambda row: (row["collection"], row["requirement_id"]))


def compile_requirements(input_paths: Iterable[Path], root: Path | None = None) -> dict[str, Any]:
    project_root = root or Path.cwd()
    documents = []
    diagnostics: list[dict[str, Any]] = []
    merged: dict[str, list[dict[str, Any]]] = {name: [] for name in REQUIRED_COLLECTIONS}
    merged["dependencies"] = []
    front_matter: dict[str, Any] = {}

    for input_path in sorted(input_paths, key=lambda item: item.as_posix()):
        document, document_diagnostics = parse_markdown(input_path, project_root)
        diagnostics.extend(document_diagnostics)
        documents.append({key: document[key] for key in ("source_id", "path", "sha256", "front_matter")})
        for key, value in document["front_matter"].items():
            front_matter.setdefault(key, value)
        for key, entries in document["collections"].items():
            merged[key].extend(entries)

    ir: dict[str, Any] = {
        "ir_version": IR_VERSION,
        "application": {
            "app_id": str(front_matter.get("app_id", "")),
            "product_name": str(front_matter.get("product_name", "")),
            "repository_id": str(front_matter.get("repository_id", "")),
            "domain": str(front_matter.get("domain", "")),
            "runtime_llm_calls_default": int(front_matter.get("runtime_llm_calls_default", 0)),
            "real_payment_calls": str(front_matter.get("real_payment_calls", "disabled")),
            "data_policy": str(front_matter.get("data_policy", "")),
        },
        "source_documents": documents,
        "requirements": {
            key: sorted(value, key=lambda item: str(item.get("id", "")))
            for key, value in sorted(merged.items())
        },
        "normalization": {
            "case": "ids preserved, section names normalized to snake_case",
            "canonical_json": "UTF-8, sorted keys, compact separators",
            "hash_algorithm": "sha256",
        },
    }
    diagnostics.extend(validate_semantics(ir))
    ir["traceability"] = build_traceability(ir["requirements"])
    ir["diagnostics"] = sorted(diagnostics, key=lambda item: (item["severity"], item["code"], item["message"]))
    canonical_subject = {key: value for key, value in ir.items() if key not in {"diagnostics"}}
    ir["canonical_hash"] = sha256_json(canonical_subject)
    return ir


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def explain_ir(ir: dict[str, Any]) -> str:
    counts = {key: len(value) for key, value in ir["requirements"].items()}
    diag_counts: dict[str, int] = {}
    for item in ir["diagnostics"]:
        diag_counts[item["severity"]] = diag_counts.get(item["severity"], 0) + 1
    return "\n".join(
        [
            f"IR version: {ir['ir_version']}",
            f"Application: {ir['application']['app_id']} ({ir['application']['product_name']})",
            f"Canonical hash: {ir['canonical_hash']}",
            f"Collections: {json.dumps(counts, sort_keys=True)}",
            f"Diagnostics: {json.dumps(diag_counts, sort_keys=True)}",
            f"Traceability rows: {len(ir['traceability'])}",
        ]
    )


def has_blocking_diagnostics(ir: dict[str, Any]) -> bool:
    return any(item["severity"] in {"critical", "error"} for item in ir["diagnostics"])


def _input_paths(values: list[str]) -> list[Path]:
    paths = [Path(value) for value in values]
    missing = [path.as_posix() for path in paths if not path.is_file()]
    if missing:
        raise SystemExit(f"Requirement input not found: {', '.join(missing)}")
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic requirements IR compiler.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("compile", "validate", "explain"):
        command = sub.add_parser(name)
        command.add_argument("--input", nargs="+", required=True)
        command.add_argument("--project-root", type=Path, default=Path.cwd())
        command.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    ir = compile_requirements(_input_paths(parsed.input), parsed.project_root)
    if parsed.output:
        write_json(parsed.output, ir)
    if parsed.command == "compile":
        if not parsed.output:
            print(json.dumps(ir, indent=2, sort_keys=True))
        return 0
    if parsed.command == "explain":
        print(explain_ir(ir))
        return 1 if has_blocking_diagnostics(ir) else 0
    print(explain_ir(ir))
    if has_blocking_diagnostics(ir):
        print("Validation failed closed due to critical/error diagnostics.", file=sys.stderr)
        return 1
    print("Requirements compiler validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
