from __future__ import annotations


def redact_upi(value: str) -> str:
    if "@" not in value:
        return "[redacted]"
    prefix, suffix = value.split("@", 1)
    visible = prefix[:2]
    return f"{visible}***@{suffix}"
