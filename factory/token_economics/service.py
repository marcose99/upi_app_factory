from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal, cast


UnknownInt = Literal["UNKNOWN"]
KnownOrUnknownInt = int | UnknownInt

RATE_CARD_SCHEMA: Final[str] = "token-economics-rate-card.v1"
BUDGET_SCHEMA: Final[str] = "token-economics-budget-envelope.v1"
MODEL_REGISTRY_SCHEMA: Final[str] = "token-economics-model-registry.v1"
ARTIFACT_REGISTRY_SCHEMA: Final[str] = "token-economics-artifact-ownership.v1"
GOVERNANCE_POLICY_SCHEMA: Final[str] = "token-economics-governance-policy.v1"
COMPACT_REPORT_SCHEMA: Final[str] = "token-economics-compact-report.v1"
LEDGER_AGGREGATE_SCHEMA: Final[str] = "token-economics-ledger-aggregate.v1"
RECONCILIATION_SCHEMA: Final[str] = "token-economics-reconciliation.v1"
DEFAULT_CONFIG_SUBDIR: Final[Path] = Path("config/token_economics")
DEFAULT_RUNTIME_LEDGER_RELATIVE_PATH: Final[Path] = Path("workspace/token_economics_runtime/ledger.jsonl")
RATE_CARD_STALENESS_DEFAULT_DAYS: Final[int] = 365
TURN_STATE_SEQUENCE: Final[tuple[str, ...]] = (
    "AUTHORIZED",
    "PRE_INVOKE_SEALED",
    "IN_PROGRESS",
    "TURN_INCOMPLETE",
    "FAILED_CLOSED",
    "TURN_FAILED",
    "TURN_INTERRUPTED",
    "TURN_COMPLETED",
    "COMPLETION_SEALED",
    "MUTATIONS_RECONCILED",
    "OBSERVED_COST_SETTLED",
    "DETERMINISTIC_VALIDATION",
    "READY_FOR_GOVERNED_REVIEW",
    "ACCEPTED",
    "REJECTED",
    "BLOCKED_FURTHER_MODEL_CALLS",
    "RECONCILIATION_PENDING",
    "RECONCILED",
)
PROHIBITED_COMPACT_FIELDS: Final[set[str]] = {
    "prompt",
    "response",
    "reasoning",
    "reasoning_summary",
    "raw_provider_payload",
    "raw_events",
    "tool_payload",
    "credential",
    "secret",
    "personal_data",
    "payment_data",
}
LLM_ACTIVITY_MARKERS: Final[tuple[str, ...]] = (
    " llm",
    "llm ",
    "model",
    "agent",
    "prompt",
    "token",
    "retrieval",
    "reasoning",
    "openai",
    "codex",
)


class TokenEconomicsError(RuntimeError):
    """Fail-closed token economics error."""


class RateCardError(TokenEconomicsError):
    """Raised when rate-card validation or resolution fails."""


class UsageNormalizationError(TokenEconomicsError):
    """Raised when provider usage violates invariants."""


class ArtifactOwnershipError(TokenEconomicsError):
    """Raised when artifact ownership cannot be resolved safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str, *, label: str) -> datetime:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TokenEconomicsError(f"{label} must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise TokenEconomicsError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TokenEconomicsError(f"expected JSON object: {path}")
    return cast(dict[str, Any], value)


def _as_decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception as exc:  # pragma: no cover - Decimal raises varied exceptions
            raise TokenEconomicsError(f"{label} must be a decimal string") from exc
    if isinstance(value, float):
        raise TokenEconomicsError(f"{label} must not use binary floating point")
    raise TokenEconomicsError(f"{label} must be an integer or decimal string")


def _quantize(value: Decimal, *, decimal_places: int, mode: str) -> Decimal:
    quantum = Decimal(1).scaleb(-decimal_places)
    rounding = ROUND_CEILING if mode == "ROUND_CEILING" else ROUND_HALF_UP
    return value.quantize(quantum, rounding=rounding)


def _non_negative_int(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TokenEconomicsError(f"{label} must be a non-negative integer")
    if value < 0:
        raise TokenEconomicsError(f"{label} must be a non-negative integer")
    return value


def _optional_non_negative_int(value: object, *, label: str) -> KnownOrUnknownInt:
    if value in {None, "", "UNKNOWN"}:
        return "UNKNOWN"
    return _non_negative_int(value, label=label)


def _usage_field(usage: Mapping[str, Any], *names: str) -> object:
    for name in names:
        if name in usage:
            return usage[name]
    return None


def default_config_root(project_root: Path | None = None) -> Path:
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    return root / DEFAULT_CONFIG_SUBDIR


@dataclass(frozen=True)
class RateCard:
    path: Path
    payload: dict[str, Any]

    @property
    def rate_card_id(self) -> str:
        return str(self.payload["rate_card_id"])

    @property
    def currency_or_credit_unit(self) -> str:
        return str(self.payload["currency_or_credit_unit"])

    @property
    def effective_from(self) -> datetime:
        return _parse_utc(str(self.payload["effective_from"]), label="effective_from")

    @property
    def effective_to(self) -> datetime | None:
        value = self.payload.get("effective_to")
        if value in {None, ""}:
            return None
        return _parse_utc(str(value), label="effective_to")

    @property
    def match_key(self) -> tuple[str, ...]:
        return (
            str(self.payload["provider"]),
            str(self.payload["billing_surface"]),
            str(self.payload["model_resolved"]),
            str(self.payload["model_version"]),
            str(self.payload["service_tier"]),
            str(self.payload["context_band"]),
            str(self.payload["modality"]),
            str(self.payload["region_or_residency"]),
            str(self.payload["currency_or_credit_unit"]),
            str(self.payload["contract_id"]),
        )

    @property
    def rounding_mode(self) -> str:
        rounding = self.payload.get("rounding_policy", {})
        if not isinstance(rounding, Mapping):
            raise RateCardError("rounding_policy must be an object")
        mode = str(rounding.get("mode", "ROUND_CEILING"))
        if mode not in {"ROUND_CEILING", "ROUND_HALF_UP"}:
            raise RateCardError("unsupported rounding mode")
        return mode

    @property
    def rounding_decimal_places(self) -> int:
        rounding = self.payload.get("rounding_policy", {})
        if not isinstance(rounding, Mapping):
            raise RateCardError("rounding_policy must be an object")
        return _non_negative_int(rounding.get("decimal_places", 7), label="rounding decimal_places")

    @property
    def staleness_threshold_days(self) -> int:
        return _non_negative_int(
            self.payload.get("staleness_threshold_days", RATE_CARD_STALENESS_DEFAULT_DAYS),
            label="staleness_threshold_days",
        )

    def categories(self) -> Mapping[str, Mapping[str, Any]]:
        categories = self.payload.get("categories")
        if not isinstance(categories, Mapping):
            raise RateCardError("categories must be an object")
        return cast(Mapping[str, Mapping[str, Any]], categories)

    def validate(self) -> dict[str, Any]:
        if self.payload.get("schema_version") != RATE_CARD_SCHEMA:
            raise RateCardError(f"unsupported rate card schema in {self.path}")
        required = (
            "rate_card_id",
            "provider",
            "billing_surface",
            "model_resolved",
            "model_version",
            "service_tier",
            "context_band",
            "modality",
            "region_or_residency",
            "currency_or_credit_unit",
            "effective_from",
            "contract_id",
            "categories",
            "provenance",
            "rounding_policy",
        )
        missing = [field for field in required if field not in self.payload]
        if missing:
            raise RateCardError(f"rate card missing required fields: {', '.join(missing)}")
        categories = self.categories()
        for required_category in ("uncached_input", "cache_read", "cache_write", "output"):
            if required_category not in categories:
                raise RateCardError(f"rate card missing {required_category} category")
        for name, category_payload in categories.items():
            if not isinstance(category_payload, Mapping):
                raise RateCardError(f"category {name} must be an object")
            _as_decimal(category_payload.get("rate"), label=f"{name} rate")
            unit_scale = category_payload.get("unit_scale")
            if not isinstance(unit_scale, str) or not unit_scale:
                raise RateCardError(f"{name} unit_scale must be a non-empty string")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise RateCardError("effective_to must be greater than effective_from")
        integrity = self.payload.get("integrity")
        if not isinstance(integrity, Mapping) or not isinstance(integrity.get("sha256"), str):
            raise RateCardError("rate card integrity.sha256 is required")
        expected = cast(str, integrity["sha256"])
        material = {key: value for key, value in self.payload.items() if key != "integrity"}
        actual = _sha256_bytes(_canonical_json_bytes(material))
        if expected != actual:
            raise RateCardError(f"rate card integrity mismatch for {self.rate_card_id}")
        return {
            "rate_card_id": self.rate_card_id,
            "path": str(self.path),
            "currency_or_credit_unit": self.currency_or_credit_unit,
            "match_key": self.match_key,
            "effective_from": self.payload["effective_from"],
            "effective_to": self.payload.get("effective_to"),
            "staleness_threshold_days": self.staleness_threshold_days,
            "integrity_sha256": expected,
        }


def load_rate_cards(config_root: Path | None = None) -> list[RateCard]:
    root = (config_root or default_config_root()).resolve()
    rate_root = root / "rate_cards"
    cards = [RateCard(path=path, payload=_json_object(path)) for path in sorted(rate_root.rglob("*.json"))]
    if not cards:
        raise RateCardError(f"no rate cards found under {rate_root}")
    validated = [card.validate() for card in cards]
    del validated
    _reject_overlapping_rate_cards(cards)
    return cards


def _reject_overlapping_rate_cards(cards: Sequence[RateCard]) -> None:
    grouped: dict[tuple[str, ...], list[RateCard]] = {}
    for card in cards:
        grouped.setdefault(card.match_key, []).append(card)
    for key, group in grouped.items():
        ordered = sorted(group, key=lambda item: item.effective_from)
        for left, right in zip(ordered, ordered[1:]):
            left_end = left.effective_to or datetime.max.replace(tzinfo=timezone.utc)
            if left_end > right.effective_from:
                raise RateCardError(
                    "overlapping effective intervals detected for "
                    f"{left.rate_card_id} and {right.rate_card_id} with key {key}"
                )


def resolve_rate_card(
    lookup: Mapping[str, Any],
    *,
    config_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    requested_time = now or datetime.now(timezone.utc)
    candidates: list[RateCard] = []
    for card in load_rate_cards(config_root):
        if any(str(card.payload.get(key)) != str(lookup.get(key)) for key in rate_card_match_key_fields()):
            continue
        if card.effective_from > requested_time:
            continue
        if card.effective_to is not None and card.effective_to <= requested_time:
            continue
        candidates.append(card)
    if not candidates:
        raise RateCardError("unknown or out-of-interval rate-card key")
    if len(candidates) != 1:
        raise RateCardError("ambiguous rate-card resolution")
    resolved = candidates[0]
    staleness_cutoff = requested_time - timedelta(days=resolved.staleness_threshold_days)
    stale = resolved.effective_from < staleness_cutoff
    return {
        "status": "resolved",
        "rate_card_id": resolved.rate_card_id,
        "path": str(resolved.path),
        "payload": resolved.payload,
        "stale": stale,
    }


def load_model_registry(config_root: Path | None = None) -> dict[str, Any]:
    root = (config_root or default_config_root()).resolve()
    payload = _json_object(root / "model_registry.json")
    if payload.get("schema_version") != MODEL_REGISTRY_SCHEMA:
        raise TokenEconomicsError("unsupported model registry schema")
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise TokenEconomicsError("model registry routes must be a non-empty array")
    return payload


def load_governance_policy(config_root: Path | None = None) -> dict[str, Any]:
    root = (config_root or default_config_root()).resolve()
    payload = _json_object(root / "governance_policy.json")
    if payload.get("schema_version") != GOVERNANCE_POLICY_SCHEMA:
        raise TokenEconomicsError("unsupported governance policy schema")
    decision_rights = payload.get("decision_rights")
    if not isinstance(decision_rights, Mapping):
        raise TokenEconomicsError("governance policy decision_rights must be an object")
    human_authority = decision_rights.get("human_authority")
    if not isinstance(human_authority, list) or any(not isinstance(item, str) for item in human_authority):
        raise TokenEconomicsError("governance policy human_authority must be a string array")
    required_human_rights = {
        "merge",
        "push",
        "release",
        "deployment",
        "budget_exception",
        "rate_card_publication",
        "certification_claim",
    }
    missing_human_rights = sorted(required_human_rights - set(human_authority))
    if missing_human_rights:
        raise TokenEconomicsError(
            "governance policy human_authority is missing required rights: "
            + ", ".join(missing_human_rights)
        )
    exception_policy = payload.get("exception_policy")
    if not isinstance(exception_policy, Mapping):
        raise TokenEconomicsError("governance policy exception_policy must be an object")
    if exception_policy.get("scoped") is not True or exception_policy.get("expiring") is not True:
        raise TokenEconomicsError("governance policy exceptions must remain scoped and expiring")
    retention_policy = payload.get("retention_policy")
    if not isinstance(retention_policy, Mapping):
        raise TokenEconomicsError("governance policy retention_policy must be an object")
    if retention_policy.get("legal_hold_machine_readable") is not True:
        raise TokenEconomicsError("governance policy must retain machine-readable legal hold state")
    compatibility_mappings = payload.get("compatibility_mappings")
    if not isinstance(compatibility_mappings, Mapping):
        raise TokenEconomicsError("governance policy compatibility_mappings must be an object")
    if compatibility_mappings.get("focus") != "compatibility_mapping_only":
        raise TokenEconomicsError("governance policy compatibility focus must stay mapping-only")
    if compatibility_mappings.get("opentelemetry_genai") != "versioned_compatibility_adapter":
        raise TokenEconomicsError(
            "governance policy compatibility adapter must remain versioned_compatibility_adapter"
        )
    return payload


def load_artifact_ownership_registry(config_root: Path | None = None) -> dict[str, Any]:
    root = (config_root or default_config_root()).resolve()
    payload = _json_object(root / "artifact_ownership_registry.json")
    if payload.get("schema_version") != ARTIFACT_REGISTRY_SCHEMA:
        raise ArtifactOwnershipError("unsupported artifact ownership schema")
    families = payload.get("families")
    if not isinstance(families, list) or not families:
        raise ArtifactOwnershipError("artifact registry families must be a non-empty array")
    for family in families:
        if not isinstance(family, Mapping):
            raise ArtifactOwnershipError("artifact registry families must contain objects")
        runtime_root = family.get("runtime_root")
        if runtime_root not in {None, ""} and family.get("candidate_commit_allowed") is not False:
            raise ArtifactOwnershipError("runtime-root artifact families must not allow candidate commits")
        path_patterns = family.get("path_patterns")
        if not isinstance(path_patterns, list) or not path_patterns:
            raise ArtifactOwnershipError("artifact registry family path_patterns must be a non-empty array")
    return payload


def resolve_artifact_owner(
    relative_path: str,
    *,
    config_root: Path | None = None,
) -> dict[str, Any]:
    registry = load_artifact_ownership_registry(config_root)
    normalized = PurePosixPath(relative_path).as_posix()
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise ArtifactOwnershipError("artifact path must stay within the repository root")
    matches = []
    for family in cast(list[dict[str, Any]], registry["families"]):
        patterns = family.get("path_patterns")
        if not isinstance(patterns, list):
            raise ArtifactOwnershipError("artifact family path_patterns must be an array")
        if any(fnmatch.fnmatch(normalized, str(pattern)) for pattern in patterns):
            matches.append(family)
    if not matches:
        raise ArtifactOwnershipError(f"undeclared artifact path: {normalized}")
    if len(matches) != 1:
        raise ArtifactOwnershipError(f"artifact path matched multiple families: {normalized}")
    return matches[0]


def validate_artifact_path(
    path: Path,
    *,
    project_root: Path | None = None,
    config_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    resolved = path.expanduser().resolve()
    if resolved.is_symlink() or path.is_symlink():
        raise ArtifactOwnershipError("symlinked artifacts are rejected")
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ArtifactOwnershipError("artifact escaped the repository root") from exc
    family = resolve_artifact_owner(relative, config_root=config_root)
    return {
        "path": str(resolved),
        "relative_path": relative,
        "family_id": family["family_id"],
        "logical_owner": family["logical_owner"],
        "artifact_kind": family["artifact_kind"],
        "candidate_commit_allowed": bool(family["candidate_commit_allowed"]),
        "runtime_root": family.get("runtime_root"),
    }


def load_budget_envelope(path: Path) -> dict[str, Any]:
    payload = _json_object(path)
    if payload.get("schema_version") != BUDGET_SCHEMA:
        raise TokenEconomicsError("unsupported budget envelope schema")
    required = (
        "budget_id",
        "scope",
        "unit",
        "soft_limit",
        "hard_limit",
        "raw_input_anomaly_limit",
        "output_limit",
        "wall_clock_limit_seconds",
        "tool_action_limit",
        "tool_byte_limit",
        "max_model_turns",
        "max_repair_cycles",
        "max_review_cycles",
        "max_handoffs",
        "mutation_allowlist",
        "mutation_diff_size_limit",
        "overrun_policy",
        "rate_card_id",
        "effective_from",
        "owner",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise TokenEconomicsError(f"budget envelope missing fields: {', '.join(missing)}")
    if _as_decimal(payload["hard_limit"], label="hard_limit") < _as_decimal(
        payload["soft_limit"],
        label="soft_limit",
    ):
        raise TokenEconomicsError("hard_limit must be greater than or equal to soft_limit")
    return payload


def normalize_usage(
    provider_usage: Mapping[str, Any] | None,
    *,
    provider_response_id: str | None = None,
    provider_turn_id: str | None = None,
    provider_request_id: str | None = None,
    provider_native_fields: Mapping[str, Any] | None = None,
    normalizer_version: str = "token-economics-normalizer.v1",
) -> dict[str, Any]:
    native = dict(provider_native_fields or {})
    if provider_usage is not None:
        native.setdefault("usage", dict(provider_usage))
    usage = provider_usage or {}
    total_input = _optional_non_negative_int(_usage_field(usage, "input_tokens"), label="input_tokens")
    cache_read = _optional_non_negative_int(
        _usage_field(usage, "cached_input_tokens", "cache_read_input_tokens"),
        label="cached_input_tokens",
    )
    cache_write = _optional_non_negative_int(
        _usage_field(usage, "cache_write_input_tokens"),
        label="cache_write_input_tokens",
    )
    total_output = _optional_non_negative_int(
        _usage_field(usage, "output_tokens"),
        label="output_tokens",
    )
    reasoning_output = _optional_non_negative_int(
        _usage_field(usage, "reasoning_output_tokens", "reasoning_tokens"),
        label="reasoning_output_tokens",
    )
    normalized_usage: dict[str, Any]
    if all(value == "UNKNOWN" for value in (total_input, cache_read, cache_write, total_output, reasoning_output)):
        normalized_usage = {
            "status": "UNKNOWN",
            "total_input_tokens": "UNKNOWN",
            "cache_read_input_tokens": "UNKNOWN",
            "cache_write_input_tokens": "UNKNOWN",
            "uncached_input_tokens": "UNKNOWN",
            "total_output_tokens": "UNKNOWN",
            "reasoning_output_tokens": "UNKNOWN",
        }
    else:
        if "UNKNOWN" in {total_input, cache_read, cache_write, total_output, reasoning_output}:
            raise UsageNormalizationError("usage fields are partially missing; unknown usage must fail closed")
        assert isinstance(total_input, int)
        assert isinstance(cache_read, int)
        assert isinstance(cache_write, int)
        assert isinstance(total_output, int)
        assert isinstance(reasoning_output, int)
        if total_input < cache_read + cache_write:
            raise UsageNormalizationError("cached and cache-write input cannot exceed total input")
        if reasoning_output > total_output:
            raise UsageNormalizationError("reasoning output cannot exceed total output")
        normalized_usage = {
            "status": "OBSERVED",
            "total_input_tokens": total_input,
            "cache_read_input_tokens": cache_read,
            "cache_write_input_tokens": cache_write,
            "uncached_input_tokens": total_input - cache_read - cache_write,
            "total_output_tokens": total_output,
            "reasoning_output_tokens": reasoning_output,
        }
    return {
        "normalizer_version": normalizer_version,
        "provider_request_id": provider_request_id,
        "provider_response_id": provider_response_id,
        "provider_turn_id": provider_turn_id,
        "provider_native_usage": native,
        "normalized_usage": normalized_usage,
    }


def estimate_usage_cost(
    usage: Mapping[str, Any],
    *,
    rate_card_id: str,
    config_root: Path | None = None,
    ancillary_fees: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    card = _rate_card_by_id(rate_card_id, config_root=config_root)
    normalized = normalize_usage(usage)
    normalized_usage = cast(dict[str, Any], normalized["normalized_usage"])
    if normalized_usage["status"] != "OBSERVED":
        raise TokenEconomicsError("estimate requires fully known usage")
    return _settle_normalized_usage(
        normalized_usage=normalized_usage,
        rate_card=card,
        ancillary_fees=ancillary_fees or {},
        settlement_state="ESTIMATED",
    )


def settle_usage(
    usage_record: Mapping[str, Any],
    *,
    rate_card_id: str,
    config_root: Path | None = None,
    ancillary_fees: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    card = _rate_card_by_id(rate_card_id, config_root=config_root)
    normalized_usage = usage_record.get("normalized_usage")
    if not isinstance(normalized_usage, Mapping):
        raise TokenEconomicsError("usage_record must contain normalized_usage")
    status = normalized_usage.get("status")
    if status != "OBSERVED":
        raise TokenEconomicsError("settlement requires observed normalized usage")
    return _settle_normalized_usage(
        normalized_usage=cast(Mapping[str, Any], normalized_usage),
        rate_card=card,
        ancillary_fees=ancillary_fees or {},
        settlement_state="SETTLED",
    )


def _rate_card_by_id(rate_card_id: str, *, config_root: Path | None = None) -> RateCard:
    cards = [card for card in load_rate_cards(config_root) if card.rate_card_id == rate_card_id]
    if len(cards) != 1:
        raise RateCardError(f"rate card id not found uniquely: {rate_card_id}")
    return cards[0]


def _rate_value(card: RateCard, category: str) -> Decimal:
    category_payload = card.categories().get(category)
    if not isinstance(category_payload, Mapping):
        raise RateCardError(f"rate card missing category {category}")
    return _as_decimal(category_payload.get("rate"), label=f"{category} rate")


def _fee_value(fees: Mapping[str, Any], key: str) -> Decimal:
    if key not in fees:
        return Decimal("0")
    return _as_decimal(fees[key], label=key)


def _settle_normalized_usage(
    *,
    normalized_usage: Mapping[str, Any],
    rate_card: RateCard,
    ancillary_fees: Mapping[str, Any],
    settlement_state: str,
) -> dict[str, Any]:
    uncached = _non_negative_int(normalized_usage["uncached_input_tokens"], label="uncached_input_tokens")
    cache_read = _non_negative_int(
        normalized_usage["cache_read_input_tokens"],
        label="cache_read_input_tokens",
    )
    cache_write = _non_negative_int(
        normalized_usage["cache_write_input_tokens"],
        label="cache_write_input_tokens",
    )
    total_output = _non_negative_int(
        normalized_usage["total_output_tokens"],
        label="total_output_tokens",
    )
    exact_inputs = {
        "uncached_input_tokens": uncached,
        "cache_read_input_tokens": cache_read,
        "cache_write_input_tokens": cache_write,
        "total_output_tokens": total_output,
    }
    uncached_cost = Decimal(uncached) * _rate_value(rate_card, "uncached_input")
    cache_read_cost = Decimal(cache_read) * _rate_value(rate_card, "cache_read")
    cache_write_cost = Decimal(cache_write) * _rate_value(rate_card, "cache_write")
    output_cost = Decimal(total_output) * _rate_value(rate_card, "output")
    tool_fees = _fee_value(ancillary_fees, "tool_fees")
    storage_fees = _fee_value(ancillary_fees, "storage_fees")
    compute_fees = _fee_value(ancillary_fees, "compute_fees")
    regional_uplift = _fee_value(ancillary_fees, "regional_uplift")
    explicit_discounts = _fee_value(ancillary_fees, "explicit_discounts")
    token_cost = uncached_cost + cache_read_cost + cache_write_cost + output_cost
    total_cost = token_cost + tool_fees + storage_fees + compute_fees + regional_uplift - explicit_discounts
    rounded = _quantize(
        total_cost,
        decimal_places=rate_card.rounding_decimal_places,
        mode=rate_card.rounding_mode,
    )
    return {
        "schema_version": "token-economics-settlement.v1",
        "state": settlement_state,
        "rate_card_id": rate_card.rate_card_id,
        "currency_or_credit_unit": rate_card.currency_or_credit_unit,
        "rounding_policy": {
            "mode": rate_card.rounding_mode,
            "decimal_places": rate_card.rounding_decimal_places,
        },
        "exact_inputs": exact_inputs,
        "exact_cost_components": {
            "uncached_input_cost": str(uncached_cost),
            "cache_read_cost": str(cache_read_cost),
            "cache_write_cost": str(cache_write_cost),
            "output_cost": str(output_cost),
            "tool_fees": str(tool_fees),
            "storage_fees": str(storage_fees),
            "compute_fees": str(compute_fees),
            "regional_uplift": str(regional_uplift),
            "explicit_discounts": str(explicit_discounts),
        },
        "token_cost_unrounded": str(token_cost),
        "total_cost_unrounded": str(total_cost),
        "rounded_amount": str(rounded),
    }


def authorize_budget(
    envelope: Mapping[str, Any],
    *,
    reserved_amount: object,
    prior_spend_amount: object = "0",
    observed_raw_input_tokens: int | None = None,
    observed_output_tokens: int | None = None,
    wall_clock_seconds: int | None = None,
    tool_actions: int | None = None,
    tool_bytes: int | None = None,
    model_turns: int | None = None,
    repair_cycles: int | None = None,
    review_cycles: int | None = None,
    handoffs: int | None = None,
    mutation_paths: Sequence[str] | None = None,
    mutation_diff_bytes: int | None = None,
) -> dict[str, Any]:
    soft = _as_decimal(envelope["soft_limit"], label="soft_limit")
    hard = _as_decimal(envelope["hard_limit"], label="hard_limit")
    reserved = _as_decimal(reserved_amount, label="reserved_amount")
    prior = _as_decimal(prior_spend_amount, label="prior_spend_amount")
    projected_total = prior + reserved
    warnings: list[str] = []
    blocks: list[str] = []

    def _classify_limit(
        *,
        label: str,
        current: int | None,
        limit: object,
    ) -> dict[str, Any]:
        parsed_limit = _non_negative_int(limit, label=label)
        if current is None:
            return {"status": "UNKNOWN", "limit": parsed_limit}
        if current > parsed_limit:
            blocks.append(label)
            return {"status": "BLOCKED", "limit": parsed_limit, "observed": current}
        return {"status": "OK", "limit": parsed_limit, "observed": current}

    economic_status = "OK"
    if projected_total >= hard:
        blocks.append("economic_budget")
        economic_status = "BLOCKED"
    elif projected_total >= soft:
        warnings.append("economic_budget")
        economic_status = "WARN"

    allowlist = envelope.get("mutation_allowlist")
    if not isinstance(allowlist, list) or not all(isinstance(item, str) for item in allowlist):
        raise TokenEconomicsError("mutation_allowlist must be an array of strings")
    disallowed_mutations = [
        path
        for path in mutation_paths or []
        if not any(fnmatch.fnmatch(path, pattern) for pattern in cast(list[str], allowlist))
    ]
    if disallowed_mutations:
        blocks.append("mutations")

    mutation_diff_limit = _non_negative_int(
        envelope["mutation_diff_size_limit"],
        label="mutation_diff_size_limit",
    )
    if mutation_diff_bytes is not None and mutation_diff_bytes > mutation_diff_limit:
        blocks.append("mutation_diff_size_limit")

    decision = {
        "schema_version": "token-economics-budget-decision.v1",
        "budget_id": envelope["budget_id"],
        "unit": envelope["unit"],
        "rate_card_id": envelope["rate_card_id"],
        "reserved_amount": str(reserved),
        "prior_spend_amount": str(prior),
        "projected_total_amount": str(projected_total),
        "controls": {
            "economic_budget": {
                "status": economic_status,
                "soft_limit": str(soft),
                "hard_limit": str(hard),
            },
            "raw_token_anomaly": _classify_limit(
                label="raw_input_anomaly_limit",
                current=observed_raw_input_tokens,
                limit=envelope["raw_input_anomaly_limit"],
            ),
            "output": _classify_limit(
                label="output_limit",
                current=observed_output_tokens,
                limit=envelope["output_limit"],
            ),
            "runtime": _classify_limit(
                label="wall_clock_limit_seconds",
                current=wall_clock_seconds,
                limit=envelope["wall_clock_limit_seconds"],
            ),
            "tools_actions": _classify_limit(
                label="tool_action_limit",
                current=tool_actions,
                limit=envelope["tool_action_limit"],
            ),
            "tool_bytes": _classify_limit(
                label="tool_byte_limit",
                current=tool_bytes,
                limit=envelope["tool_byte_limit"],
            ),
            "model_turns": _classify_limit(
                label="max_model_turns",
                current=model_turns,
                limit=envelope["max_model_turns"],
            ),
            "repair_cycles": _classify_limit(
                label="max_repair_cycles",
                current=repair_cycles,
                limit=envelope["max_repair_cycles"],
            ),
            "review_cycles": _classify_limit(
                label="max_review_cycles",
                current=review_cycles,
                limit=envelope["max_review_cycles"],
            ),
            "handoffs": _classify_limit(
                label="max_handoffs",
                current=handoffs,
                limit=envelope["max_handoffs"],
            ),
            "mutations": {
                "status": "BLOCKED" if disallowed_mutations else "OK",
                "allowlist": list(allowlist),
                "disallowed_paths": disallowed_mutations,
                "diff_size_limit_bytes": mutation_diff_limit,
                "observed_diff_size_bytes": mutation_diff_bytes,
            },
        },
        "warnings": warnings,
        "blocks": blocks,
        "authorize_next_model_call": not blocks,
    }
    return decision


def state_transition_path(
    *,
    turn_state: str,
    completed_within_budget: bool | None = None,
    validation_passed: bool | None = None,
    accepted: bool | None = None,
    ready_for_governed_review: bool = False,
) -> list[str]:
    path = ["AUTHORIZED", "PRE_INVOKE_SEALED", "IN_PROGRESS"]
    if turn_state == "TURN_INCOMPLETE":
        return path + ["TURN_INCOMPLETE", "FAILED_CLOSED"]
    if turn_state == "TURN_FAILED":
        return path + ["TURN_FAILED"]
    if turn_state == "TURN_INTERRUPTED":
        return path + ["TURN_INTERRUPTED"]
    if turn_state != "TURN_COMPLETED":
        raise TokenEconomicsError(f"unsupported turn_state {turn_state}")
    path.extend(["TURN_COMPLETED", "COMPLETION_SEALED", "MUTATIONS_RECONCILED", "OBSERVED_COST_SETTLED"])
    if completed_within_budget is False:
        path.append("BLOCKED_FURTHER_MODEL_CALLS")
    path.append("DETERMINISTIC_VALIDATION")
    if validation_passed:
        if accepted is True:
            path.append("ACCEPTED")
        elif accepted is False:
            path.append("REJECTED")
        elif ready_for_governed_review:
            path.append("READY_FOR_GOVERNED_REVIEW")
        else:
            path.append("REJECTED")
    else:
        path.append("REJECTED")
    return path


def reconcile_records(payload: Mapping[str, Any]) -> dict[str, Any]:
    estimate = payload.get("estimate")
    observed = payload.get("observed")
    settled = payload.get("settled")
    provider_ids = payload.get("provider_ids", {})
    if not isinstance(provider_ids, Mapping):
        raise TokenEconomicsError("provider_ids must be an object")
    provider_identity_values = [
        str(value)
        for key, value in provider_ids.items()
        if key.endswith("_id") and value not in {None, ""}
    ]
    duplicates = [value for value, count in Counter(provider_identity_values).items() if count > 1]
    observed_amount = _as_decimal(
        cast(Mapping[str, Any], observed).get("rounded_amount", "0") if isinstance(observed, Mapping) else "0",
        label="observed rounded_amount",
    )
    settled_amount = _as_decimal(
        cast(Mapping[str, Any], settled).get("rounded_amount", "0") if isinstance(settled, Mapping) else "0",
        label="settled rounded_amount",
    )
    estimate_amount = _as_decimal(
        cast(Mapping[str, Any], estimate).get("rounded_amount", "0") if isinstance(estimate, Mapping) else "0",
        label="estimate rounded_amount",
    )
    variance = settled_amount - observed_amount
    unresolved = []
    completion_status = str(payload.get("completion_status", "")).strip().upper()
    ambiguous_completion = completion_status == "PROVIDER_COMPLETED_CLIENT_TIMEOUT"
    if observed is None:
        unresolved.append("missing_observed_usage")
    if settled is None:
        unresolved.append("missing_settled_usage")
    if duplicates:
        unresolved.append("duplicate_provider_identities")
    if ambiguous_completion:
        unresolved.append("ambiguous_provider_completed_client_timeout")
    return {
        "schema_version": RECONCILIATION_SCHEMA,
        "estimate_amount": str(estimate_amount),
        "observed_amount": str(observed_amount),
        "settled_amount": str(settled_amount),
        "variance_amount": str(variance),
        "provider_ids": dict(provider_ids),
        "completion_status": completion_status or "UNSPECIFIED",
        "duplicate_provider_identities": duplicates,
        "unresolved": unresolved,
        "explicit_recovery_required": bool(unresolved),
        "retry_permitted": not ambiguous_completion and not unresolved,
        "status": "RECONCILED" if not unresolved else "RECONCILIATION_PENDING",
    }


def summarize_ledger(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    attempt_costs: list[Decimal] = []
    accepted_costs: list[Decimal] = []
    latencies_ms: list[int] = []
    cache_ratios: list[float] = []
    retries = 0
    state_counter: Counter[str] = Counter()
    waste_counter: Counter[str] = Counter()
    for record in records:
        settlement = record.get("settlement", {})
        if isinstance(settlement, Mapping) and "rounded_amount" in settlement:
            amount = _as_decimal(settlement["rounded_amount"], label="rounded_amount")
            attempt_costs.append(amount)
            if record.get("accepted_outcome") is True:
                accepted_costs.append(amount)
        latency = record.get("duration_ms")
        if isinstance(latency, int) and latency >= 0:
            latencies_ms.append(latency)
        normalized = record.get("normalized_usage", {})
        if isinstance(normalized, Mapping) and normalized.get("status") == "OBSERVED":
            total_input = normalized.get("total_input_tokens")
            cache_read = normalized.get("cache_read_input_tokens")
            if isinstance(total_input, int) and total_input > 0 and isinstance(cache_read, int):
                cache_ratios.append(cache_read / total_input)
        retries += _non_negative_int(record.get("retry_count", 0), label="retry_count")
        state_counter[str(record.get("turn_state", "UNKNOWN"))] += 1
        for waste in cast(list[object], record.get("waste_labels", [])) if isinstance(record.get("waste_labels"), list) else []:
            waste_counter[str(waste)] += 1
    return {
        "schema_version": LEDGER_AGGREGATE_SCHEMA,
        "record_count": len(records),
        "attempt_cost_total": str(sum(attempt_costs, Decimal("0"))),
        "accepted_outcome_cost_total": str(sum(accepted_costs, Decimal("0"))),
        "cost_per_attempt": str((sum(attempt_costs, Decimal("0")) / Decimal(len(attempt_costs))) if attempt_costs else Decimal("0")),
        "cost_per_accepted_outcome": str((sum(accepted_costs, Decimal("0")) / Decimal(len(accepted_costs))) if accepted_costs else Decimal("0")),
        "p50_latency_ms": _percentile(latencies_ms, 50),
        "p95_latency_ms": _percentile(latencies_ms, 95),
        "p50_cache_hit_ratio": _percentile_float(cache_ratios, 50),
        "p95_cache_hit_ratio": _percentile_float(cache_ratios, 95),
        "retry_count_total": retries,
        "turn_states": dict(state_counter),
        "waste_taxonomy": dict(waste_counter),
    }


def _group_key(record: Mapping[str, Any], *, dimension: str) -> str:
    if dimension == "accepted_outcome":
        outcome = record.get("accepted_outcome")
        if outcome is True:
            return "accepted"
        if outcome is False:
            return "rejected"
        return "unknown"
    value = record.get(dimension)
    if value in {None, ""}:
        return "UNKNOWN"
    return str(value)


def aggregate_ledger_by_dimension(
    records: Sequence[Mapping[str, Any]],
    *,
    dimension: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault(_group_key(record, dimension=dimension), []).append(record)
    return {
        key: summarize_ledger(grouped[key])
        for key in sorted(grouped)
    }


def _percentile(values: Sequence[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, (len(ordered) * percentile - 1) // 100))
    return ordered[index]


def _percentile_float(values: Sequence[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, (len(ordered) * percentile - 1) // 100))
    return round(ordered[index], 6)


def redacted_evidence_report(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    compact_records = []
    for record in records:
        compact: dict[str, Any] = {}
        for key, value in record.items():
            key_text = str(key)
            if key_text in PROHIBITED_COMPACT_FIELDS:
                compact[f"{key_text}_sha256"] = _sha256_bytes(json.dumps(value, sort_keys=True).encode("utf-8"))
                compact[f"{key_text}_size_bytes"] = len(json.dumps(value, sort_keys=True).encode("utf-8"))
                continue
            compact[key_text] = value
        compact_records.append(compact)
    return {
        "schema_version": COMPACT_REPORT_SCHEMA,
        "generated_at_utc": _utc_now(),
        "record_count": len(compact_records),
        "records": compact_records,
    }


def load_runtime_ledger_records(
    project_root: Path | None = None,
    *,
    ledger_path: Path | None = None,
) -> list[dict[str, Any]]:
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    target = (ledger_path or (root / DEFAULT_RUNTIME_LEDGER_RELATIVE_PATH)).resolve()
    if not target.is_file():
        return []
    return LedgerStore(target).read_all()


def classify_generated_application_token_economics(
    *,
    requirements_text: str | None = None,
    runtime_llm_calls_default: int = 0,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if runtime_llm_calls_default > 0:
        return {
            "status": "APPLICABLE",
            "reason": "generated architecture declares runtime LLM activity",
            "runtime_llm_calls_default": runtime_llm_calls_default,
        }
    candidates = [requirements_text or ""]
    if metadata is not None:
        candidates.append(json.dumps(dict(metadata), sort_keys=True))
    combined = " ".join(candidates).lower()
    if any(marker in combined for marker in LLM_ACTIVITY_MARKERS):
        return {
            "status": "APPLICABLE",
            "reason": "requirements or metadata mention LLM or model activity",
            "runtime_llm_calls_default": runtime_llm_calls_default,
        }
    return {
        "status": "NOT_APPLICABLE",
        "reason": "no LLM, agent, or model activity is declared in the generated application contract",
        "runtime_llm_calls_default": runtime_llm_calls_default,
    }


def build_token_economics_summary(project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    config_root = default_config_root(root)
    cards = load_rate_cards(config_root)
    model_registry = load_model_registry(config_root)
    governance = load_governance_policy(config_root)
    artifact_registry = load_artifact_ownership_registry(config_root)
    budget = load_budget_envelope(config_root / "budgets" / "default_stage_budget.json")
    requested_time = datetime.now(timezone.utc)
    generation_metadata = root / "workspace" / "factory_generated" / "upi_dispute_resolution" / "generated_application" / "generation_metadata.json"
    applicability = {
        "status": "NOT_APPLICABLE",
        "reason": "generated application metadata is not available yet",
        "runtime_llm_calls_default": 0,
    }
    if generation_metadata.is_file():
        metadata = _json_object(generation_metadata)
        applicability = classify_generated_application_token_economics(
            metadata=metadata,
            runtime_llm_calls_default=int(metadata.get("llm_calls", 0)),
        )
    runtime_root = root / "workspace" / "token_economics_runtime"
    return {
        "schema_version": "token-economics-portal-summary.v1",
        "generated_at_utc": _utc_now(),
        "rate_cards": {
            "count": len(cards),
            "ids": [card.rate_card_id for card in cards],
            "units": sorted({card.currency_or_credit_unit for card in cards}),
            "entries": [
                {
                    "rate_card_id": card.rate_card_id,
                    "unit": card.currency_or_credit_unit,
                    "effective_from": card.payload["effective_from"],
                    "effective_to": card.payload.get("effective_to"),
                    "contract_id": card.payload["contract_id"],
                    "stale": card.effective_from
                    < requested_time - timedelta(days=card.staleness_threshold_days),
                    "provenance": dict(cast(Mapping[str, Any], card.payload.get("provenance", {}))),
                }
                for card in cards
            ],
        },
        "model_routes": {
            "count": len(cast(list[object], model_registry["routes"])),
            "policy_version": model_registry.get("policy_version"),
        },
        "governance": {
            "policy_version": governance.get("policy_version"),
            "decision_roles": governance.get("decision_rights", {}),
            "incident_classes": governance.get("incident_classes", []),
        },
        "artifact_ownership": {
            "family_count": len(cast(list[object], artifact_registry["families"])),
            "runtime_root": str(runtime_root),
        },
        "default_stage_budget": {
            "budget_id": budget["budget_id"],
            "unit": budget["unit"],
            "rate_card_id": budget["rate_card_id"],
            "soft_limit": budget["soft_limit"],
            "hard_limit": budget["hard_limit"],
            "warning_policy": budget.get("warning_policy"),
            "overrun_policy": budget.get("overrun_policy"),
        },
        "generated_application_applicability": applicability,
        "operator_visibility": {
            "estimate_vs_observed_vs_settled": True,
            "token_breakdown": True,
            "budget_vs_runtime_controls": True,
            "aggregation_levels": [
                "per_stage",
                "per_run",
                "per_application",
                "per_outcome",
            ],
            "cost_per_accepted_outcome": True,
            "reconciliation_variance": True,
        },
        "mock_boundaries": {
            "live_provider_calls_allowed": False,
            "real_payment_calls": "disabled",
            "runtime_llm_calls_default": 0,
        },
    }


def build_token_economics_operator_surface(
    project_root: Path | None = None,
    *,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    config_root = default_config_root(root)
    summary = build_token_economics_summary(root)
    budget = load_budget_envelope(config_root / "budgets" / "default_stage_budget.json")
    records = load_runtime_ledger_records(root, ledger_path=ledger_path)
    overall = summarize_ledger(records)
    latest = records[-1] if records else {}
    latest_normalized = latest.get("normalized_usage") if isinstance(latest.get("normalized_usage"), Mapping) else None
    observed_input = (
        int(latest_normalized["total_input_tokens"])
        if isinstance(latest_normalized, Mapping) and isinstance(latest_normalized.get("total_input_tokens"), int)
        else None
    )
    observed_output = (
        int(latest_normalized["total_output_tokens"])
        if isinstance(latest_normalized, Mapping) and isinstance(latest_normalized.get("total_output_tokens"), int)
        else None
    )
    decision = authorize_budget(
        budget,
        reserved_amount="0",
        prior_spend_amount=overall["attempt_cost_total"],
        observed_raw_input_tokens=observed_input,
        observed_output_tokens=observed_output,
    )

    def _usage_view(name: str) -> dict[str, Any]:
        payload = latest.get(name)
        if isinstance(payload, Mapping):
            return {"status": "RECORDED", "payload": dict(payload)}
        return {"status": "NOT_RECORDED", "payload": None}

    token_breakdown = {
        "status": "UNKNOWN",
        "total_input_tokens": "UNKNOWN",
        "cache_read_input_tokens": "UNKNOWN",
        "cache_write_input_tokens": "UNKNOWN",
        "uncached_input_tokens": "UNKNOWN",
        "total_output_tokens": "UNKNOWN",
        "reasoning_output_tokens": "UNKNOWN",
        "reasoning_subset_of_total_output": True,
    }
    if isinstance(latest_normalized, Mapping):
        token_breakdown = {
            "status": str(latest_normalized.get("status", "UNKNOWN")),
            "total_input_tokens": latest_normalized.get("total_input_tokens", "UNKNOWN"),
            "cache_read_input_tokens": latest_normalized.get("cache_read_input_tokens", "UNKNOWN"),
            "cache_write_input_tokens": latest_normalized.get("cache_write_input_tokens", "UNKNOWN"),
            "uncached_input_tokens": latest_normalized.get("uncached_input_tokens", "UNKNOWN"),
            "total_output_tokens": latest_normalized.get("total_output_tokens", "UNKNOWN"),
            "reasoning_output_tokens": latest_normalized.get("reasoning_output_tokens", "UNKNOWN"),
            "reasoning_subset_of_total_output": True,
        }

    reconciliation = latest.get("reconciliation") if isinstance(latest.get("reconciliation"), Mapping) else None
    ledger_path_value = ledger_path if ledger_path is not None else root / DEFAULT_RUNTIME_LEDGER_RELATIVE_PATH
    return {
        "schema_version": "token-economics-operator-surface.v1",
        "generated_at_utc": _utc_now(),
        "summary": summary,
        "default_stage_budget": {
            "budget_id": budget["budget_id"],
            "unit": budget["unit"],
            "soft_limit": budget["soft_limit"],
            "hard_limit": budget["hard_limit"],
            "raw_input_anomaly_limit": budget["raw_input_anomaly_limit"],
            "output_limit": budget["output_limit"],
            "rate_card_id": budget["rate_card_id"],
            "warning_policy": budget.get("warning_policy"),
            "overrun_policy": budget.get("overrun_policy"),
        },
        "usage_views": {
            "estimate": _usage_view("estimate"),
            "observed": {
                "status": "RECORDED" if isinstance(latest_normalized, Mapping) else "NOT_RECORDED",
                "payload": dict(latest_normalized) if isinstance(latest_normalized, Mapping) else None,
            },
            "settled": _usage_view("settlement"),
            "token_breakdown": token_breakdown,
        },
        "budget_controls": {
            "status": "available",
            "decision": decision,
            "blocked_next_call": decision["authorize_next_model_call"] is False,
            "warning_reasons": list(decision["warnings"]),
            "blocking_reasons": list(decision["blocks"]),
        },
        "aggregations": {
            "overall": overall,
            "per_stage": aggregate_ledger_by_dimension(records, dimension="stage_id"),
            "per_run": aggregate_ledger_by_dimension(records, dimension="run_id"),
            "per_application": aggregate_ledger_by_dimension(records, dimension="application_id"),
            "per_outcome": aggregate_ledger_by_dimension(records, dimension="accepted_outcome"),
        },
        "reconciliation": {
            "status": "RECORDED" if reconciliation is not None else "NOT_RECORDED",
            "latest": dict(reconciliation) if reconciliation is not None else None,
            "unresolved_records": sum(
                1
                for record in records
                if isinstance(record.get("reconciliation"), Mapping)
                and cast(Mapping[str, Any], record["reconciliation"]).get("status") != "RECONCILED"
            ),
        },
        "runtime_ledger": {
            "path": str(ledger_path_value),
            "record_count": len(records),
            "latest_recorded_at_utc": latest.get("recorded_at_utc") if isinstance(latest, Mapping) else None,
        },
        "policy_incidents": summary["governance"]["incident_classes"],
    }


class LedgerStore:
    """Append-only JSONL ledger with duplicate settlement protection."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        items: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            loaded = json.loads(line)
            if isinstance(loaded, dict):
                items.append(cast(dict[str, Any], loaded))
        return items

    def append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        duplicate_identity = self._duplicate_identity(record)
        if duplicate_identity is not None:
            for existing in self.read_all():
                if self._duplicate_identity(existing) == duplicate_identity:
                    raise TokenEconomicsError(f"duplicate ledger identity rejected: {duplicate_identity}")
        payload = dict(record)
        payload.setdefault("recorded_at_utc", _utc_now())
        material = json.dumps(payload, sort_keys=True) + "\n"
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        try:
            os.write(fd, material.encode("utf-8"))
        finally:
            os.close(fd)
        return payload

    def _duplicate_identity(self, record: Mapping[str, Any]) -> str | None:
        for key in ("provider_turn_id", "provider_response_id", "settlement_id", "idempotency_key"):
            value = record.get(key)
            if isinstance(value, str) and value:
                return f"{key}:{value}"
        return None

def rate_card_match_key_fields() -> tuple[str, ...]:
    return (
        "provider",
        "billing_surface",
        "model_resolved",
        "model_version",
        "service_tier",
        "context_band",
        "modality",
        "region_or_residency",
        "currency_or_credit_unit",
        "contract_id",
    )
