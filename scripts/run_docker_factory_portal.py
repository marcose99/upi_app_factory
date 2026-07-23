#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.operator_portal.web_ui import create_web_ui_app  # noqa: E402


def _require_mock_only_environment() -> None:
    expected = {
        "FACTORY_LLM_ENABLED": {"0", "false", "False"},
        "UPI_APP_FACTORY_LLM_ENABLED": {"0", "false", "False"},
        "REAL_PAYMENT_CALLS": {"disabled"},
        "UPI_APP_FACTORY_REAL_PAYMENT_CALLS": {"disabled"},
    }
    for name, allowed in expected.items():
        value = os.environ.get(name)
        if value not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise SystemExit(f"{name} must be one of [{allowed_text}] for the local Docker route.")


def main() -> int:
    _require_mock_only_environment()
    state_root = Path(os.environ.get("UPI_APP_FACTORY_STATE_ROOT", "/app/.var/operator_portal")).resolve()
    publication_root = Path(
        os.environ.get(
            "UPI_APP_FACTORY_PORTAL_PUBLICATION_ROOT",
            str(state_root / "publications"),
        )
    ).resolve()
    portfolio_state_root = state_root / "portfolio"
    runtime_state_root = state_root / "runtime"
    publication_root.mkdir(parents=True, exist_ok=True)
    portfolio_state_root.mkdir(parents=True, exist_ok=True)
    runtime_state_root.mkdir(parents=True, exist_ok=True)

    host = os.environ.get("UPI_APP_FACTORY_HOST", "0.0.0.0")
    if host not in {"0.0.0.0", "127.0.0.1", "localhost"}:
        raise SystemExit("Docker portal host must be container-local or loopback.")
    port = int(os.environ.get("UPI_APP_FACTORY_PORT", "8036"))

    import uvicorn

    uvicorn.run(
        create_web_ui_app(
            project_root=PROJECT_ROOT,
            publication_root=publication_root,
            portfolio_state_root=portfolio_state_root,
            runtime_state_root=runtime_state_root,
        ),
        host=host,
        port=port,
        log_level=os.environ.get("UPI_APP_FACTORY_LOG_LEVEL", "INFO").lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
