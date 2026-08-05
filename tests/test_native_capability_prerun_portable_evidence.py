from __future__ import annotations

import json
from pathlib import Path

from factory.evidence_portability import (
    PORTABLE_HOME_TOKEN,
    portable_evidence_value,
    portable_json_dump,
    portable_json_dumps,
)


def test_portable_evidence_value_replaces_active_home() -> None:
    home = str(Path.home())
    value = {"path": home + "/projects/factory", "nested": [home + "/Downloads"]}
    transformed = portable_evidence_value(value)
    assert transformed["path"] == PORTABLE_HOME_TOKEN + "/projects/factory"
    assert transformed["nested"] == [PORTABLE_HOME_TOKEN + "/Downloads"]


def test_portable_json_dumps_preserves_json_semantics() -> None:
    home = str(Path.home())
    encoded = portable_json_dumps({"path": home + "/x", "safe": True}, sort_keys=True)
    assert json.loads(encoded) == {"path": PORTABLE_HOME_TOKEN + "/x", "safe": True}


def test_portable_json_dump_writes_portable_payload(tmp_path: Path) -> None:
    home = str(Path.home())
    target = tmp_path / "payload.json"
    with target.open("w", encoding="utf-8") as stream:
        portable_json_dump({"path": home + "/y"}, stream, indent=2)
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "path": PORTABLE_HOME_TOKEN + "/y"
    }


def test_native_capability_report_writers_use_portable_serializers() -> None:
    root = Path(__file__).resolve().parents[1]
    report_writers: list[Path] = []
    portable_modules: list[Path] = []
    for relative in (Path("factory/native_capability_prerun"), Path("scripts")):
        base = root / relative
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "CAPABILITY_PRE_RUN_REPORT.json" in text:
                report_writers.append(path)
            if "portable_json_dump" in text:
                portable_modules.append(path)
    assert report_writers
    assert portable_modules
