from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator


@contextmanager
def local_span(name: str, correlation_id: str) -> Iterator[dict[str, str]]:
    yield {"span": name, "correlation_id": correlation_id}
