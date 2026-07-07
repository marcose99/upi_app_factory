from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AuditEvent, new_id, utc_now_iso


class AuditLogger:
    def __init__(self, audit_path: Path) -> None:
        self.audit_path = audit_path
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        event_type: str,
        actor: str,
        details: dict[str, Any],
        dispute_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=new_id("audit"),
            event_type=event_type,
            dispute_id=dispute_id,
            actor=actor,
            details=details,
            created_at_utc=utc_now_iso(),
        )
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(), sort_keys=True) + "\n")
        return event
