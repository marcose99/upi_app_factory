from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def write_audit_event(action: str, target: str, result: str, details: dict[str, Any] | None = None) -> str:
    event_id = f"AUD-{uuid4().hex[:12]}"
    path = Path(os.getenv("AUDIT_LOG_PATH", "workspace/runs/audit_events.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": event_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "target": target,
        "result": result,
        "details": details or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event_id
