#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
import sys
from typing import Any


HOST = os.environ.get("UPI_DISPUTE_LOCAL_HOST", "127.0.0.1")
PORT = int(os.environ.get("UPI_DISPUTE_LOCAL_PORT", "8042"))
REQUIRED_PATHS = ("/health", "/runtime/health", "/runtime/metrics")


def fetch_json(path: str) -> dict[str, Any]:
    connection = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
    finally:
        connection.close()
    if response.status != 200:
        raise RuntimeError(f"{path} returned HTTP {response.status}: {body}")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} returned non-object JSON")
    return value


def main() -> int:
    failures: list[str] = []
    for path in REQUIRED_PATHS:
        try:
            payload = fetch_json(path)
        except Exception as exc:  # pragma: no cover - command line reporting
            failures.append(f"{path}: {exc}")
            continue
        if payload.get("status") not in {"ok", "passed", "available"}:
            failures.append(f"{path}: unexpected status {payload.get('status')!r}")
        serialized = json.dumps(payload, sort_keys=True)
        if "certification_ready_not_certified" not in serialized and path != "/runtime/metrics":
            failures.append(f"{path}: certification boundary not reported")
        if '"live_provider_calls_allowed": true' in serialized:
            failures.append(f"{path}: live provider calls appear enabled")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"Local health checks passed for http://{HOST}:{PORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
