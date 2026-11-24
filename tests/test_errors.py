"""Tests for the operational error categories and retry classification."""

from __future__ import annotations

import pytest

from resilient_browser_automation.errors import (
    AuthenticationError,
    AutomationError,
    ErrorCode,
    ExtractionContractError,
    JobDeadlineExceeded,
    PermanentTargetError,
    StorageError,
    TransientTargetError,
)


@pytest.mark.parametrize(
    ("error_type", "code", "retryable"),
    [
        (TransientTargetError, ErrorCode.TRANSIENT_TARGET, True),
        (PermanentTargetError, ErrorCode.PERMANENT_TARGET, False),
        (JobDeadlineExceeded, ErrorCode.JOB_DEADLINE_EXCEEDED, False),
        (AuthenticationError, ErrorCode.AUTHENTICATION, False),
        (ExtractionContractError, ErrorCode.EXTRACTION_CONTRACT, False),
        (StorageError, ErrorCode.STORAGE, False),
    ],
)
def test_operational_errors_have_distinct_codes_and_retry_policy(
    error_type: type[AutomationError], code: ErrorCode, retryable: bool
) -> None:
    error = error_type("safe diagnostic")

    assert isinstance(error, AutomationError)
    assert error.code is code
    assert error.retryable is retryable
    assert str(error) == "safe diagnostic"
