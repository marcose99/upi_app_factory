from __future__ import annotations


def mask_upi_id(upi_id: str) -> str:
    if "@" not in upi_id:
        return "***"
    handle, provider = upi_id.split("@", 1)
    if not handle:
        return f"***@{provider}"
    if len(handle) <= 2:
        masked_handle = handle[0] + "***"
    else:
        masked_handle = f"{handle[:2]}***{handle[-1]}"
    return f"{masked_handle}@{provider}"


def assert_no_obvious_real_sensitive_values(text: str) -> None:
    compact_digits = "".join(character for character in text if character.isdigit())
    if len(compact_digits) >= 12:
        raise ValueError("input appears to contain long numeric sensitive data")
