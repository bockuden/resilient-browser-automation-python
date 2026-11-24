"""Small error taxonomy for failures reported by the automation worker."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable machine-readable categories attached to job failures."""

    TRANSIENT_TARGET = "transient_target"
    PERMANENT_TARGET = "permanent_target"
    JOB_DEADLINE_EXCEEDED = "job_deadline_exceeded"
    AUTHENTICATION = "authentication"
    EXTRACTION_CONTRACT = "extraction_contract"
    STORAGE = "storage"


class AutomationError(Exception):
    """Base for expected operational failures with an explicit retry policy."""

    code: ErrorCode
    retryable: bool

    def __init__(self, message: str) -> None:
        super().__init__(message)


class TransientTargetError(AutomationError):
    """The target returned a temporary failure that may succeed on retry."""

    code = ErrorCode.TRANSIENT_TARGET
    retryable = True

    def __init__(self, message: str, *, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class PermanentTargetError(AutomationError):
    """The target returned a response that should not be repeated."""

    code = ErrorCode.PERMANENT_TARGET
    retryable = False


class JobDeadlineExceeded(AutomationError):
    """The total execution budget expired before a safe retry could complete."""

    code = ErrorCode.JOB_DEADLINE_EXCEEDED
    retryable = False


class AuthenticationError(AutomationError):
    """Authentication failed or the configured session cannot be restored."""

    code = ErrorCode.AUTHENTICATION
    retryable = False


class ExtractionContractError(AutomationError):
    """The page or response violated the expected extraction contract."""

    code = ErrorCode.EXTRACTION_CONTRACT
    retryable = False


class StorageError(AutomationError):
    """Persisted state could not be read, written, or committed safely."""

    code = ErrorCode.STORAGE
    retryable = False
