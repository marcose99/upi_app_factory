from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from tools.factory_control_plane.common import ControlPlaneError, write_json
from tools.factory_control_plane.engine import ControlPlaneEngine


class InboxWorker:
    def __init__(self, inbox_root: Path, engine: ControlPlaneEngine) -> None:
        self.root = inbox_root.resolve()
        self.engine = engine
        for name in ("pending", "processing", "completed", "failed"):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def run_once(self) -> dict[str, Any]:
        manifests = sorted((self.root / "pending").glob("*.json"))
        if not manifests:
            return {"status": "idle"}
        pending = manifests[0]
        processing = self.root / "processing" / pending.name
        pending.replace(processing)
        try:
            result = self.engine.run(processing)
        except Exception as exc:
            failed = self.root / "failed" / processing.name
            processing.replace(failed)
            write_json(
                failed.with_suffix(failed.suffix + ".result.json"),
                {"status": "failed", "error": str(exc)},
            )
            return {"status": "failed", "manifest": str(failed), "error": str(exc)}
        completed = self.root / "completed" / processing.name
        shutil.copy2(processing, completed)
        processing.unlink()
        write_json(completed.with_suffix(completed.suffix + ".result.json"), result)
        return {"status": "completed", "manifest": str(completed), "result": result}

    def run_polling(self, max_empty_polls: int = 1) -> dict[str, Any]:
        if max_empty_polls < 1:
            raise ControlPlaneError("max_empty_polls must be positive")
        processed = 0
        empty = 0
        while empty < max_empty_polls:
            result = self.run_once()
            if result["status"] == "idle":
                empty += 1
            else:
                processed += 1
                empty = 0
        return {"status": "stopped", "processed": processed}
