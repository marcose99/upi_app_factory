from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACKED_RUNTIME = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py"
)
TEMPLATE_RUNTIME = (
    PROJECT_ROOT
    / "factory/templates/mock_dispute_app/generated_application/app/interfaces/api/main.py"
)
COMPATIBILITY_MARKERS = (
    '@app.get("/runtime/health")',
    '@app.get("/capabilities")',
    '@app.post("/scenario/echo", response_model=None)',
    '@app.get("/missing")',
    '"replay_status": 200',
    '"validation_error"',
)


def test_authoritative_runtime_and_template_preserve_portfolio_compatibility_routes() -> None:
    for path in (TRACKED_RUNTIME, TEMPLATE_RUNTIME):
        text = path.read_text(encoding="utf-8")
        for marker in COMPATIBILITY_MARKERS:
            assert marker in text
