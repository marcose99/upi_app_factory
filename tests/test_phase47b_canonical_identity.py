from __future__ import annotations

from pathlib import Path
import subprocess

from tools.identity_compat import (
    CANONICAL_ENV_PREFIX,
    CANONICAL_PRODUCT_NAME,
    CANONICAL_REPOSITORY_NAME,
    legacy_repository_name,
    promote_legacy_environment_aliases,
)


def test_canonical_identity_constants() -> None:
    assert CANONICAL_REPOSITORY_NAME == "upi_app_factory"
    assert CANONICAL_PRODUCT_NAME == "UPI App Factory"
    assert CANONICAL_ENV_PREFIX == "UPI_APP_FACTORY_"


def test_legacy_environment_alias_is_promoted_without_overwrite() -> None:
    legacy_prefix = "UPI_DISPUTE_RESOLUTION" + "_FACTORY_"
    environ = {
        legacy_prefix + "MODE": "legacy",
        "UPI_APP_FACTORY_EXISTING": "canonical",
        legacy_prefix + "EXISTING": "legacy",
    }
    promoted = promote_legacy_environment_aliases(environ)
    assert environ["UPI_APP_FACTORY_MODE"] == "legacy"
    assert environ["UPI_APP_FACTORY_EXISTING"] == "canonical"
    assert promoted == {"UPI_APP_FACTORY_MODE": legacy_prefix + "MODE"}


def test_legacy_repository_name_is_compatibility_only() -> None:
    assert legacy_repository_name() == "upi_dispute_resolution" + "_factory"


def test_generated_application_identity_remains_present() -> None:
    root = Path(__file__).resolve().parents[1]
    generated = root / "workspace/factory_generated/upi_dispute_resolution"
    assert generated.exists()


def test_no_forbidden_project_label_in_tracked_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = "Factory" + "FromNothing"
    raw = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    ).stdout
    violations: list[str] = []
    for item in raw.split(b"\x00"):
        if not item:
            continue
        relative = item.decode("utf-8", errors="surrogateescape")
        path = root / relative
        if forbidden in relative:
            violations.append(relative)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if forbidden in text:
            violations.append(relative)
    assert violations == []
