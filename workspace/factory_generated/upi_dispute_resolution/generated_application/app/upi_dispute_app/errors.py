from __future__ import annotations

from enum import Enum


class AppErrorCode(str, Enum):
    VALIDATION_BOUNDARY = "validation_boundary"
    DUPLICATE_CLIENT_REQUEST = "duplicate_client_request"
    DISPUTE_NOT_FOUND = "dispute_not_found"
    PAYLOAD_CONFLICT = "payload_conflict"
    MOCK_ECOSYSTEM_FAILURE = "mock_ecosystem_failure"


class ApplicationError(Exception):
    def __init__(
        self,
        code: AppErrorCode,
        message: str,
        *,
        http_status: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def as_error_payload(self, *, path: str, boundary_notice: str) -> dict[str, object]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "path": path,
                "boundary_notice": boundary_notice,
            }
        }
