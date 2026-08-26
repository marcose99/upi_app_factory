from __future__ import annotations

import json
from pathlib import Path

from factory.quality_assurance.reporting import write_report_suite


def test_reports_are_distinct_typed_fact_projections(tmp_path: Path) -> None:
    index = write_report_suite(
        tmp_path,
        kind="application",
        context={
            "source_fact_ids": ["FACT-1"],
            "sections": [
                {"heading": "Shared identity", "content": "FACT-1"},
                {"heading": "Security facts", "content": "SEC-1", "projection_ids": ["security_supply_chain"]},
            ],
            "evidence_ids_by_projection": {"security_supply_chain": ["SEC-1"]},
        },
    )
    documents = [json.loads((tmp_path / row["json_path"]).read_text()) for row in index["reports"]]
    assert len({doc["projection_id"] for doc in documents}) == 14
    assert len({json.dumps(doc["sections"], sort_keys=True) for doc in documents}) == 14
    security = next(doc for doc in documents if doc["projection_id"] == "security_supply_chain")
    executive = next(doc for doc in documents if doc["projection_id"] == "executive")
    assert security["evidence_ids"] == ["SEC-1"]
    assert any(section["heading"] == "Security facts" for section in security["sections"])
    assert all(section["heading"] != "Security facts" for section in executive["sections"])
    assert security["source_fact_ids"] == ["FACT-1"]
