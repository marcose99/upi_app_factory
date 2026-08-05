from __future__ import annotations

from typing import Any, Mapping


class Response:
    status_code: int
    text: str
    content: bytes
    headers: Mapping[str, str]

    def json(self) -> Any: ...


class ASGITransport:
    def __init__(
        self,
        app: object,
        *,
        raise_app_exceptions: bool = ...,
        root_path: str = ...,
        client: tuple[str, int] | None = ...,
    ) -> None: ...


class AsyncClient:
    def __init__(
        self,
        *,
        transport: object | None = ...,
        base_url: str = ...,
        headers: Mapping[str, str] | None = ...,
    ) -> None: ...

    async def __aenter__(self) -> AsyncClient: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    async def request(
        self,
        method: str,
        url: str,
        *,
        json: Any = ...,
        headers: Mapping[str, str] | None = ...,
    ) -> Response: ...
    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = ...,
    ) -> Response: ...
    async def post(
        self,
        url: str,
        *,
        json: Any = ...,
        headers: Mapping[str, str] | None = ...,
    ) -> Response: ...
