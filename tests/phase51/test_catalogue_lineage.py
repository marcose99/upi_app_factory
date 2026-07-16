from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from factory.application_engineering.portfolio import PortfolioError, VersionState
from tests.phase51.conftest import PortfolioFixture, mock_app, registration


def test_catalogue_registration_supersedes_prior_active_version(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, _, _ = portfolio
    first = catalogue.register(
        registration(
            app_id="catalogue_app",
            version_id="v1",
            app_root=mock_app(tmp_path, "catalogue_v1", "v1"),
        )
    )
    second = catalogue.register(
        registration(
            app_id="catalogue_app",
            version_id="v2",
            app_root=mock_app(tmp_path, "catalogue_v2", "v2"),
        )
    )

    assert first.state == VersionState.ACTIVE
    assert second.state == VersionState.ACTIVE
    assert catalogue.get(app_id="catalogue_app", version_id="v1").state == VersionState.SUPERSEDED
    assert [item.version_key for item in catalogue.list_versions()] == [
        "catalogue_app:v1",
        "catalogue_app:v2",
    ]


def test_catalogue_rejects_duplicate_versions_and_detects_digest_tampering(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    store, catalogue, _, _ = portfolio
    request = registration(app_id="digest_app", app_root=mock_app(tmp_path, "digest_app", "digest"))
    catalogue.register(request)

    with pytest.raises(PortfolioError, match="already registered"):
        catalogue.register(request)

    payload = store.catalogue_path.read_text(encoding="utf-8")
    store.catalogue_path.write_text(
        payload.replace("digest_app", "forged_app", 1),
        encoding="utf-8",
    )
    with pytest.raises(PortfolioError, match="tampering"):
        catalogue.catalogue()


def test_catalogue_blocks_ungoverned_identity_and_entrypoint_values(
    tmp_path: Path,
    portfolio: PortfolioFixture,
) -> None:
    _, catalogue, _, _ = portfolio
    app_root = mock_app(tmp_path, "identity_app", "identity")
    with pytest.raises(PortfolioError, match="application id"):
        catalogue.register(registration(app_id="Bad-App", app_root=app_root))
    with pytest.raises(PortfolioError, match="module:app"):
        request = registration(app_id="entrypoint_app", app_root=app_root)
        catalogue.register(replace(request, entrypoint="../main.py"))
