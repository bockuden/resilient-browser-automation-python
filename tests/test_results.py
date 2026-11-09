"""Outcome-to-exit-code contract tests."""

from __future__ import annotations

import pytest

from resilient_browser_automation.errors import ErrorCode
from resilient_browser_automation.results import ExitCode, JobOutcome, JobResult


@pytest.mark.parametrize(
    ("outcome", "exit_code"),
    [
        (JobOutcome.COMPLETED, ExitCode.SUCCESS),
        (JobOutcome.FAILED, ExitCode.FAILED),
        (JobOutcome.INCOMPLETE, ExitCode.INCOMPLETE),
        (JobOutcome.CANCELLED, ExitCode.CANCELLED),
    ],
)
def test_every_terminal_outcome_has_a_stable_exit_code(
    outcome: JobOutcome, exit_code: ExitCode
) -> None:
    result = JobResult(
        job_id="job-001",
        outcome=outcome,
        pages_completed=2,
        records_collected=7,
    )

    assert result.exit_code is exit_code


@pytest.mark.parametrize("count", [-1, True])
def test_result_rejects_invalid_progress_counts(count: int) -> None:
    with pytest.raises(ValueError, match="nonnegative integer"):
        JobResult(job_id="job-001", outcome=JobOutcome.INCOMPLETE, pages_completed=count)


def test_result_rejects_blank_job_id_and_untyped_error_code() -> None:
    with pytest.raises(ValueError, match="job_id must not be empty"):
        JobResult(job_id=" ", outcome=JobOutcome.FAILED)
    with pytest.raises(ValueError, match="error_code must be an ErrorCode"):
        JobResult(job_id="job-001", outcome=JobOutcome.FAILED, error_code="storage")  # type: ignore[arg-type]


def test_job_result_carries_a_typed_error_category() -> None:
    result = JobResult(
        job_id="job-001",
        outcome=JobOutcome.FAILED,
        error_code=ErrorCode.STORAGE,
    )

    assert result.error_code is ErrorCode.STORAGE
