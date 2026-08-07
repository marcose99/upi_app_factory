from __future__ import annotations

import hashlib


PII_DIGEST_SALT = "upi-app-factory-local-generated-blueprint-v1"


def redact_upi(value: str) -> str:
    if value.startswith("[masked:"):
        return value.removeprefix("[masked:").removesuffix("]")
    if "@" not in value:
        return "[redacted]"
    prefix, suffix = value.split("@", 1)
    visible = prefix[:2]
    return f"{visible}***@{suffix}"


def upi_storage_digest(value: str) -> str:
    digest = hashlib.sha256(f"{PII_DIGEST_SALT}:{value}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def stored_masked_upi(value: str) -> str:
    return f"[masked:{redact_upi(value)}]"
