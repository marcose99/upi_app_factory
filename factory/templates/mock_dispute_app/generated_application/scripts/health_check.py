#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
import sys
from typing import Any


HOST = os.environ.get("UPI_DISPUTE_LOCAL_HOST", "127.0.0.1")
PORT = int(os.environ.get("UPI_DISPUTE_LOCAL_PORT", "8042"))
JSON_PATHS = ("/health", "/startup", "/live", "/ready")
TEXT_PATHS = ("/metrics",)
EXPECTED_STATUSES = {"ok", "passed", "available", "started", "live", "ready"}


def fetch(path: str) -> tuple[int, str, str]:
    connection = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        content_type = response.getheader("content-type", "")
        return response.status, content_type, body
    finally:
        connection.close()


def parse_json(path: str, body: str) -> dict[str, Any]:
    value = json.loads(body)
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} returned non-object JSON")
    return value


def main() -> int:
    failures: list[str] = []
    for path in JSON_PATHS:
        status, _content_type, body = fetch(path)
        if status != 200:
            failures.append(f"{path}: HTTP {status}: {body}")
            continue
        payload = parse_json(path, body)
        if payload.get("status") not in EXPECTED_STATUSES:
            failures.append(f"{path}: unexpected status {payload.get('status')!r}")
        if '"live_provider_calls_allowed": true' in json.dumps(payload, sort_keys=True):
            failures.append(f"{path}: live provider calls appear enabled")
    for path in TEXT_PATHS:
        status, content_type, body = fetch(path)
        if status != 200:
            failures.append(f"{path}: HTTP {status}: {body}")
        if "openmetrics-text" not in content_type:
            failures.append(f"{path}: unexpected content type {content_type!r}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"Local health checks passed for http://{HOST}:{PORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
