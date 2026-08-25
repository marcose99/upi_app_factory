"""Deterministic realization of a requirements IR into a finite semantic model.

The model is deliberately provider neutral.  It is an executable-generation input,
not an interpretation produced by a runtime language model.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence


SEMANTIC_MODEL_VERSION = "upi-app-factory.semantic-model.v1"
_COLLECTIONS = (
    "actors",
    "use_cases",
    "bounded_contexts",
    "commands",
    "queries",
    "events",
    "aggregates",
    "invariants",
    "workflows",
    "apis",
    "data",
    "security",
    "operations",
    "evidence",
)


class SemanticRealizationError(ValueError):
    """Raised when an IR cannot be represented truthfully by the finite model."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _slug(value: object, fallback: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return result or fallback


def _plain(value: Any) -> Any:
    """Remove source-location noise while retaining all requirement semantics."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in sorted(value.items()) if key != "source"}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _entries(ir: Mapping[str, Any], collection: str) -> list[dict[str, Any]]:
    nested = ir.get("requirements", {})
    nested_requirements = nested if isinstance(nested, Mapping) else {}
    raw = ir.get(collection, nested_requirements.get(collection, []))
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise SemanticRealizationError(f"requirements IR collection {collection!r} must be a list")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, Mapping):
            raise SemanticRealizationError(f"{collection}[{index}] must be an object")
        body = _plain(item)
        identifier = str(body.get("id") or f"{collection}_{index:03d}")
        body["id"] = identifier
        body["semantic_key"] = _slug(identifier, f"{collection}_{index:03d}")
        rows.append(body)
    return sorted(rows, key=lambda row: (str(row["id"]), _canonical(row)))


def _state_machine(workflows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    states: set[str] = {"received"}
    transitions: list[dict[str, str]] = []
    for index, row in enumerate(workflows, 1):
        source = _slug(row.get("from") or row.get("source_state") or "received", "received")
        target = _slug(
            row.get("to") or row.get("target_state") or row.get("state") or row["id"],
            f"state_{index}",
        )
        signal = _slug(
            row.get("signal") or row.get("command") or row.get("event") or row["id"],
            f"signal_{index}",
        )
        states.update((source, target))
        transitions.append({"from": source, "signal": signal, "to": target})
    if not transitions:
        states.add("completed")
        transitions.append({"from": "received", "signal": "complete", "to": "completed"})
    valid = sorted(transitions, key=lambda row: (row["from"], row["signal"], row["to"]))
    invalid = [
        {"from": state, "signal": "unsupported", "error": "INVALID_TRANSITION"}
        for state in sorted(states)
    ]
    return {
        "initial": "received",
        "states": sorted(states),
        "valid_transitions": valid,
        "invalid_transitions": invalid,
    }


def build_semantic_model(requirements_ir: Mapping[str, Any]) -> dict[str, Any]:
    """Build the versioned finite model solely from normalized requirements IR."""
    if not isinstance(requirements_ir, Mapping):
        raise SemanticRealizationError("requirements_ir must be a mapping")
    collections = {name: _entries(requirements_ir, name) for name in _COLLECTIONS}
    if not any(collections.values()):
        raise SemanticRealizationError("requirements IR has no semantic entries")
    requirement_rows: list[dict[str, Any]] = []
    for collection, rows in collections.items():
        requirement_rows.extend(
            {
                "requirement_id": row["id"],
                "collection": collection,
                "semantic_key": row["semantic_key"],
            }
            for row in rows
        )
    workflows = collections["workflows"]
    policies = {
        "deadline": [
            row for row in workflows if any(key in row for key in ("deadline", "duration", "tat"))
        ],
        "reentry": [
            row for row in workflows if any(key in row for key in ("reentry", "re_entry", "retry"))
        ],
        "human_review": [
            row
            for row in workflows
            if any(key in row for key in ("human_review", "review_role", "approval"))
        ],
        "security": collections["security"],
    }
    normalized_input = {name: collections[name] for name in _COLLECTIONS}
    model: dict[str, Any] = {
        "schema_version": SEMANTIC_MODEL_VERSION,
        "source_ir_version": str(
            requirements_ir.get("schema_version") or requirements_ir.get("ir_version") or "unknown"
        ),
        "source_ir_sha256": hashlib.sha256(
            _canonical(_plain(requirements_ir)).encode()
        ).hexdigest(),
        "finite_scope": {
            "collections": list(_COLLECTIONS),
            "requirement_count": len(requirement_rows),
        },
        "requirements": sorted(
            requirement_rows, key=lambda row: (row["collection"], str(row["requirement_id"]))
        ),
        "actors": collections["actors"],
        "commands": collections["commands"],
        "queries": collections["queries"],
        "events": collections["events"],
        "aggregates": collections["aggregates"],
        "data": collections["data"],
        "apis": collections["apis"],
        "invariants": collections["invariants"],
        "policies": policies,
        "state_machine": _state_machine(workflows),
        "normalized_requirements": normalized_input,
        "authority": {
            "local_only": True,
            "mock_only": True,
            "real_payment_calls": "disabled",
            "runtime_llm_calls": 0,
        },
    }
    model["semantic_fingerprint"] = semantic_fingerprint(model)
    return model


def semantic_fingerprint(model: Mapping[str, Any]) -> str:
    """Return a stable fingerprint of semantic content, excluding self-identities."""
    if not isinstance(model, Mapping):
        raise SemanticRealizationError("semantic model must be a mapping")
    body = {
        str(key): _plain(value)
        for key, value in model.items()
        if key not in {"semantic_fingerprint", "generated_at"}
    }
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def render_semantic_files(
    model: Mapping[str, Any], app_id: str = "generated_application"
) -> dict[str, str]:
    """Render canonical semantic evidence and an importable policy data module."""
    expected = semantic_fingerprint(model)
    supplied = model.get("semantic_fingerprint")
    if supplied not in (None, expected):
        raise SemanticRealizationError("semantic fingerprint does not match model content")
    payload = dict(model)
    payload["semantic_fingerprint"] = expected
    literal = repr(
        {
            "state_machine": payload.get("state_machine", {}),
            "policies": payload.get("policies", {}),
            "authority": payload.get("authority", {}),
            "commands": payload.get("commands", []),
            "events": payload.get("events", []),
        }
    )
    return {
        "evidence/semantic_model.json": json.dumps(
            payload, indent=2, ensure_ascii=False, sort_keys=True
        )
        + "\n",
        f"app/{app_id}/semantic_policy.py": (
            '"""Generated from the canonical finite semantic model."""\n'
            f"SEMANTIC_MODEL_VERSION = {SEMANTIC_MODEL_VERSION!r}\n"
            f"SEMANTIC_FINGERPRINT = {expected!r}\n"
            f"SEMANTICS = {literal}\n"
        ),
    }


__all__ = ["build_semantic_model", "render_semantic_files", "semantic_fingerprint"]
