from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TextIO

PORTABLE_HOME_TOKEN = "__USER_HOME__"


def portable_evidence_value(value: Any, *, home: str | None = None) -> Any:
    """Return a JSON-compatible value with the active home path neutralized."""
    resolved_home = home if home is not None else str(Path.home())
    if isinstance(value, str):
        return value.replace(resolved_home, PORTABLE_HOME_TOKEN)
    if isinstance(value, dict):
        return {
            portable_evidence_value(key, home=resolved_home): portable_evidence_value(
                item,
                home=resolved_home,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [portable_evidence_value(item, home=resolved_home) for item in value]
    if isinstance(value, tuple):
        return tuple(
            portable_evidence_value(item, home=resolved_home) for item in value
        )
    return value


def portable_json_dumps(value: Any, *args: Any, **kwargs: Any) -> str:
    """Serialize JSON after neutralizing the active machine home path."""
    return json.dumps(portable_evidence_value(value), *args, **kwargs)


def portable_json_dump(
    value: Any,
    stream: TextIO,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Write JSON after neutralizing the active machine home path."""
    json.dump(portable_evidence_value(value), stream, *args, **kwargs)
