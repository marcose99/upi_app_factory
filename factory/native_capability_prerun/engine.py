from __future__ import annotations

from factory.evidence_portability import portable_json_dumps

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
from typing import Any, Final, Mapping, Sequence, cast

from typing import TypeGuard


def _is_string_list(value: object) -> TypeGuard[list[str]]:
    """Narrow a configuration value through runtime evidence."""
    return isinstance(value, list) and all(
        isinstance(item, str) for item in value
    )


def _require_string_list(value: object) -> list[str]:
    """Fail closed unless a configuration value is a string list."""
    if not _is_string_list(value):
        raise TypeError("expected a list of strings")
    return value


def _require_int_value(value: object) -> int:
    """Fail closed unless a configuration value is already an integer."""
    if not isinstance(value, int):
        raise TypeError("expected an integer")
    return value



CLASSIFICATIONS: Final[set[str]] = {
    "FULFILLABLE",
    "PARTIALLY_FULFILLABLE",
    "NOT_FULFILLABLE_FACTORY_GAP",
    "NOT_FULFILLABLE_ENVIRONMENT_GAP",
    "NOT_FULFILLABLE_EXTERNAL_DEPENDENCY",
    "NOT_FULFILLABLE_REQUIREMENTS_AMBIGUITY",
    "NOT_FULFILLABLE_GOVERNANCE_BOUNDARY",
    "NOT_APPLICABLE",
}
MANDATORY_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(shall|must|required|mandatory|prohibited|fail(?:s|ed|ing)? closed)\b",
    re.IGNORECASE,
)
LIST_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^(?:[-*]|\u2022|\d+[.)])\s+")
APP_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
KEY_VALUE_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*:\s+\S.*$")
NON_OBLIGATION_FRONTMATTER_KEYS: Final[set[str]] = {
    "app_id",
    "product_name",
    "repository_id",
    "domain",
    "inherits",
    "journey_stage",
    "official_reference_ids",
    "regulatory_profile",
    "requirement_id",
    "scenario_family",
    "scenario_id",
    "scenario_number",
    "severity_default",
    "target_application_id",
}
DEFAULT_SCHEMA_VERSION: Final[str] = "native-capability-prerun.v1"
GO_DECISION: Final[str] = "PROVEN_100_PERCENT_CAPABILITY"
NO_GO_DECISION: Final[str] = "NO_GO_WITH_IMPROVEMENT_REQUIREMENTS"
ARTIFACT_NAMES: Final[tuple[str, ...]] = (
    "CAPABILITY_PRE_RUN_REPORT.json",
    "CAPABILITY_PRE_RUN_REPORT.md",
    "REQUIREMENT_CAPABILITY_MATRIX.json",
    "REQUIREMENT_CAPABILITY_MATRIX.md",
    "FACTORY_IMPROVEMENT_REQUIREMENTS.json",
    "FACTORY_IMPROVEMENT_REQUIREMENTS.md",
    "FACTORY_IMPROVEMENT_PLAN.json",
    "FACTORY_IMPROVEMENT_PLAN.md",
    "PRE_RUN_MANIFEST.json",
    "PRE_RUN_SHA256SUMS",
)
AUTOMATED_TEST_EVIDENCE_TYPES: Final[set[str]] = {
    "unit_test",
    "integration_test",
    "regression_test",
    "negative_test",
    "security_test",
    "end_to_end_test",
}
EXPLICIT_PROOF_MODES: Final[set[str]] = {
    "exact_text",
    "source_requirement_id",
    "source_requirement_name",
}


class NativeCapabilityError(RuntimeError):
    """Fail-closed native capability error."""


@dataclass(frozen=True)
class PreRunConfig:
    requirements_document: Path
    application_id: str
    output_root: Path
    factory_root: Path
    expected_requirements_sha256: str | None = None
    run_id: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def portable_requirements_path(requirements: Path, factory_root: Path, requirements_sha: str) -> str:
    try:
        resolved_requirements = requirements.resolve()
        resolved_root = factory_root.resolve()
    except OSError:
        resolved_requirements = requirements.absolute()
        resolved_root = factory_root.absolute()
    if resolved_requirements == resolved_root:
        return "."
    if resolved_requirements.is_relative_to(resolved_root):
        return resolved_requirements.relative_to(resolved_root).as_posix()
    return f"external_requirements/{requirements_sha}/{resolved_requirements.name}"


def canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    return sha256_bytes(portable_json_dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def validate_application_id(value: str) -> str:
    if not APP_ID_RE.fullmatch(value) or value in {".", ".."} or "/" in value or "\\" in value:
        raise NativeCapabilityError("application id must be lowercase snake_case and path-safe")
    return value


def safe_resolved_file(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if path.is_symlink() or resolved.is_symlink():
        raise NativeCapabilityError(f"{label} must not be a symlink")
    if not resolved.is_file():
        raise NativeCapabilityError(f"{label} is not a file: {resolved}")
    return resolved


def safe_output_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if path.exists() and resolved.is_symlink():
        raise NativeCapabilityError("output root must not be a symlink")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, portable_json_dumps(payload, indent=2, sort_keys=True) + "\n")


def git_identity(factory_root: Path) -> dict[str, Any]:
    def run_git(args: Sequence[str]) -> str:
        completed = subprocess.run(
            ["git", "-C", str(factory_root), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        return completed.stdout.strip() if completed.returncode == 0 else ""

    head = os.getenv("UPI_APP_FACTORY_SOURCE_COMMIT") or run_git(["rev-parse", "HEAD"])
    branch = run_git(["branch", "--show-current"]) or "unknown"
    status = run_git(["status", "--short"])
    diff_name = run_git(["diff", "--name-only"])
    return {
        "head": head if re.fullmatch(r"[0-9a-f]{40}", head) else "unavailable",
        "branch": branch,
        "dirty": bool(status),
        "status_sha256": sha256_bytes(status.encode("utf-8")),
        "diff_name_only_sha256": sha256_bytes(diff_name.encode("utf-8")),
    }


def extract_text(requirements_document: Path) -> dict[str, Any]:
    data = requirements_document.read_bytes()
    suffix = requirements_document.suffix.lower()
    if suffix in {".md", ".txt", ".rst"}:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NativeCapabilityError("requirements text document must be UTF-8") from exc
        return {
            "text": text.replace("\r\n", "\n").replace("\r", "\n"),
            "extractor": "native_utf8_text_loader",
            "extractor_version": "1",
            "extraction_status": "extracted",
        }
    if suffix == ".pdf":
        binary = shutil.which(os.getenv("UPI_APP_FACTORY_PDF_TEXT_EXTRACTOR", "pdftotext"))
        if not binary:
            raise NativeCapabilityError("PDF requirements need local pdftotext extractor")
        completed = subprocess.run(
            [binary, "-layout", str(requirements_document), "-"],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            raise NativeCapabilityError("PDF text extraction failed closed")
        version = subprocess.run(
            [binary, "-v"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        version_text = (version.stderr or version.stdout).strip().splitlines()
        return {
            "text": completed.stdout.replace("\r\n", "\n").replace("\r", "\n"),
            "extractor": str(Path(binary).name),
            "extractor_path_sha256": sha256_bytes(str(Path(binary).resolve()).encode("utf-8")),
            "extractor_version": version_text[0] if version_text else "unknown",
            "extraction_status": "extracted",
        }
    raise NativeCapabilityError(f"unsupported requirements document type: {suffix or '<none>'}")


def _plain_atomic_clauses(text: str) -> list[str]:
    if (
        text.endswith(":")
        and len(text.split()) <= 12
        and not re.search(r"\b(shall|must|required|permitted|requires|retain only|contain)\b", text, re.IGNORECASE)
    ):
        return []
    return _sentence_level_clauses(text)


def _sentence_level_clauses(text: str) -> list[str]:
    clauses: list[str] = []
    for sentence in re.split(r"(?<=[.!?;])\s+", text):
        normalized = sentence.strip(" \t;:,.")
        if len(normalized) >= 3:
            clauses.append(normalized)
    return clauses


CONJUNCTION_STOPWORDS: Final[set[str]] = {
    "a",
    "all",
    "an",
    "and",
    "any",
    "as",
    "at",
    "before",
    "by",
    "can",
    "cannot",
    "could",
    "each",
    "every",
    "for",
    "from",
    "if",
    "in",
    "it",
    "its",
    "may",
    "must",
    "no",
    "not",
    "of",
    "on",
    "or",
    "shall",
    "should",
    "that",
    "the",
    "their",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "when",
    "which",
    "will",
    "with",
    "without",
}


def _split_prefix(prefix: str, value: str) -> list[str]:
    parts = [part.strip(" \t;:,.") for part in re.split(r"\s+(?:and|or)\s+", value)]
    return [f"{prefix} {part}".strip() for part in parts if part and part.lower() not in {"and", "or"}]


def _comma_enumeration_parts(text: str) -> list[str] | None:
    if text.count(",") < 1:
        return None
    normalized = re.sub(r",\s+(and|or)\s+", ", ", text)
    parts = [part.strip(" \t;:,.") for part in normalized.split(",")]
    parts = [part for part in parts if part and part.lower() not in {"and", "or"}]
    if len(parts) < 2:
        return None
    negative_prefixes = ("perform no", "do not", "must not", "shall not", "never", "without")
    lowered = parts[0].lower()
    for prefix in negative_prefixes:
        if lowered.startswith(prefix + " "):
            first_value = parts[0][len(prefix):].strip()
            items = [first_value, *parts[1:]]
            return [f"{prefix} {item}".strip() for item in items if item]
    return parts


def _short_conjunction_parts(text: str) -> list[str] | None:
    if "," in text or re.search(r"\bone or more\b", text, re.IGNORECASE):
        return None
    negative_prefixes = ("perform no", "do not", "must not", "shall not", "never", "without")
    lowered = text.lower()
    for prefix in negative_prefixes:
        if lowered.startswith(prefix + " "):
            remainder = text[len(prefix):].strip()
            parts = _split_prefix(prefix, remainder)
            return parts if len(parts) >= 2 else None
    imperative = re.match(r"^(?P<prefix>[A-Za-z][A-Za-z0-9_/-]*)\s+(?P<rest>.+)$", text)
    if imperative:
        prefix = imperative.group("prefix")
        rest = imperative.group("rest")
        if (
            len(text.split()) <= 18
            and prefix.lower() not in CONJUNCTION_STOPWORDS
            and not rest.lower().startswith(("and ", "or "))
        ):
            parts = _split_prefix(prefix, imperative.group("rest"))
            return parts if len(parts) >= 2 else None
    if len(text.split()) > 8:
        return None
    parts = [part.strip(" \t;:,.") for part in re.split(r"\s+(?:and|or)\s+", text)]
    parts = [part for part in parts if part and part.lower() not in {"and", "or"}]
    return parts if len(parts) >= 2 else None


def _leading_pair_prefix_parts(text: str) -> list[str] | None:
    if "," in text or len(text.split()) > 18:
        return None
    match = re.match(
        r"^(?P<first>[A-Za-z][A-Za-z0-9_-]*)\s+"
        r"(?P<join>and|or)\s+"
        r"(?P<second>[A-Za-z][A-Za-z0-9_-]*)\s+"
        r"(?P<rest>.+)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    first = match.group("first")
    second = match.group("second")
    if first.lower() in CONJUNCTION_STOPWORDS or second.lower() in CONJUNCTION_STOPWORDS:
        return None
    rest = match.group("rest").strip(" \t;:,.")
    if not rest:
        return None
    return [f"{first} {rest}", f"{second} {rest}"]


def _slash_compound_parts(text: str) -> list[str] | None:
    match = re.search(r"\b([A-Za-z][A-Za-z0-9_-]*(?:/[A-Za-z][A-Za-z0-9_-]*)+)\b", text)
    if not match:
        return None
    if (match.start() > 0 and text[match.start() - 1] == "`") or (
        match.end() < len(text) and text[match.end()] == "`"
    ):
        return None
    token = match.group(1)
    components = [component for component in token.split("/") if component]
    if len(components) < 2:
        return None
    prefix = text[:match.start()].strip()
    suffix = text[match.end():].strip()
    return [
        " ".join(part for part in (prefix, component, suffix) if part).strip(" \t;:,.")
        for component in components
    ]


def _expand_atomic_fragments(text: str) -> list[str]:
    def _expand_parts(parts: list[str]) -> list[str]:
        expanded: list[str] = []
        for part in parts:
            expanded.extend(_expand_atomic_fragments(part))
        return expanded

    comma_parts = _comma_enumeration_parts(text)
    if comma_parts:
        return _expand_parts(comma_parts)
    slash_parts = _slash_compound_parts(text)
    if slash_parts:
        return _expand_parts(slash_parts)
    pair_prefix_parts = _leading_pair_prefix_parts(text)
    if pair_prefix_parts:
        return _expand_parts(pair_prefix_parts)
    conjunction_parts = _short_conjunction_parts(text)
    if conjunction_parts:
        return _expand_parts(conjunction_parts)
    return [text]


def iter_logical_lines(text: str) -> list[tuple[int, str]]:
    logical_lines: list[tuple[int, str]] = []
    current_start = 0
    current_text = ""
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            if current_text:
                logical_lines.append((current_start, current_text))
                current_text = ""
            continue
        if stripped == "---" or stripped.startswith("#") or LIST_PREFIX_RE.match(stripped):
            if current_text:
                logical_lines.append((current_start, current_text))
            current_start = line_number
            current_text = stripped
            if stripped == "---" or stripped.startswith("#"):
                logical_lines.append((current_start, current_text))
                current_text = ""
            continue
        if KEY_VALUE_LINE_RE.fullmatch(stripped):
            if current_text:
                logical_lines.append((current_start, current_text))
            logical_lines.append((line_number, stripped))
            current_text = ""
            continue
        if current_text and not current_text.endswith((".", "!", "?", ";")):
            current_text = f"{current_text} {stripped}"
            continue
        if current_text:
            logical_lines.append((current_start, current_text))
        current_start = line_number
        current_text = stripped
    if current_text:
        logical_lines.append((current_start, current_text))
    return logical_lines


def _structured_field_map(text: str) -> dict[str, str]:
    field_map: dict[str, str] = {}
    for field in text.split(";"):
        key, separator, value = field.partition(":")
        if not separator:
            continue
        normalized_key = key.strip().lower()
        normalized_value = value.strip()
        if normalized_value:
            field_map[normalized_key] = normalized_value
    return field_map


def _frontmatter_clauses(line: str) -> list[str]:
    key, separator, value = line.partition(":")
    if not separator:
        return []
    normalized_key = key.strip().casefold()
    normalized_value = value.strip()
    if not normalized_key or not normalized_value:
        return []
    if normalized_key in NON_OBLIGATION_FRONTMATTER_KEYS:
        return []
    return [f"{normalized_key}: {normalized_value}"]


def _structured_atomic_clauses(field_map: Mapping[str, str]) -> list[str]:
    clauses: list[str] = []
    name = field_map.get("name", "")
    description_clauses = _plain_atomic_clauses(field_map.get("description", ""))
    clauses.extend(description_clauses)
    if name:
        clauses.extend(f"{name}: {clause}" for clause in description_clauses)
    actors = field_map.get("actors", "")
    if actors:
        for actor in [part.strip() for part in actors.split(",") if part.strip()]:
            clauses.append(f"actor {actor}")
            if name:
                clauses.append(f"{name} actor {actor}")
    method = field_map.get("method", "")
    if method:
        clauses.append(f"HTTP method {method}")
        if name:
            clauses.append(f"{name} HTTP method {method}")
    path = field_map.get("path", "")
    if path:
        clauses.append(f"API path {path}")
        if name:
            clauses.append(f"{name} API path {path}")
    if clauses:
        return clauses
    fallback_fields = [field_map[key] for key in ("path", "name") if field_map.get(key)]
    field_values: list[str] = []
    for value in fallback_fields:
        field_values.extend(_sentence_level_clauses(value))
    return field_values


def split_atomic_clauses(line: str) -> list[str]:
    clean = LIST_PREFIX_RE.sub("", line.strip())
    clean = re.sub(r"\s+", " ", clean)
    if not clean or clean.startswith("#"):
        return []
    if clean.startswith("id:") and ";" in clean:
        field_map = _structured_field_map(clean)
        structured_clauses = _structured_atomic_clauses(field_map)
        if structured_clauses:
            return structured_clauses
    return _plain_atomic_clauses(clean)


def _append_obligation(
    obligations: list[dict[str, Any]],
    *,
    clause: str,
    line_number: int,
    keywords: list[str],
    clause_metadata: Mapping[str, Any] | None = None,
) -> None:
    digest = sha256_bytes(f"{line_number}:{clause}".encode("utf-8"))[:12]
    obligations.append(
        {
            "id": f"REQ-{len(obligations) + 1:04d}",
            "source_location": {"line": line_number, "fingerprint": digest},
            "text": clause,
            "mandatory": True,
            "keywords": keywords or ["atomic_requirement"],
            **(dict(clause_metadata or {})),
        }
    )


def inventory_obligations(text: str, *, application_id: str | None = None) -> list[dict[str, Any]]:
    obligations: list[dict[str, Any]] = []
    fallback_candidates: list[dict[str, Any]] = []
    in_mandatory_section = False
    in_frontmatter = False
    for line_number, line in iter_logical_lines(text):
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            for clause in _frontmatter_clauses(stripped):
                if application_id and clause == application_id:
                    continue
                _append_obligation(
                    obligations,
                    clause=clause,
                    line_number=line_number,
                    keywords=["atomic_requirement"],
                    clause_metadata=None,
                )
            continue
        if stripped.startswith("#"):
            in_mandatory_section = bool(MANDATORY_RE.search(stripped))
            continue
        if stripped.endswith(":") and not re.match(r"^([-*]|\d+[.)])\s+", stripped):
            if MANDATORY_RE.search(stripped):
                in_mandatory_section = True
            continue
        inherited_mandatory = in_mandatory_section and bool(LIST_PREFIX_RE.match(stripped))
        if not stripped:
            continue
        normalized_line = LIST_PREFIX_RE.sub("", stripped)
        clause_metadata: dict[str, Any] = {}
        clauses = split_atomic_clauses(line)
        if not clauses:
            continue
        if normalized_line.startswith("id:") and ";" in normalized_line:
            field_map = _structured_field_map(normalized_line)
            source_requirement_id = field_map.get("id")
            source_requirement_name = field_map.get("name")
            if source_requirement_id:
                clause_metadata["source_requirement_id"] = source_requirement_id
            if source_requirement_name:
                clause_metadata["source_requirement_name"] = source_requirement_name
        structured_requirement = bool(clause_metadata)
        line_is_obligation = (
            inherited_mandatory
            or bool(MANDATORY_RE.search(normalized_line))
            or structured_requirement
        )
        for clause in clauses:
            # The externally bound application id is intake metadata, not a capability obligation.
            if application_id and clause == application_id:
                continue
            keywords = sorted({item.lower() for item in MANDATORY_RE.findall(clause)})
            if not keywords and inherited_mandatory:
                keywords = ["inherited_required_section"]
            candidate = {
                "line_number": line_number,
                "clause": clause,
                "keywords": keywords or ["atomic_requirement"],
                "clause_metadata": dict(clause_metadata),
            }
            if line_is_obligation:
                _append_obligation(
                    obligations,
                    clause=clause,
                    line_number=line_number,
                    keywords=_require_string_list(candidate["keywords"]),
                    clause_metadata=clause_metadata,
                )
            else:
                fallback_candidates.append(candidate)
    if not obligations:
        for candidate in fallback_candidates:
            _append_obligation(
                obligations,
                clause=str(candidate["clause"]),
                line_number=_require_int_value(candidate["line_number"]),
                keywords=cast(list[str], candidate["keywords"]),
                clause_metadata=cast(Mapping[str, Any], candidate["clause_metadata"]),
            )
    if not obligations:
        raise NativeCapabilityError("no mandatory atomic obligations were detected")
    return obligations


def default_capability_catalogue(factory_root: Path) -> list[dict[str, Any]]:
    configured = factory_root / "config" / "native_capability" / "catalogue.json"
    if configured.is_file():
        payload = json.loads(configured.read_text(encoding="utf-8"))
        entries = payload.get("capabilities") if isinstance(payload, dict) else None
        if isinstance(entries, list):
            return [cast(dict[str, Any], item) for item in entries if isinstance(item, dict)]
    return [
        {
            "id": "CAP-MOCK-SAFETY",
            "patterns": ["mock", "live", "external", "provider", "payment", "bank", "rail", "npci"],
            "paths": ["scripts/run_portal_requirements_driven_application_engineering.py"],
        }
    ]


def evidence_reference(factory_root: Path, relative_path: str, capability_id: str) -> dict[str, Any]:
    return _evidence_reference(
        factory_root,
        relative_path,
        capability_id=capability_id,
        factory_commit=git_identity(factory_root)["head"],
        evidence_type="implementation_or_test",
    )


def _evidence_reference(
    factory_root: Path,
    relative_path: str,
    *,
    capability_id: str,
    factory_commit: str,
    evidence_type: str,
    cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cached = cache.get(relative_path) if cache is not None else None
    if cached is None:
        path = factory_root / relative_path
        exists = path.is_file()
        cached = {
            "path": relative_path,
            "factory_commit": factory_commit,
            "verification_status": "PASS" if exists else "MISSING",
            "verified": exists,
            "sha256": sha256_file(path) if exists else None,
        }
        if cache is not None:
            cache[relative_path] = cached
    return {**cached, "type": evidence_type, "capability_id": capability_id}


def _capability_match(obligation: Mapping[str, Any], capability: Mapping[str, Any]) -> dict[str, Any] | None:
    matched_by: list[dict[str, str]] = []
    source_requirement_id = obligation.get("source_requirement_id")
    if isinstance(source_requirement_id, str):
        configured_ids = capability.get("source_requirement_ids", [])
        if isinstance(configured_ids, list):
            for candidate in configured_ids:
                if isinstance(candidate, str) and candidate == source_requirement_id:
                    matched_by.append({"kind": "source_requirement_id", "value": candidate})
        configured_prefixes = capability.get("source_requirement_prefixes", [])
        if isinstance(configured_prefixes, list):
            for prefix in configured_prefixes:
                if isinstance(prefix, str) and source_requirement_id.startswith(prefix):
                    matched_by.append({"kind": "source_requirement_prefix", "value": prefix})

    source_requirement_name = obligation.get("source_requirement_name")
    if isinstance(source_requirement_name, str):
        configured_names = capability.get("source_requirement_names", [])
        if isinstance(configured_names, list):
            normalized_name = source_requirement_name.casefold()
            for candidate in configured_names:
                if isinstance(candidate, str) and candidate.casefold() == normalized_name:
                    matched_by.append({"kind": "source_requirement_name", "value": candidate})

    exact_texts = capability.get("exact_texts", [])
    if isinstance(exact_texts, list):
        obligation_text = str(obligation["text"]).casefold()
        for candidate in exact_texts:
            if isinstance(candidate, str) and candidate.casefold() == obligation_text:
                matched_by.append({"kind": "exact_text", "value": candidate})

    normalized = str(obligation["text"]).lower()
    patterns = capability.get("patterns", [])
    if isinstance(patterns, list):
        for pattern in patterns:
            if isinstance(pattern, str) and pattern.lower() in normalized:
                matched_by.append({"kind": "text_pattern", "value": pattern})

    if not matched_by:
        return None

    proof_mode = matched_by[0]["kind"]
    return {
        "proof_mode": proof_mode,
        "matched_by": matched_by,
        "capability_id": str(capability.get("id", "CAP-UNKNOWN")),
        "capability_description": str(capability.get("description", "")),
    }


def _capability_evidence(
    capability: Mapping[str, Any],
    *,
    factory_root: Path,
    factory_commit: str,
    evidence_cache: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    evidence_entries = capability.get("evidence")
    if isinstance(evidence_entries, list):
        for entry in evidence_entries:
            if not isinstance(entry, Mapping):
                continue
            path = entry.get("path")
            if not isinstance(path, str):
                continue
            evidence_type = str(entry.get("type", "implementation_or_test"))
            references.append(
                _evidence_reference(
                    factory_root,
                    path,
                    capability_id=str(capability.get("id", "CAP-UNKNOWN")),
                    factory_commit=factory_commit,
                    evidence_type=evidence_type,
                    cache=evidence_cache,
                )
            )
    if references:
        return references
    paths = capability.get("paths", [])
    if isinstance(paths, list):
        for relative in paths:
            if isinstance(relative, str):
                references.append(
                    _evidence_reference(
                        factory_root,
                        relative,
                        capability_id=str(capability.get("id", "CAP-UNKNOWN")),
                        factory_commit=factory_commit,
                        evidence_type="implementation_or_test",
                        cache=evidence_cache,
                    )
                )
    return references


def _proof_mode_priority(value: str | None) -> int:
    return {
        "exact_text": 5,
        "source_requirement_id": 4,
        "source_requirement_name": 3,
        "source_requirement_prefix": 2,
        "text_pattern": 1,
    }.get(value or "", 0)


def _partition_evidence(
    evidence: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    implementation: list[dict[str, Any]] = []
    automated_tests: list[dict[str, Any]] = []
    additional: list[dict[str, Any]] = []
    for reference in evidence:
        evidence_type = str(reference.get("type", ""))
        copied = dict(reference)
        if evidence_type == "implementation":
            implementation.append(copied)
        elif evidence_type in AUTOMATED_TEST_EVIDENCE_TYPES:
            automated_tests.append(copied)
        else:
            additional.append(copied)
    return implementation, automated_tests, additional


def evaluated_obligation(
    obligation: Mapping[str, Any],
    *,
    classification: str,
    fulfillable: bool,
    reason: str,
    evidence: Sequence[Mapping[str, Any]],
    proof_mode: str | None = None,
    matched_by: Sequence[Mapping[str, str]] = (),
    matched_capabilities: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    source_location = obligation.get("source_location")
    source_locator = dict(source_location) if isinstance(source_location, Mapping) else source_location
    normalized_reason = reason.strip()
    return {
        **obligation,
        "classification": classification,
        "fulfillable": fulfillable,
        "reason": normalized_reason,
        "reasons": [normalized_reason] if normalized_reason else [],
        "source_locator": source_locator,
        "source_text": str(obligation["text"]),
        "proof_mode": proof_mode,
        "matched_by": [dict(item) for item in matched_by],
        "matched_capabilities": [dict(item) for item in matched_capabilities],
        "evidence": [dict(reference) for reference in evidence],
    }


def classify_obligation(
    obligation: Mapping[str, Any],
    *,
    capabilities: Sequence[Mapping[str, Any]],
    factory_root: Path,
    factory_commit: str,
    evidence_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    text = str(obligation["text"])
    normalized = text.lower()
    if re.search(r"\bignore\b.{0,50}\b(instructions|rules|policy)\b", normalized):
        return evaluated_obligation(
            obligation,
            classification="NOT_FULFILLABLE_GOVERNANCE_BOUNDARY",
            fulfillable=False,
            reason="Prompt-injection-like governance override text cannot be fulfilled.",
            evidence=[],
        )
    authorised_real_world_verification = (
        re.search(r"\bbefore\s+any\s+real(?:-world)?\s+implementation\b", normalized)
        and re.search(r"\bauthori[sz]ed\b.{0,100}\bowner\b", normalized)
        and re.search(r"\b(?:must\s+)?verif(?:y|ies|ied|ication)\b", normalized)
    )
    independent_real_world_verification = (
        re.search(r"\b(?:obligations?|requirements?)\b.{0,80}\b(?:confirm(?:ed)?|verif(?:y|ied))\b", normalized)
        and re.search(r"\bindependent(?:ly)?\b", normalized)
        and re.search(r"\b(?:before|prior to)\b.{0,80}\b(?:real(?:-world)? (?:implementation|deployment)|production)\b", normalized)
    )
    if authorised_real_world_verification or independent_real_world_verification:
        return evaluated_obligation(
            obligation,
            classification="NOT_FULFILLABLE_GOVERNANCE_BOUNDARY",
            fulfillable=False,
            reason=(
                "Independent regulatory or compliance verification is an authorised-human "
                "governance gate for real-world transition; local mock generation cannot claim it."
            ),
            evidence=[],
        )
    dependency_language = (
        r"\b(access|calls?|connect(?:ion|ivity)?|integrat(?:e|ion)|providers?|banks?|payments?|"
        r"rails?|npci|psp|sockets?|dns|https?)\b"
    )
    denial_terms = (
        r"(?:deny|denies|denied|forbid|forbids|forbidden|prohibit|prohibits|prohibited|"
        r"block|blocks|blocked|disable|disables|disabled|must not|shall not|never|"
        r"request|requests|requested|requesting|attempt|attempts|attempted|attempting|"
        r"reject|rejects|rejected|rejecting)"
    )
    dependency_terms = (
        r"(?:access|calls?|connect(?:ion|ivity)?|integrat(?:e|ion)|providers?|banks?|payments?|"
        r"rails?|upi|npci|psp|sockets?|dns|https?|processing|interactions?|actions?|data)"
    )
    negative_access_pattern = (
        rf"(?:\b{denial_terms}\b.{{0,100}}\b{dependency_terms}\b|"
        rf"\b{dependency_terms}\b.{{0,60}}\b{denial_terms}\b|"
        rf"\b(?:live|real)[- ]?{dependency_terms}\b.{{0,40}}\brequested\b|"
        rf"\bno\b.{{0,40}}\b(?:live|real)\b|"
        rf"\bwithout(?: performing)?\b.{{0,40}}\b(?:live|real)[- ]?{dependency_terms}\b)"
    )
    positive_access_action = (
        r"(?:connect|call|use|access|integrate|send|require|invoke|contact|reach|perform|"
        r"process|execute|initiate|transmit)\w*"
    )
    independent_action_start = (
        rf"(?:(?:the|this|that|our|an?|a)\s+(?:app|application|system|service|workflow|"
        rf"factory|runtime)\s+)?(?:(?:must|shall|should|will|may|can|to)\s+)?"
        rf"{positive_access_action}"
    )
    access_clauses = [
        clause.strip()
        for clause in re.split(
            rf"(?:[;.!?]|\b(?:but|however|then|while)\b|"
            rf",(?=\s*{independent_action_start}\b)|"
            rf"\band\b(?=\s*{independent_action_start}\b))",
            normalized,
        )
        if clause.strip()
    ]
    unnegated_live_dependency = any(
        re.search(dependency_language, clause)
        and re.search(r"\b(?:real|live)\b", clause)
        and not re.search(negative_access_pattern, clause)
        for clause in access_clauses
    )
    if unnegated_live_dependency:
        return evaluated_obligation(
            obligation,
            classification="NOT_FULFILLABLE_EXTERNAL_DEPENDENCY",
            fulfillable=False,
            reason="The obligation requires a live external dependency outside the mock-only boundary.",
            evidence=[],
        )

    matched_candidates: list[dict[str, Any]] = []
    verified_candidates: list[dict[str, Any]] = []
    for capability in capabilities:
        match = _capability_match(obligation, capability)
        if match is not None:
            capability_refs = _capability_evidence(
                capability,
                factory_root=factory_root,
                factory_commit=factory_commit,
                evidence_cache=evidence_cache,
            )
            candidate = {
                "priority": _proof_mode_priority(str(match["proof_mode"])),
                "proof_mode": str(match["proof_mode"]),
                "matched_by": cast(list[dict[str, str]], match["matched_by"]),
                "capability": {
                    "id": match["capability_id"],
                    "description": match["capability_description"],
                },
                "evidence": capability_refs,
                "explicit_requirement_trace": str(match["proof_mode"]) in EXPLICIT_PROOF_MODES,
                "proof_complete": bool(_partition_evidence(capability_refs)[0]) and bool(_partition_evidence(capability_refs)[1]),
            }
            matched_candidates.append(candidate)
            if capability_refs and all(ref["verification_status"] == "PASS" for ref in capability_refs):
                verified_candidates.append(candidate)

    if verified_candidates:
        best_priority = max(candidate["priority"] for candidate in verified_candidates)
        selected = [candidate for candidate in verified_candidates if candidate["priority"] == best_priority]
        explicit_trace = all(bool(candidate["explicit_requirement_trace"]) for candidate in selected)
        proof_complete = all(bool(candidate["proof_complete"]) for candidate in selected)
        combined_evidence = [
            reference for candidate in selected for reference in cast(list[dict[str, Any]], candidate["evidence"])
        ]
        matched_by = [
            match_entry
            for candidate in selected
            for match_entry in cast(list[dict[str, str]], candidate["matched_by"])
        ]
        matched_capabilities = [cast(dict[str, Any], candidate["capability"]) for candidate in selected]
        if explicit_trace and proof_complete:
            return evaluated_obligation(
                obligation,
                classification="FULFILLABLE",
                fulfillable=True,
                reason="Exact obligation mapping includes current implementation and automated-test evidence.",
                evidence=combined_evidence,
                proof_mode=str(selected[0]["proof_mode"]) if selected else None,
                matched_by=matched_by,
                matched_capabilities=matched_capabilities,
            )
        gaps: list[str] = []
        if not explicit_trace:
            gaps.append("The current match is not bound to the exact obligation text or requirement identifier.")
        if not proof_complete:
            gaps.append("Both implementation and automated-test evidence are required for a truthful 100% claim.")
        return evaluated_obligation(
            obligation,
            classification="PARTIALLY_FULFILLABLE",
            fulfillable=False,
            reason=" ".join(gaps),
            evidence=combined_evidence,
            proof_mode=str(selected[0]["proof_mode"]) if selected else None,
            matched_by=matched_by,
            matched_capabilities=matched_capabilities,
        )
    if matched_candidates:
        best_priority = max(candidate["priority"] for candidate in matched_candidates)
        selected = [candidate for candidate in matched_candidates if candidate["priority"] == best_priority]
        return evaluated_obligation(
            obligation,
            classification="NOT_FULFILLABLE_FACTORY_GAP",
            fulfillable=False,
            reason="Matched capability evidence is missing or stale.",
            evidence=[reference for candidate in selected for reference in cast(list[dict[str, Any]], candidate["evidence"])],
            proof_mode=str(selected[0]["proof_mode"]) if selected else None,
            matched_by=[
                match_entry
                for candidate in selected
                for match_entry in cast(list[dict[str, str]], candidate["matched_by"])
            ],
            matched_capabilities=[cast(dict[str, Any], candidate["capability"]) for candidate in selected],
        )
    if "ambiguous" in normalized or "as applicable" in normalized:
        classification = "NOT_FULFILLABLE_REQUIREMENTS_AMBIGUITY"
        reason = "The requirement is ambiguous without owner clarification."
    else:
        classification = "NOT_FULFILLABLE_FACTORY_GAP"
        reason = "No current version-bound executable capability evidence matched this obligation."
    return evaluated_obligation(
        obligation,
        classification=classification,
        fulfillable=False,
        reason=reason,
        evidence=[],
        proof_mode=None,
        matched_by=[],
        matched_capabilities=[],
    )


def build_improvement_items(
    evaluated: Sequence[Mapping[str, Any]],
    *,
    application_id: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    non_fulfillable = [item for item in evaluated if item.get("fulfillable") is not True]
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    group_order: list[str] = []
    for item in non_fulfillable:
        group_key = str(item.get("source_requirement_id") or item["id"])
        if group_key not in grouped:
            grouped[group_key] = []
            group_order.append(group_key)
        grouped[group_key].append(item)

    for index, group_key in enumerate(group_order, start=1):
        group = grouped[group_key]
        item = group[0]
        classification = str(item["classification"])
        owner = {
            "NOT_FULFILLABLE_ENVIRONMENT_GAP": "environment",
            "NOT_FULFILLABLE_EXTERNAL_DEPENDENCY": "external dependency owner",
            "NOT_FULFILLABLE_REQUIREMENTS_AMBIGUITY": "requirements owner",
            "NOT_FULFILLABLE_GOVERNANCE_BOUNDARY": "governance authority",
        }.get(classification, "factory")
        blocked_requirement_ids = [str(entry["id"]) for entry in group]
        blocked_source_ids = list(
            dict.fromkeys(
                str(entry.get("source_requirement_id") or entry["id"])
                for entry in group
            )
        )
        root_causes = list(dict.fromkeys(str(entry["reason"]) for entry in group))
        blocked_target = blocked_source_ids[0]
        items.append(
            {
                "id": f"FAC-IMP-{index:03d}",
                "normative_requirement": (
                    f"UPI App Factory SHALL provide current executable evidence or owner-attributed "
                    f"closure for {blocked_target} before engineering {application_id}."
                ),
                "blocked_requirement_ids": blocked_requirement_ids,
                "blocked_source_requirement_ids": blocked_source_ids,
                "root_cause": " ".join(root_causes),
                "attribution": classification,
                "affected_factory_layers": [
                    "requirements intake",
                    "capability catalogue",
                    "application-engineering gate",
                    "evidence validation",
                ],
                "candidate_paths": [
                    "factory/native_capability_prerun/",
                    "config/native_capability/",
                    "tests/test_phase49a_browser_driven_intake_orchestration.py",
                ],
                "priority": "P0" if classification.endswith("FACTORY_GAP") else "P1",
                "risk": "high" if classification.endswith("GOVERNANCE_BOUNDARY") else "medium",
                "dependencies": [],
                "implementation_wave": 1,
                "acceptance_criteria": [
                    "The blocked obligation is inventoried with stable identity.",
                    "Current evidence path, commit identity, verification status, and checksum are recorded.",
                    "The pre-run remains NO_GO until the obligation is FULFILLABLE.",
                ],
                "required_tests": {
                    "unit": True,
                    "integration": True,
                    "regression": True,
                    "negative": True,
                    "security": classification.endswith("GOVERNANCE_BOUNDARY"),
                    "end_to_end": True,
                },
                "required_evidence": [
                    "updated capability catalogue entry",
                    "passing executable test evidence",
                    "pre-run before/after capability delta",
                ],
                "definition_of_done": "A later native pre-run proves the obligation FULFILLABLE without weakening governance.",
                "prohibited_shortcuts": [
                    "Do not mark fulfillable from LLM claims alone.",
                    "Do not skip, delete, or weaken tests.",
                    "Do not bypass mock-only or human-gated boundaries.",
                ],
                "owner_category": owner,
            }
        )
    return items


def build_requirement_matrix_item(
    item: Mapping[str, Any],
    *,
    improvements: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    evidence = [dict(reference) for reference in cast(Sequence[Mapping[str, Any]], item["evidence"])]
    implementation_evidence, automated_test_evidence, additional_evidence = _partition_evidence(evidence)
    explicit_trace = str(item.get("proof_mode") or "") in EXPLICIT_PROOF_MODES
    return {
        "id": item["id"],
        "requirement_id": item["id"],
        "source_requirement_id": item.get("source_requirement_id"),
        "source_requirement_name": item.get("source_requirement_name"),
        "source_location": item["source_location"],
        "source_locator": item["source_locator"],
        "text": item["text"],
        "source_text": item["source_text"],
        "text_sha256": sha256_bytes(str(item["text"]).encode("utf-8")),
        "classification": item["classification"],
        "fulfillable": item["fulfillable"],
        "mandatory": item.get("mandatory", True),
        "reason": item["reason"],
        "reasons": item["reasons"],
        "proof_mode": item.get("proof_mode"),
        "matched_by": item.get("matched_by", []),
        "matched_capabilities": item.get("matched_capabilities", []),
        "evidence": evidence,
        "proof_trace": {
            "explicit_requirement_binding": explicit_trace,
            "implementation_evidence": implementation_evidence,
            "automated_test_evidence": automated_test_evidence,
            "additional_evidence": additional_evidence,
            "requirement_to_code_and_test_complete": explicit_trace
            and bool(implementation_evidence)
            and bool(automated_test_evidence),
        },
        "improvement_ids": [
            improvement["id"]
            for improvement in improvements
            if item["id"] in improvement["blocked_requirement_ids"]
        ],
    }


def markdown_table(rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    rendered = []
    for index, row in enumerate(rows):
        rendered.append("| " + " | ".join(value.ljust(widths[column]) for column, value in enumerate(row)) + " |")
        if index == 0:
            rendered.append("| " + " | ".join("-" * widths[column] for column in range(len(row))) + " |")
    return "\n".join(rendered) + "\n"


def render_report_md(report: Mapping[str, Any]) -> str:
    rows = [["ID", "Classification", "Fulfillable", "Reason"]]
    for item in cast(list[dict[str, Any]], report["obligations"]):
        rows.append([str(item["id"]), str(item["classification"]), str(item["fulfillable"]), str(item["reason"])])
    return (
        "# Capability Pre-Run Report\n\n"
        f"- Application ID: {report['application_id']}\n"
        f"- Decision: {report['decision']}\n"
        f"- Requirements SHA-256: {report['requirements_sha256']}\n"
        f"- Atomic obligations: {report['obligation_count']}\n\n"
        + markdown_table(rows)
    )


def render_matrix_md(matrix: Mapping[str, Any]) -> str:
    items = cast(list[dict[str, Any]], matrix["items"])
    rows = [["Requirement", "Primary Classification", "Fulfillable", "Evidence Count"]]
    for item in items:
        rows.append(
            [
                str(item["requirement_id"]),
                str(item["classification"]),
                str(item["fulfillable"]),
                str(len(cast(list[Any], item.get("evidence", [])))),
            ]
        )
    return (
        "# Requirement Capability Matrix\n\n"
        f"- Application ID: {matrix['application_id']}\n"
        f"- Decision: {matrix['decision']}\n"
        f"- Requirements SHA-256: {matrix['requirements_sha256']}\n"
        f"- Atomic obligations: {matrix.get('atomic_obligation_count', matrix.get('obligation_count', len(items)))}\n\n"
        + markdown_table(rows)
    )


def render_improvements_md(payload: Mapping[str, Any]) -> str:
    lines = ["# Factory Improvement Requirements", ""]
    for item in cast(list[dict[str, Any]], payload["items"]):
        lines.extend(
            [
                f"## {item['id']}",
                "",
                str(item["normative_requirement"]),
                "",
                f"- Owner: {item['owner_category']}",
                f"- Blocks: {', '.join(cast(list[str], item['blocked_requirement_ids']))}",
                f"- Source requirements: {', '.join(cast(list[str], item.get('blocked_source_requirement_ids', [])))}",
                f"- Root cause: {item['root_cause']}",
                "",
            ]
        )
    if not payload["items"]:
        lines.append("No improvements are required by the current pre-run.")
    return "\n".join(lines) + "\n"


def render_plan_md(payload: Mapping[str, Any]) -> str:
    rows = [["Wave", "Improvement", "Priority", "Owner"]]
    for step in cast(list[dict[str, Any]], payload["implementation_steps"]):
        step_id = step.get("id", step.get("improvement_id", ""))
        rows.append([str(step["wave"]), str(step_id), str(step["priority"]), str(step["owner_category"])])
    return "# Factory Improvement Plan\n\n" + markdown_table(rows)


def write_artifacts(output_root: Path, payloads: Mapping[str, Any]) -> dict[str, str]:
    paths: dict[str, Path] = {
        "CAPABILITY_PRE_RUN_REPORT.json": output_root / "CAPABILITY_PRE_RUN_REPORT.json",
        "REQUIREMENT_CAPABILITY_MATRIX.json": output_root / "REQUIREMENT_CAPABILITY_MATRIX.json",
        "FACTORY_IMPROVEMENT_REQUIREMENTS.json": output_root / "FACTORY_IMPROVEMENT_REQUIREMENTS.json",
        "FACTORY_IMPROVEMENT_PLAN.json": output_root / "FACTORY_IMPROVEMENT_PLAN.json",
        "PRE_RUN_MANIFEST.json": output_root / "PRE_RUN_MANIFEST.json",
    }
    for name, path in paths.items():
        atomic_write_json(path, cast(Mapping[str, Any], payloads[name]))
    atomic_write_text(output_root / "CAPABILITY_PRE_RUN_REPORT.md", render_report_md(cast(Mapping[str, Any], payloads["CAPABILITY_PRE_RUN_REPORT.json"])))
    atomic_write_text(output_root / "REQUIREMENT_CAPABILITY_MATRIX.md", render_matrix_md(cast(Mapping[str, Any], payloads["REQUIREMENT_CAPABILITY_MATRIX.json"])))
    atomic_write_text(output_root / "FACTORY_IMPROVEMENT_REQUIREMENTS.md", render_improvements_md(cast(Mapping[str, Any], payloads["FACTORY_IMPROVEMENT_REQUIREMENTS.json"])))
    atomic_write_text(output_root / "FACTORY_IMPROVEMENT_PLAN.md", render_plan_md(cast(Mapping[str, Any], payloads["FACTORY_IMPROVEMENT_PLAN.json"])))
    sums: list[str] = []
    checksums: dict[str, str] = {}
    for name in ARTIFACT_NAMES:
        if name == "PRE_RUN_SHA256SUMS":
            continue
        digest = sha256_file(output_root / name)
        checksums[name] = digest
        sums.append(f"{digest}  {name}")
    atomic_write_text(output_root / "PRE_RUN_SHA256SUMS", "\n".join(sums) + "\n")
    checksums["PRE_RUN_SHA256SUMS"] = sha256_file(output_root / "PRE_RUN_SHA256SUMS")
    return checksums


def build_payloads(config: PreRunConfig) -> dict[str, Any]:
    app_id = validate_application_id(config.application_id)
    requirements = safe_resolved_file(config.requirements_document, label="requirements document")
    data = requirements.read_bytes()
    requirements_sha = sha256_bytes(data)
    if config.expected_requirements_sha256 and requirements_sha != config.expected_requirements_sha256:
        raise NativeCapabilityError("requirements document SHA-256 does not match controller-derived value")
    extraction = extract_text(requirements)
    normalized_text = str(extraction["text"])
    obligations = inventory_obligations(normalized_text, application_id=app_id)
    repo = git_identity(config.factory_root)
    capabilities = default_capability_catalogue(config.factory_root)
    evidence_cache: dict[str, dict[str, Any]] = {}
    evaluated = [
        classify_obligation(
            item,
            capabilities=capabilities,
            factory_root=config.factory_root,
            factory_commit=str(repo["head"]),
            evidence_cache=evidence_cache,
        )
        for item in obligations
    ]
    for item in evaluated:
        if item["classification"] not in CLASSIFICATIONS:
            raise NativeCapabilityError("internal classification outside schema")
        if item["classification"] != "FULFILLABLE" and item["fulfillable"] is True:
            raise NativeCapabilityError("non-fulfillable classification cannot set fulfillable true")
    improvements = build_improvement_items(evaluated, application_id=app_id)
    go = all(item["fulfillable"] is True for item in evaluated) and not improvements
    decision = GO_DECISION if go else NO_GO_DECISION
    run_id = config.run_id or (
        "pre_run_"
        + requirements_sha[:16]
        + "_"
        + sha256_bytes(app_id.encode("utf-8"))[:10]
    )
    summary = {
        "total": len(evaluated),
        "fulfillable": sum(1 for item in evaluated if item["fulfillable"] is True),
        "non_fulfillable": sum(1 for item in evaluated if item["fulfillable"] is not True),
        "explicit_requirement_to_code_and_test": sum(
            1
            for item in evaluated
            if str(item.get("proof_mode") or "") in EXPLICIT_PROOF_MODES
            and bool(_partition_evidence(cast(Sequence[Mapping[str, Any]], item["evidence"]))[0])
            and bool(_partition_evidence(cast(Sequence[Mapping[str, Any]], item["evidence"]))[1])
        ),
        "by_classification": {
            classification: sum(1 for item in evaluated if item["classification"] == classification)
            for classification in sorted(CLASSIFICATIONS)
        },
    }
    matrix_items = [
        build_requirement_matrix_item(item, improvements=improvements)
        for item in evaluated
    ]
    report = {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "artifact": "CAPABILITY_PRE_RUN_REPORT",
        "run_id": run_id,
        "application_id": app_id,
        "requirements_path": portable_requirements_path(
            requirements,
            config.factory_root,
            requirements_sha,
        ),
        "requirements_sha256": requirements_sha,
        "requirements_size_bytes": len(data),
        "factory_identity": repo,
        "document_normalization": {
            key: value for key, value in extraction.items() if key != "text"
        }
        | {
            "normalized_sha256": sha256_bytes(normalized_text.encode("utf-8")),
            "normalized_size_bytes": len(normalized_text.encode("utf-8")),
        },
        "status": decision,
        "decision": decision,
        "mandatory_gate_passed": go,
        "obligation_count": len(matrix_items),
        "summary": summary,
        "obligations": matrix_items,
        "improvement_item_count": len(improvements),
        "created_at_utc": utc_now(),
        "llm_claims_used": False,
        "real_payment_calls": "disabled",
        "live_provider_calls": "prohibited",
    }
    matrix = {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "artifact": "REQUIREMENT_CAPABILITY_MATRIX",
        "application_id": app_id,
        "requirements_sha256": requirements_sha,
        "obligation_count": len(matrix_items),
        "atomic_obligation_count": len(matrix_items),
        "requirements": matrix_items,
        "items": matrix_items,
        "decision": decision,
    }
    improvement_payload = {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "artifact": "FACTORY_IMPROVEMENT_REQUIREMENTS",
        "application_id": app_id,
        "requirements_sha256": requirements_sha,
        "factory_baseline": repo["head"],
        "source_status": decision,
        "items": improvements,
    }
    plan = {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "artifact": "FACTORY_IMPROVEMENT_PLAN",
        "application_id": app_id,
        "requirements_sha256": requirements_sha,
        "plan_only_default": True,
        "implementation_steps": [
            {
                "wave": item["implementation_wave"],
                "id": item["id"],
                "priority": item["priority"],
                "owner_category": item["owner_category"],
                "candidate_paths": item["candidate_paths"],
                "acceptance_criteria": item["acceptance_criteria"],
            }
            for item in improvements
        ],
        "stop_condition": "governed review after deterministic validation",
        "prohibited_actions": [
            "merge",
            "push",
            "force push",
            "tag",
            "release",
            "deployment",
            "certification claim",
            "branch deletion",
            "worktree deletion",
            "live provider calls",
        ],
    }
    manifest = {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "artifact": "PRE_RUN_MANIFEST",
        "run_id": run_id,
        "application_id": app_id,
        "requirements_sha256": requirements_sha,
        "factory_identity": repo,
        "artifacts": list(ARTIFACT_NAMES),
        "decision": decision,
        "mandatory_gate_passed": go,
        "created_at_utc": utc_now(),
    }
    return {
        "CAPABILITY_PRE_RUN_REPORT.json": report,
        "REQUIREMENT_CAPABILITY_MATRIX.json": matrix,
        "FACTORY_IMPROVEMENT_REQUIREMENTS.json": improvement_payload,
        "FACTORY_IMPROVEMENT_PLAN.json": plan,
        "PRE_RUN_MANIFEST.json": manifest,
    }


def verify_artifacts(output_root: Path) -> dict[str, str]:
    missing = [name for name in ARTIFACT_NAMES if not (output_root / name).is_file()]
    if missing:
        raise NativeCapabilityError("missing mandatory artifacts: " + ", ".join(missing))
    recorded = (output_root / "PRE_RUN_SHA256SUMS").read_text(encoding="utf-8").splitlines()
    expected: dict[str, str] = {}
    for line in recorded:
        digest, _, name = line.partition("  ")
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not name:
            raise NativeCapabilityError("PRE_RUN_SHA256SUMS contains malformed line")
        expected[name] = digest
    for name, digest in expected.items():
        actual = sha256_file(output_root / name)
        if actual != digest:
            raise NativeCapabilityError(f"artifact checksum mismatch for {name}")
    return {**expected, "PRE_RUN_SHA256SUMS": sha256_file(output_root / "PRE_RUN_SHA256SUMS")}


def run_capability_prerun(config: PreRunConfig) -> dict[str, Any]:
    output_root = safe_output_root(config.output_root)
    lock = output_root / ".native_capability_prerun.lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise NativeCapabilityError("native capability pre-run output is locked by another run") from exc
    try:
        payloads = build_payloads(config)
        with tempfile.TemporaryDirectory(prefix=".native_capability_prerun.", dir=output_root) as temp_name:
            temp_root = Path(temp_name)
            checksums = write_artifacts(temp_root, payloads)
            for name in ARTIFACT_NAMES:
                (temp_root / name).replace(output_root / name)
        checksums = verify_artifacts(output_root)
        report = json.loads((output_root / "CAPABILITY_PRE_RUN_REPORT.json").read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise NativeCapabilityError("report artifact is malformed")
        report["artifact_checksums"] = checksums
        return report
    finally:
        try:
            lock.rmdir()
        except FileNotFoundError:
            pass
