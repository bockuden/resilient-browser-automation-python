"""Deterministic tests for retry timing, Retry-After parsing, and job deadlines."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import format_datetime

import pytest

from resilient_browser_automation.config import RetrySettings
from resilient_browser_automation.errors import (
    JobDeadlineExceeded,
    PermanentTargetError,
    TransientTargetError,
)
from resilient_browser_automation.retry import RetryPolicy, parse_retry_after


@pytest.mark.parametrize(
    ("header", "now", "expected"),
    [
        ("2", 1_700_000_000.0, 2.0),
        (" 7 ", 1_700_000_000.0, 7.0),
        ("invalid", 1_700_000_000.0, None),
        ("-1", 1_700_000_000.0, None),
        ("", 1_700_000_000.0, None),
        (None, 1_700_000_000.0, None),
    ],
)
def test_parse_retry_after_delta_seconds_and_invalid_values(
    header: str | None, now: float, expected: float | None
) -> None:
    assert parse_retry_after(header, now=now) == expected


def test_parse_retry_after_http_date_uses_explicit_wall_clock() -> None:
    now = datetime(2026, 11, 24, 12, 0, tzinfo=UTC).timestamp()
    header = format_datetime(datetime(2026, 11, 24, 12, 0, 5, tzinfo=UTC), usegmt=True)

    assert parse_retry_after(header, now=now) == 5.0
    assert parse_retry_after("Sun, 06 Nov 1994 08:49:37 GMT", now=now) == 0.0


def test_retry_policy_uses_injected_clock_sleep_and_randomness() -> None:
    now = [100.0]
    waits: list[float] = []
    attempts = 0

    async def sleep(delay: float) -> None:
        waits.append(delay)
        now[0] += delay

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TransientTargetError("temporary")
        return "done"

    policy = RetryPolicy(
        RetrySettings(max_attempts=3, initial_delay_seconds=1, max_delay_seconds=10),
        job_timeout_seconds=5,
        monotonic=lambda: now[0],
        wall_time=lambda: 1_700_000_000.0,
        sleep=sleep,
        random_value=lambda: 0.5,
    )

    assert asyncio.run(policy.run(operation)) == "done"
    assert attempts == 3
    assert waits == [0.5, 1.0]


@pytest.mark.parametrize(
    ("header", "expected_wait"),
    [
        ("2", 2.0),
        ("Tue, 24 Nov 2026 12:00:03 GMT", 3.0),
        ("not-a-date", 0.5),
    ],
)
def test_retry_policy_honors_server_delay_and_falls_back_for_invalid_header(
    header: str, expected_wait: float
) -> None:
    now = [datetime(2026, 11, 24, 12, 0, tzinfo=UTC).timestamp()]
    waits: list[float] = []
    attempts = 0

    async def sleep(delay: float) -> None:
        waits.append(delay)
        now[0] += delay

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TransientTargetError("temporary", retry_after=header)
        return "done"

    policy = RetryPolicy(
        RetrySettings(max_attempts=2, initial_delay_seconds=1),
        job_timeout_seconds=10,
        monotonic=lambda: now[0],
        wall_time=lambda: now[0],
        sleep=sleep,
        random_value=lambda: 0.5,
    )

    assert asyncio.run(policy.run(operation)) == "done"
    assert waits == [expected_wait]


def test_retry_after_that_exceeds_remaining_budget_ends_job_without_sleeping() -> None:
    waits: list[float] = []
    attempts = 0

    async def sleep(delay: float) -> None:
        waits.append(delay)

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise TransientTargetError("rate limited", retry_after="6")

    policy = RetryPolicy(
        RetrySettings(max_attempts=3),
        job_timeout_seconds=5,
        monotonic=lambda: 100.0,
        wall_time=lambda: 1_700_000_000.0,
        sleep=sleep,
    )

    with pytest.raises(JobDeadlineExceeded, match="retry delay"):
        asyncio.run(policy.run(operation))
    assert attempts == 1
    assert waits == []


@pytest.mark.parametrize("error", [PermanentTargetError("not found"), asyncio.CancelledError()])
def test_permanent_errors_and_cancellation_are_never_retried(
    error: BaseException,
) -> None:
    attempts = 0

    async def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise error

    policy = RetryPolicy(RetrySettings(), job_timeout_seconds=5)

    with pytest.raises(type(error)):
        asyncio.run(policy.run(operation))
    assert attempts == 1
