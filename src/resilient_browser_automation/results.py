"""Typed job outcomes and stable process exit codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class JobOutcome(StrEnum):
    """Terminal state reported for one job."""

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"


class ExitCode(IntEnum):
    """Stable command exit codes for automation callers and shell scripts."""

    SUCCESS = 0
    FAILED = 1
    INCOMPLETE = 2
    CANCELLED = 130


@dataclass(frozen=True, slots=True)
class JobResult:
    """A job's terminal outcome and bounded progress summary."""

    job_id: str
    outcome: JobOutcome
    pages_completed: int = 0
    records_collected: int = 0
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id must not be empty")
        if not isinstance(self.outcome, JobOutcome):
            raise ValueError("outcome must be a JobOutcome")
        _require_nonnegative_integer(self.pages_completed, "pages_completed")
        _require_nonnegative_integer(self.records_collected, "records_collected")
        if self.error_code is not None and not self.error_code.strip():
            raise ValueError("error_code must be omitted or non-empty")

    @property
    def exit_code(self) -> ExitCode:
        """Return the documented stable process exit code for this outcome."""

        return {
            JobOutcome.COMPLETED: ExitCode.SUCCESS,
            JobOutcome.FAILED: ExitCode.FAILED,
            JobOutcome.INCOMPLETE: ExitCode.INCOMPLETE,
            JobOutcome.CANCELLED: ExitCode.CANCELLED,
        }[self.outcome]


def _require_nonnegative_integer(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
