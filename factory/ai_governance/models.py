from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Mapping


class GovernanceError(ValueError):
    """A deterministic, fail-closed governance validation error."""


class LearningClass(IntEnum):
    L0_READ_ONLY_LEARNING = 0
    L1_DETERMINISTIC_SELF_HEAL = 1
    L2_SEMANTIC_ENGINEERING_CANDIDATE = 2
    L3_CANDIDATE_LEARNING_RULE = 3
    L4_PROTECTED_PROMOTION = 4
    L0 = L0_READ_ONLY_LEARNING
    L1 = L1_DETERMINISTIC_SELF_HEAL
    L2 = L2_SEMANTIC_ENGINEERING_CANDIDATE
    L3 = L3_CANDIDATE_LEARNING_RULE
    L4 = L4_PROTECTED_PROMOTION

    @classmethod
    def parse(cls, value: object) -> "LearningClass":
        if not isinstance(value, str):
            raise GovernanceError("learning_class must be a string")
        aliases = {member.name: member for member in cls}
        aliases.update({member.name.split("_", 1)[0]: member for member in cls})
        try:
            return aliases[value]
        except KeyError as exc:
            raise GovernanceError("unknown learning_class") from exc


@dataclass(frozen=True)
class SupplyChainMetadata:
    model: str
    provider: str
    data_sources: tuple[str, ...]

    @classmethod
    def parse(cls, value: object) -> "SupplyChainMetadata":
        if not isinstance(value, Mapping) or set(value) != {"model", "provider", "data_sources"}:
            raise GovernanceError("supply_chain must contain model, provider, and data_sources")
        model = _bounded_string(value["model"], "model")
        provider = _bounded_string(value["provider"], "provider")
        sources = _bounded_strings(value["data_sources"], "data_sources", maximum=32)
        return cls(model, provider, sources)


@dataclass(frozen=True)
class GovernedLearningRequest:
    system_id: str
    system_version: str
    learning_class: LearningClass
    data_classes: tuple[str, ...]
    objective: str
    change_class: str
    change_budget: int
    evaluation_score: float
    held_out_score: float
    requested_promotion: int
    acceptance_bar_delta: float
    supply_chain: SupplyChainMetadata | None = None

    @classmethod
    def parse(cls, value: object) -> "GovernedLearningRequest":
        if not isinstance(value, Mapping):
            raise GovernanceError("governed_learning must be an object")
        required = {
            "system_id", "system_version", "learning_class", "data_classes",
            "objective", "change_class", "change_budget", "evaluation_score",
            "held_out_score", "requested_promotion", "acceptance_bar_delta",
        }
        optional = {"supply_chain"}
        if set(value) - required - optional or required - set(value):
            raise GovernanceError("governed_learning has missing or unknown fields")
        budget = value["change_budget"]
        promotion = value["requested_promotion"]
        delta = value["acceptance_bar_delta"]
        evaluation = value["evaluation_score"]
        held_out = value["held_out_score"]
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            raise GovernanceError("change_budget must be a non-negative integer")
        if isinstance(promotion, bool) or not isinstance(promotion, int) or not 0 <= promotion <= 4:
            raise GovernanceError("requested_promotion must be 0..4")
        for name, score in (("evaluation_score", evaluation), ("held_out_score", held_out)):
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
                raise GovernanceError(f"{name} must be 0..1")
        if isinstance(delta, bool) or not isinstance(delta, (int, float)):
            raise GovernanceError("acceptance_bar_delta must be numeric")
        supply = None if "supply_chain" not in value else SupplyChainMetadata.parse(value["supply_chain"])
        return cls(
            _bounded_string(value["system_id"], "system_id"),
            _bounded_string(value["system_version"], "system_version"),
            LearningClass.parse(value["learning_class"]),
            _bounded_strings(value["data_classes"], "data_classes", maximum=32),
            _bounded_string(value["objective"], "objective"),
            _bounded_string(value["change_class"], "change_class"),
            budget, float(evaluation), float(held_out), promotion, float(delta), supply,
        )


@dataclass(frozen=True)
class GovernanceDecision:
    outcome: str
    reasons: tuple[str, ...]
    request: GovernedLearningRequest | None = None

    @property
    def authorized(self) -> bool:
        return self.outcome == "allow"

    def to_record(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "human_required": self.outcome == "human_gate", "reasons": list(self.reasons)}


def _bounded_string(value: object, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise GovernanceError(f"{name} must be a non-empty bounded string")
    return value


def _bounded_strings(value: object, name: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value or len(value) > maximum:
        raise GovernanceError(f"{name} must be a non-empty bounded list")
    result = tuple(_bounded_string(item, name) for item in value)
    if len(set(result)) != len(result):
        raise GovernanceError(f"{name} contains duplicates")
    return result
