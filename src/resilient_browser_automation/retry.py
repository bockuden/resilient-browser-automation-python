"""Classified retry orchestration with server hints and a total job deadline."""

from __future__ import annotations

import asyncio
import math
import random
import time
from collections.abc import Awaitable, Callable
from datetime import UTC
from email.utils import parsedate_to_datetime
from typing import TypeVar

from resilient_browser_automation.config import RetrySettings
from resilient_browser_automation.errors import JobDeadlineExceeded, TransientTargetError

T = TypeVar("T")


class RetryPolicy:
    """Retry only transient target errors inside one monotonic time budget.

    Invalid ``Retry-After`` values fall back to jittered exponential backoff. A
    valid server delay is never shortened; when it cannot fit before the job
    deadline, the operation fails immediately instead of overrunning the budget.
    """

    def __init__(
        self,
        settings: RetrySettings,
        *,
        job_timeout_seconds: float,
        operation_timeout_seconds: float | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall_time: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        if not math.isfinite(job_timeout_seconds) or job_timeout_seconds <= 0:
            raise ValueError("job_timeout_seconds must be positive and finite")
        if operation_timeout_seconds is not None and (
            not math.isfinite(operation_timeout_seconds) or operation_timeout_seconds <= 0
        ):
            raise ValueError("operation_timeout_seconds must be positive and finite")
        self._settings = settings
        self._job_timeout_seconds = job_timeout_seconds
        self._operation_timeout_seconds = operation_timeout_seconds
        self._monotonic = monotonic
        self._wall_time = wall_time
        self._sleep = sleep
        self._random_value = random_value

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Execute an awaitable with classified retries and a total deadline."""

        deadline = self._monotonic() + self._job_timeout_seconds
        for attempt in range(1, self._settings.max_attempts + 1):
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise JobDeadlineExceeded("job deadline exceeded")
            attempt_timeout = remaining
            if self._operation_timeout_seconds is not None:
                attempt_timeout = min(attempt_timeout, self._operation_timeout_seconds)
            timeout_scope = asyncio.timeout(attempt_timeout)
            retry_error: TransientTargetError | None = None
            try:
                async with timeout_scope:
                    return await operation()
            except TimeoutError as error:
                if not timeout_scope.expired():
                    raise
                if attempt_timeout == remaining:
                    raise JobDeadlineExceeded(
                        "job deadline exceeded during an operation"
                    ) from error
            except TransientTargetError as error:
                retry_error = error
            if retry_error is None:
                retry_error = TransientTargetError("operation timed out")
            if attempt >= self._settings.max_attempts:
                raise retry_error
            delay = self._delay_before_retry(attempt, retry_error.retry_after)
            remaining = deadline - self._monotonic()
            if delay >= remaining:
                raise JobDeadlineExceeded(
                    "retry delay exceeds the remaining job deadline"
                ) from retry_error
            timeout_scope = asyncio.timeout(remaining)
            try:
                async with timeout_scope:
                    await self._sleep(delay)
            except TimeoutError as timeout_error:
                if timeout_scope.expired():
                    raise JobDeadlineExceeded(
                        "job deadline exceeded while waiting to retry"
                    ) from timeout_error
                raise
        raise AssertionError("retry loop exited without a result or exception")

    def _delay_before_retry(self, attempt: int, retry_after: str | None) -> float:
        server_delay = parse_retry_after(retry_after, now=self._wall_time())
        if server_delay is not None:
            return server_delay
        ceiling = min(
            self._settings.max_delay_seconds,
            self._settings.initial_delay_seconds * self._settings.multiplier ** (attempt - 1),
        )
        random_value = min(1.0, max(0.0, self._random_value()))
        return ceiling * random_value


def parse_retry_after(value: str | None, *, now: float) -> float | None:
    """Parse delta-seconds or an HTTP-date into a nonnegative wait in seconds.

    Malformed values are ignored so the policy can use its configured backoff.
    An excessively large but syntactically valid delta remains infinite and is
    rejected by the job deadline check.
    """

    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.isascii() and candidate.isdecimal():
        try:
            return float(int(candidate))
        except OverflowError:
            return float("inf")
    try:
        retry_at = parsedate_to_datetime(candidate)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    if retry_at is None:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, retry_at.timestamp() - now)
