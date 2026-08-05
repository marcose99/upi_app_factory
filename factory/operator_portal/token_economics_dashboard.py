from __future__ import annotations

from pathlib import Path
from typing import Any

from factory.token_economics import TokenEconomicsError, build_token_economics_operator_surface


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_dashboard(project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or PROJECT_ROOT).resolve()
    try:
        return {
            "status": "available",
            **build_token_economics_operator_surface(root),
        }
    except (OSError, ValueError, TokenEconomicsError):
        return {
            "status": "missing",
            "reason": "token_economics_configuration_unavailable",
            "config_root": str(root / "config" / "token_economics"),
        }
