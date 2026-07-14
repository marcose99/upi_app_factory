from __future__ import annotations

import os
from collections.abc import MutableMapping


CANONICAL_REPOSITORY_NAME = "upi_app_factory"
CANONICAL_PRODUCT_NAME = "UPI App Factory"
CANONICAL_ENV_PREFIX = "UPI_APP_FACTORY_"

_LEGACY_REPOSITORY_NAME = "upi_dispute_resolution" + "_factory"
_LEGACY_ENV_PREFIX = "UPI_DISPUTE_RESOLUTION" + "_FACTORY_"


def legacy_repository_name() -> str:
    return _LEGACY_REPOSITORY_NAME


def promote_legacy_environment_aliases(
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    target = os.environ if environ is None else environ
    promoted: dict[str, str] = {}
    for key, value in list(target.items()):
        if not key.startswith(_LEGACY_ENV_PREFIX):
            continue
        suffix = key[len(_LEGACY_ENV_PREFIX) :]
        canonical_key = CANONICAL_ENV_PREFIX + suffix
        if canonical_key in target:
            continue
        target[canonical_key] = value
        promoted[canonical_key] = key
    return promoted
