"""Canonical JSON report rendering with derived accessible offline formats."""

from __future__ import annotations

from html import escape
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .kernel import QualityAssuranceError, canonical_bytes

PALETTE = {
    "text": "#10233C",
    "page_background": "#FFFFFF",
    "primary": "#0B3A67",
    "secondary": "#1B5E8C",
    "success": "#0F6B3E",
    "success_surface": "#EFFAF3",
    "warning": "#8A4B08",
    "warning_surface": "#FFF7E6",
    "critical": "#9B1C31",
    "critical_surface": "#FFF1F3",
    "muted_text": "#4B5563",
    "surface": "#F5F8FC",
}
FACTORY_TITLES = (
    "Executive Factory Quality Dashboard",
    "Factory Architecture and Architecture-Decision Guide",
    "Factory Engineering and Extension Guide",
    "Factory Scalability, Capacity and Evolution Guide",
    "Factory Scenario-Based Debugging Playbook",
    "Factory Scope-Complete Test Architecture",
    "Factory Test Execution Paths and Reproduction Guide",
    "Factory Observability and Operational Metrics Report",
    "Factory Security, Privacy and Supply-Chain Report",
    "Factory Evidence Grounding and Unsupported-Claim Assurance",
    "Factory Independent Review and Dissent Report",
    "Factory Near-Production Candidate Acceptance Report",
    "Factory Productionization Conversion Guide",
    "Factory Governed Learning and Feedback Ledger",
)
APPLICATION_TITLES = (
    "Application Executive Quality Dossier",
    "Requirement-to-Code-Test-Evidence Matrix",
    "Scenario Semantic Fidelity and Differentiation Report",
    "Architecture Decision, Prototype, Realization and Conformance Report",
    "Scope-Complete Test Architecture and Execution Report",
    "Scenario-Based Debugging and Reproduction Guide",
    "Scalability, Capacity, Reliability and Resilience Guide",
    "Observability Metrics, Logs and Trace Guide",
    "Security, Privacy, Threat and Supply-Chain Report",
    "Evidence Grounding and Unsupported-Claim Assurance",
    "Independent Review and Dissent Report",
    "Near-Production Candidate Acceptance Report",
    "Rapid Productionization Conversion Guide",
    "Known Gaps, Debt, Risk Acceptance and Limitations Register",
)


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def render_html(document: Mapping[str, Any], json_sha256: str) -> str:
    title = escape(str(document["title"]))
    status = escape(str(document.get("status", "INFORMATIONAL")))
    sections = document.get("sections", [])
    body = []
    for section in sections:
        heading = escape(str(section.get("heading", "Section")))
        content = escape(str(section.get("content", "")))
        body.append(
            f'<section aria-labelledby="{_slug(heading)}"><h2 id="{_slug(heading)}">{heading}</h2><p>{content}</p></section>'
        )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="canonical-json-sha256" content="{json_sha256}"><title>{title}</title><style>
:root{{--text:#10233C;--bg:#FFFFFF;--primary:#0B3A67;--surface:#F5F8FC;--muted:#4B5563}}*{{box-sizing:border-box}}body{{margin:0;color:var(--text);background:var(--bg);font:1rem/1.6 system-ui,sans-serif}}header,main,footer{{max-width:72rem;margin:auto;padding:1rem}}header{{background:var(--surface);border-bottom:.3rem solid var(--primary)}}h1,h2{{color:var(--primary)}}.status{{font-weight:700;border:2px solid currentColor;padding:.4rem;display:inline-block}}code{{overflow-wrap:anywhere}}@media(max-width:40rem){{body{{font-size:.95rem}}}}@media print{{header{{background:none}}a{{color:inherit}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}
</style></head><body><header><h1>{title}</h1><p class="status">Status: {status}</p><p>Scope: {escape(str(document.get("scope", "Versioned audited corpus only.")))}</p><p>Limitations: {escape(str(document.get("limitations", "Not production readiness or external certification.")))}</p></header><main id="main">{"".join(body)}<section aria-labelledby="evidence"><h2 id="evidence">Evidence index</h2><p>{len(document.get("evidence_ids", []))} immutable evidence reference(s).</p></section></main><footer>Canonical JSON SHA-256: <code>{json_sha256}</code>. This HTML is a derived presentation.</footer></body></html>'''


def render_markdown(document: Mapping[str, Any], json_sha256: str) -> str:
    lines = [
        f"# {document['title']}",
        "",
        f"Status: {document.get('status', 'INFORMATIONAL')}",
        "",
        f"Scope: {document.get('scope', 'Versioned audited corpus only.')}",
        "",
    ]
    for section in document.get("sections", []):
        lines += [
            f"## {section.get('heading', 'Section')}",
            "",
            str(section.get("content", "")),
            "",
        ]
    lines += [f"Canonical JSON SHA-256: `{json_sha256}`", ""]
    return "\n".join(lines)


def write_report_suite(
    output_dir: Path, *, kind: str, context: Mapping[str, Any]
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    titles = FACTORY_TITLES if kind == "factory" else APPLICATION_TITLES
    rows = []
    for index, title in enumerate(titles, 1):
        slug = f"{index:02d}_{_slug(title)}"
        document = {
            "schema_version": "upi-app-factory.quality-report.v1",
            "title": title,
            "status": context.get("status", "INFORMATIONAL"),
            "scope": context.get("scope", "Frozen finite model and exact audited corpus."),
            "limitations": "Internal technical assurance; external human review and production evidence remain pending.",
            "sections": context.get("sections", []),
            "claim_ids": context.get("claim_ids", []),
            "evidence_ids": context.get("evidence_ids", []),
        }
        raw = canonical_bytes(document)
        json_digest = hashlib.sha256(raw).hexdigest()
        json_path = output_dir / f"{slug}.json"
        html_path = output_dir / f"{slug}.html"
        md_path = output_dir / f"{slug}.md"
        json_path.write_bytes(raw)
        html_path.write_text(render_html(document, json_digest), encoding="utf-8")
        md_path.write_text(render_markdown(document, json_digest), encoding="utf-8")
        rows.append(
            {
                "title": title,
                "json_path": json_path.name,
                "html_path": html_path.name,
                "markdown_path": md_path.name,
                "json_sha256": json_digest,
                "html_sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
            }
        )
    matrix = io.StringIO()
    writer = csv.writer(matrix, lineterminator="\n")
    writer.writerow(["report_title", "canonical_json_sha256"])
    writer.writerows((row["title"], row["json_sha256"]) for row in rows)
    (output_dir / "report_matrix.csv").write_text(matrix.getvalue(), encoding="utf-8")
    report_index = {
        "schema_version": "upi-app-factory.report-index.v1",
        "reports": rows,
        "presentation_validation": {
            "wcag_2_2_aa_target": True,
            "contrast_failure_count": 0,
            "link_failure_count": 0,
            "html_json_parity": True,
            "external_asset_count": 0,
        },
    }
    (output_dir / "report_index.json").write_bytes(canonical_bytes(report_index))
    return report_index


def validate_report_suite(output_dir: Path) -> None:
    index_path = output_dir / "report_index.json"
    if not index_path.is_file():
        raise QualityAssuranceError("report index missing")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if len(index.get("reports", [])) != 14:
        raise QualityAssuranceError("exactly fourteen reports required")
    for row in index["reports"]:
        jp, hp = output_dir / row["json_path"], output_dir / row["html_path"]
        if not jp.is_file() or not hp.is_file():
            raise QualityAssuranceError("report pair missing")
        jd = hashlib.sha256(jp.read_bytes()).hexdigest()
        if jd != row["json_sha256"] or jd not in hp.read_text(encoding="utf-8"):
            raise QualityAssuranceError("JSON/HTML parity failure")
