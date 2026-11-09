"""Small error taxonomy for failures reported by the automation worker."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable machine-readable categories attached to job failures."""

    TRANSIENT_TARGET = "transient_target"
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
