from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, cast

from tools.factory_control_plane.common import (
    ControlPlaneError,
    canonical_json,
    sha256_bytes,
    utc_now,
)
from tools.factory_control_plane.lifecycle import LifecycleState, advance
from tools.factory_control_plane.manifest import Activity, CampaignManifest


SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id TEXT PRIMARY KEY,
  manifest_digest TEXT NOT NULL,
  baseline TEXT NOT NULL,
  lifecycle_state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  event_hash TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE TABLE IF NOT EXISTS activities (
  campaign_id TEXT NOT NULL,
  activity_id TEXT NOT NULL,
  input_digest TEXT NOT NULL,
  status TEXT NOT NULL,
  result_json TEXT,
  PRIMARY KEY(campaign_id, activity_id),
  FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE TABLE IF NOT EXISTS policy_decisions (
  decision_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  activity_id TEXT,
  decision_json TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE TABLE IF NOT EXISTS incidents (
  incident_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  activity_id TEXT,
  failure_class TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  campaign_id TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
"""


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> StateStore:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection:
            yield self.connection

    def create_or_load_campaign(
        self,
        manifest: CampaignManifest,
        baseline: str,
    ) -> LifecycleState:
        row = self.connection.execute(
            "SELECT manifest_digest, baseline, lifecycle_state FROM campaigns WHERE campaign_id=?",
            (manifest.campaign_id,),
        ).fetchone()
        now = utc_now()
        if row is None:
            self.connection.execute(
                "INSERT INTO campaigns VALUES (?, ?, ?, ?, ?, ?)",
                (
                    manifest.campaign_id,
                    manifest.digest,
                    baseline,
                    LifecycleState.NEW.value,
                    now,
                    now,
                ),
            )
            self.connection.commit()
            self.emit_event(manifest.campaign_id, "campaign_created", {"baseline": baseline})
            return LifecycleState.NEW
        if row["manifest_digest"] != manifest.digest:
            raise ControlPlaneError("manifest drift detected for existing campaign")
        if row["baseline"] != baseline:
            raise ControlPlaneError("baseline drift detected for existing campaign")
        return LifecycleState(str(row["lifecycle_state"]))

    def lifecycle_state(self, campaign_id: str) -> LifecycleState:
        row = self.connection.execute(
            "SELECT lifecycle_state FROM campaigns WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        if row is None:
            raise ControlPlaneError("unknown campaign")
        return LifecycleState(str(row["lifecycle_state"]))

    def set_state(self, campaign_id: str, target: LifecycleState) -> None:
        current = self.lifecycle_state(campaign_id)
        next_state = advance(current, target)
        if next_state == current:
            return
        self.connection.execute(
            "UPDATE campaigns SET lifecycle_state=?, updated_at=? WHERE campaign_id=?",
            (next_state.value, utc_now(), campaign_id),
        )
        self.connection.commit()
        self.emit_event(
            campaign_id,
            "state_transition",
            {"from": current.value, "to": next_state.value},
        )

    def emit_event(self, campaign_id: str, event_type: str, payload: dict[str, Any]) -> str:
        sequence = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM events WHERE campaign_id=?", (campaign_id,)
            ).fetchone()[0]
        ) + 1
        body = {
            "campaign_id": campaign_id,
            "sequence": sequence,
            "event_type": event_type,
            "payload": payload,
        }
        event_hash = sha256_bytes(canonical_json(body))
        self.connection.execute(
            "INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)",
            (
                event_hash,
                campaign_id,
                sequence,
                event_type,
                canonical_json(payload).decode(),
                utc_now(),
            ),
        )
        self.connection.commit()
        return event_hash

    def record_policy(
        self,
        campaign_id: str,
        activity_id: str | None,
        decision: dict[str, Any],
    ) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO policy_decisions VALUES (?, ?, ?, ?)",
            (
                str(decision["decision_id"]),
                campaign_id,
                activity_id,
                canonical_json(decision).decode(),
            ),
        )
        self.connection.commit()
        self.emit_event(campaign_id, "policy_decision", decision)

    def activity_status(
        self,
        campaign_id: str,
        activity: Activity,
    ) -> tuple[str, dict[str, Any] | None]:
        row = self.connection.execute(
            "SELECT input_digest, status, result_json "
            "FROM activities WHERE campaign_id=? AND activity_id=?",
            (campaign_id, activity.id),
        ).fetchone()
        if row is None:
            return ("pending", None)
        if row["input_digest"] != activity.digest:
            raise ControlPlaneError(f"changed inputs for activity {activity.id} rejected")
        result = (
            None
            if row["result_json"] is None
            else cast(dict[str, Any], json.loads(str(row["result_json"])))
        )
        return (str(row["status"]), result)

    def record_activity(
        self,
        campaign_id: str,
        activity: Activity,
        status: str,
        result: dict[str, Any],
    ) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO activities VALUES (?, ?, ?, ?, ?)",
            (campaign_id, activity.id, activity.digest, status, canonical_json(result).decode()),
        )
        self.connection.commit()
        self.emit_event(
            campaign_id,
            "activity_result",
            {"activity_id": activity.id, "status": status},
        )

    def record_incident(
        self,
        campaign_id: str,
        activity_id: str | None,
        failure_class: str,
        payload: dict[str, Any],
    ) -> str:
        incident = {
            "campaign_id": campaign_id,
            "activity_id": activity_id,
            "failure_class": failure_class,
            **payload,
        }
        incident_id = sha256_bytes(canonical_json(incident))
        self.connection.execute(
            "INSERT OR REPLACE INTO incidents VALUES (?, ?, ?, ?, ?)",
            (
                incident_id,
                campaign_id,
                activity_id,
                failure_class,
                canonical_json(incident).decode(),
            ),
        )
        self.connection.commit()
        self.emit_event(campaign_id, "incident", incident)
        return incident_id

    def summary(self, campaign_id: str) -> dict[str, Any]:
        state = self.lifecycle_state(campaign_id).value
        activities = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM activities WHERE campaign_id=? AND status='completed'",
                (campaign_id,),
            ).fetchone()[0]
        )
        incidents = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM incidents WHERE campaign_id=?", (campaign_id,)
            ).fetchone()[0]
        )
        events = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM events WHERE campaign_id=?", (campaign_id,)
            ).fetchone()[0]
        )
        return {
            "campaign_id": campaign_id,
            "state": state,
            "completed_activities": activities,
            "incidents": incidents,
            "events": events,
        }

    def export_events(self, campaign_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT event_hash, sequence, event_type, payload_json, created_at "
            "FROM events WHERE campaign_id=? ORDER BY sequence",
            (campaign_id,),
        ).fetchall()
        return [
            {
                "event_hash": str(row["event_hash"]),
                "sequence": int(row["sequence"]),
                "event_type": str(row["event_type"]),
                "payload": json.loads(str(row["payload_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]
