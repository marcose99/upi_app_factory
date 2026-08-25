from pathlib import Path

from factory.quality_assurance.reporting import PALETTE, validate_report_suite, write_report_suite


def luminance(color: str) -> float:
    values = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def test_json_html_parity_accessibility_and_offline_assets(tmp_path: Path) -> None:
    index = write_report_suite(
        tmp_path,
        kind="application",
        context={"sections": [{"heading": "Scope", "content": "Finite model."}]},
    )
    validate_report_suite(tmp_path)
    assert len(index["reports"]) == 14
    for row in index["reports"]:
        html = (tmp_path / row["html_path"]).read_text()
        assert row["json_sha256"] in html and "<h1>" in html and "@media print" in html
        assert "https://" not in html and "<script" not in html
    ratio = (max(luminance(PALETTE["text"]), luminance(PALETTE["page_background"])) + 0.05) / (
        min(luminance(PALETTE["text"]), luminance(PALETTE["page_background"])) + 0.05
    )
    assert ratio >= 4.5
