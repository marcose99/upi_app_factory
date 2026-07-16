from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from urllib.parse import urljoin, urlparse

from factory.operator_portal.runtime_contracts import RuntimeContractError


ALLOWED_METHODS: Final[set[str]] = {"GET", "POST"}
MAX_PAYLOAD_BYTES: Final[int] = 64 * 1024
MAX_RESPONSE_BYTES: Final[int] = 512 * 1024
REQUEST_TIMEOUT_SECONDS: Final[float] = 3.0
CONCURRENCY_LIMIT: Final[int] = 2


@dataclass(frozen=True)
class NormalizedRuntimeURL:
    url: str
    method: str
    path: str


def _is_loopback_host(host: str | None) -> bool:
    return host == "127.0.0.1"


def normalize_runtime_url(*, base_url: str, method: str, endpoint: str, owned_port: int) -> NormalizedRuntimeURL:
    normalized_method = method.upper()
    if normalized_method not in ALLOWED_METHODS:
        raise RuntimeContractError("method is not allow-listed")
    if endpoint.startswith("//") or "://" in endpoint:
        raise RuntimeContractError("absolute scenario endpoints are not allowed")
    if ".." in endpoint.split("/"):
        raise RuntimeContractError("runtime URL path traversal rejected")
    parsed_base = urlparse(base_url)
    if parsed_base.scheme != "http" or not _is_loopback_host(parsed_base.hostname):
        raise RuntimeContractError("runtime base URL must be loopback HTTP")
    if parsed_base.port != owned_port:
        raise RuntimeContractError("runtime base URL must use the owned port")
    url = urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))
    parsed = urlparse(url)
    if parsed.scheme != "http" or not _is_loopback_host(parsed.hostname) or parsed.port != owned_port:
        raise RuntimeContractError("runtime URL escaped the loopback owned-port boundary")
    if ".." in parsed.path.split("/"):
        raise RuntimeContractError("runtime URL path traversal rejected")
    return NormalizedRuntimeURL(url=url, method=normalized_method, path=parsed.path)


def validate_redirect_location(*, base_url: str, location: str, owned_port: int) -> str:
    resolved = urljoin(base_url.rstrip("/") + "/", location)
    parsed = urlparse(resolved)
    if parsed.scheme != "http" or not _is_loopback_host(parsed.hostname) or parsed.port != owned_port:
        raise RuntimeContractError("redirect target escaped loopback owned-port boundary")
    return resolved
