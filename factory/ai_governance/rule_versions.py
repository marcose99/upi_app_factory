from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping

from .models import GovernanceError


def _canonical(value: object) -> bytes:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class RuleVersion:
    version_id: str
    previous_hash: str | None
    payload: Mapping[str, Any]
    digest: str


class RuleVersionChain:
    def __init__(self) -> None:
        self._versions: list[RuleVersion] = []
        self._active: str | None = None

    @property
    def versions(self) -> tuple[RuleVersion, ...]:
        return tuple(self._versions)

    @property
    def active(self) -> RuleVersion | None:
        return next((item for item in self._versions if item.version_id == self._active), None)

    def append(self, version_id: str, payload: Mapping[str, Any]) -> RuleVersion:
        if not version_id or any(item.version_id == version_id for item in self._versions):
            raise GovernanceError("rule version id is empty or duplicate")
        previous = self._versions[-1].digest if self._versions else None
        frozen_payload = _freeze(json.loads(_canonical(payload).decode()))
        assert isinstance(frozen_payload, Mapping)
        digest = hashlib.sha256(_canonical({"version_id": version_id, "previous_hash": previous, "payload": frozen_payload})).hexdigest()
        version = RuleVersion(version_id, previous, frozen_payload, digest)
        self._versions.append(version)
        self._active = version_id
        return version

    def select(self, version_id: str) -> RuleVersion:
        selected = next((item for item in self._versions if item.version_id == version_id), None)
        if selected is None:
            raise GovernanceError("unknown immutable rule version")
        self._active = version_id
        return selected

    rollback = select

    def verify(self) -> bool:
        previous = None
        for item in self._versions:
            expected = hashlib.sha256(_canonical({"version_id": item.version_id, "previous_hash": previous, "payload": item.payload})).hexdigest()
            if item.previous_hash != previous or item.digest != expected:
                return False
            previous = item.digest
        return True
