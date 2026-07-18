from __future__ import annotations

from dataclasses import asdict

from upi_factory.rubric_alignment.models import MemoryRecord, MemoryScope, ReviewerFeedback
from upi_factory.rubric_alignment.utils import contains_sensitive


class MemoryStore:
    def __init__(self, *, run_id: str) -> None:
        self.run_id = run_id
        self._records: dict[str, MemoryRecord] = {}

    def remember(self, key: str, value: str, *, scope: MemoryScope, expires_after_runs: int = 1) -> MemoryRecord:
        if contains_sensitive(value):
            record = MemoryRecord(key=key, value="[REJECTED_SENSITIVE_MEMORY]", scope=scope, expires_after_runs=0, created_run_id=self.run_id, sensitive_rejected=True)
            return record
        record = MemoryRecord(key=key, value=value, scope=scope, expires_after_runs=expires_after_runs, created_run_id=self.run_id)
        self._records[f"{scope}:{key}"] = record
        return record

    def recall(self, key: str, *, scope: MemoryScope, run_id: str) -> str | None:
        record = self._records.get(f"{scope}:{key}")
        if record is None or record.created_run_id != run_id:
            return None
        value: str = record.value
        return value

    def reset(self, *, scope: MemoryScope | None = None) -> None:
        if scope is None:
            self._records.clear()
            return
        self._records = {key: value for key, value in self._records.items() if value.scope != scope}

    def expire(self) -> None:
        retained: dict[str, MemoryRecord] = {}
        for key, record in self._records.items():
            if record.expires_after_runs > 1:
                retained[key] = MemoryRecord(record.key, record.value, record.scope, record.expires_after_runs - 1, record.created_run_id)
        self._records = retained

    def snapshot(self) -> list[dict[str, object]]:
        return [asdict(record) for record in self._records.values()]


def apply_feedback(feedback_id: str, text: str, before: str) -> ReviewerFeedback:
    lower = text.lower()
    unsafe = any(term in lower for term in ("ignore safety", "bypass approval", "call live bank", "store phone"))
    if unsafe:
        return ReviewerFeedback(feedback_id, text, False, "contradictory_or_unsafe_feedback", before, before)
    after = f"{before} Reviewer feedback accepted: {text}"
    return ReviewerFeedback(feedback_id, text, True, None, before, after)
