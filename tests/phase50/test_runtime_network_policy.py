from __future__ import annotations

import pytest

from factory.operator_portal.runtime_contracts import RuntimeContractError
from factory.operator_portal.runtime_network_policy import normalize_runtime_url


def test_network_policy_is_owned_port_bound() -> None:
    with pytest.raises(RuntimeContractError):
        normalize_runtime_url(
            base_url="http://127.0.0.1:18043",
            method="GET",
            endpoint="/health",
            owned_port=18042,
        )
