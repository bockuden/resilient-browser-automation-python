"""Validation tests for jobs, target configuration, and execution budgets."""

from __future__ import annotations

import pytest

from resilient_browser_automation.config import (
    ConfigurationError,
    JobSpec,
    RetrySettings,
    TargetConfig,
    WorkerConfig,
)


def _job(*, target_url: str = "https://catalog.example/items", page_limit: int = 10) -> JobSpec:
    target = TargetConfig(name="catalog", base_url="https://catalog.example")
    return JobSpec(
        job_id="job-001",
        target=target,
        target_url=target_url,
        page_limit=page_limit,
    )


@pytest.mark.parametrize(
    "url",
    [
        "",
        "catalog.example/items",
        "ftp://catalog.example/items",
        "https:///items",
        "https://user:secret@catalog.example/items",
        "https://catalog.example/items#fragment",
    ],
)
def test_job_rejects_invalid_target_urls(url: str) -> None:
    with pytest.raises(ConfigurationError):
        _job(target_url=url)


def test_job_rejects_target_url_on_an_unconfigured_origin() -> None:
    with pytest.raises(ConfigurationError, match="configured target origin"):
        _job(target_url="https://other.example/items")


@pytest.mark.parametrize("page_limit", [0, -1, True])
def test_job_rejects_nonpositive_page_limits(page_limit: int) -> None:
    with pytest.raises(ConfigurationError, match="page_limit must be a positive integer"):
        _job(page_limit=page_limit)


@pytest.mark.parametrize(
    ("operation_timeout", "job_timeout"),
    [
        (0.0, 300.0),
        (float("inf"), 300.0),
        (30.0, -1.0),
        (10.0, 5.0),
    ],
)
def test_worker_rejects_invalid_or_incompatible_timeouts(
    operation_timeout: float, job_timeout: float
) -> None:
    with pytest.raises(ConfigurationError):
        WorkerConfig(
            operation_timeout_seconds=operation_timeout,
            job_timeout_seconds=job_timeout,
        )


@pytest.mark.parametrize(
    ("attempts", "initial", "maximum", "multiplier"),
    [
        (0, 0.5, 30.0, 2.0),
        (3, 0.0, 30.0, 2.0),
        (3, 5.0, 2.0, 2.0),
        (3, 0.5, 30.0, 0.5),
    ],
)
def test_retry_settings_reject_invalid_budgets(
    attempts: int, initial: float, maximum: float, multiplier: float
) -> None:
    with pytest.raises(ConfigurationError):
        RetrySettings(
            max_attempts=attempts,
            initial_delay_seconds=initial,
            max_delay_seconds=maximum,
            multiplier=multiplier,
        )


def test_target_credentials_must_be_configured_as_a_pair() -> None:
    with pytest.raises(ConfigurationError, match="configured together"):
        TargetConfig(name="catalog", base_url="https://catalog.example", username="account")
