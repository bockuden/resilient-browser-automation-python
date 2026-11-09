"""Validated job and worker configuration models."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import SplitResult, urlsplit


class ConfigurationError(ValueError):
    """Raised when job or worker settings cannot be used safely."""


@dataclass(frozen=True, slots=True)
class TargetConfig:
    """Settings that belong to one target rather than to the worker."""

    name: str
    base_url: str = field(repr=False)
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ConfigurationError("target name must not be empty")
        _validate_http_url(self.base_url, "target base URL", allow_query=False)
        if (self.username is None) != (self.password is None):
            raise ConfigurationError("target username and password must be configured together")
        if self.username is not None and not isinstance(self.username, str):
            raise ConfigurationError("target credentials must be strings")
        if self.password is not None and not isinstance(self.password, str):
            raise ConfigurationError("target credentials must be strings")
        if self.username == "" or self.password == "":
            raise ConfigurationError("target credentials must not be empty")


@dataclass(frozen=True, slots=True)
class JobSpec:
    """Identity and target-specific input for one bounded collection job."""

    job_id: str
    target: TargetConfig
    target_url: str = field(repr=False)
    page_limit: int

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not self.job_id.strip():
            raise ConfigurationError("job_id must not be empty")
        if not isinstance(self.target, TargetConfig):
            raise ConfigurationError("job target must be a TargetConfig")
        target_parts = _validate_http_url(
            self.target.base_url, "target base URL", allow_query=False
        )
        job_parts = _validate_http_url(self.target_url, "job target URL", allow_query=True)
        if _origin(target_parts) != _origin(job_parts):
            raise ConfigurationError("job target URL must use the configured target origin")
        _require_positive_integer(self.page_limit, "page_limit")


@dataclass(frozen=True, slots=True)
class RetrySettings:
    """Bounded exponential retry settings; max_attempts includes the first try."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.5
    max_delay_seconds: float = 30.0
    multiplier: float = 2.0

    def __post_init__(self) -> None:
        _require_positive_integer(self.max_attempts, "retry max_attempts")
        initial = _require_positive_number(self.initial_delay_seconds, "retry initial delay")
        maximum = _require_positive_number(self.max_delay_seconds, "retry maximum delay")
        multiplier = _require_positive_number(self.multiplier, "retry multiplier")
        if initial > maximum:
            raise ConfigurationError("retry initial delay must not exceed its maximum delay")
        if multiplier < 1:
            raise ConfigurationError("retry multiplier must be at least 1")


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    """Worker-wide execution budgets, independent of target credentials/selectors."""

    operation_timeout_seconds: float = 30.0
    job_timeout_seconds: float = 300.0
    retry: RetrySettings = field(default_factory=RetrySettings)

    def __post_init__(self) -> None:
        operation_timeout = _require_positive_number(
            self.operation_timeout_seconds, "operation timeout"
        )
        job_timeout = _require_positive_number(self.job_timeout_seconds, "job timeout")
        if operation_timeout > job_timeout:
            raise ConfigurationError("operation timeout must not exceed the job timeout budget")
        if not isinstance(self.retry, RetrySettings):
            raise ConfigurationError("retry must be a RetrySettings instance")


def resolve_settings(
    *,
    defaults: Mapping[str, object],
    file_settings: Mapping[str, object],
    environment_settings: Mapping[str, object],
    command_line_settings: Mapping[str, object],
) -> dict[str, object]:
    """Merge normalized settings from lowest to highest precedence."""

    resolved = dict(defaults)
    resolved.update(file_settings)
    resolved.update(environment_settings)
    resolved.update(command_line_settings)
    return resolved


def format_configuration_diagnostics(job: JobSpec, worker: WorkerConfig) -> str:
    """Format a useful summary without including URLs or credential values."""

    return "\n".join(
        (
            f"job_id={job.job_id}",
            f"target={job.target.name}",
            f"page_limit={job.page_limit}",
            f"operation_timeout_seconds={worker.operation_timeout_seconds:g}",
            f"job_timeout_seconds={worker.job_timeout_seconds:g}",
            f"retry_max_attempts={worker.retry.max_attempts}",
            f"retry_initial_delay_seconds={worker.retry.initial_delay_seconds:g}",
            f"retry_max_delay_seconds={worker.retry.max_delay_seconds:g}",
        )
    )


def _validate_http_url(value: str, label: str, *, allow_query: bool) -> SplitResult:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(character.isspace() for character in value)
    ):
        raise ConfigurationError(f"{label} must be an absolute HTTP or HTTPS URL")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError(f"{label} is malformed") from error
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise ConfigurationError(f"{label} must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigurationError(f"{label} must not embed credentials")
    if parsed.fragment:
        raise ConfigurationError(f"{label} must not contain a fragment")
    if port == 0:
        raise ConfigurationError(f"{label} must use a port between 1 and 65535")
    if not allow_query and parsed.query:
        raise ConfigurationError(f"{label} must not contain a query string")
    return parsed


def _origin(parsed: SplitResult) -> tuple[str, str, int]:
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname
    if hostname is None:
        raise ConfigurationError("URL must include a hostname")
    port = parsed.port or (443 if scheme == "https" else 80)
    return scheme, hostname.lower(), port


def _require_positive_integer(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigurationError(f"{label} must be a positive integer")


def _require_positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{label} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ConfigurationError(f"{label} must be a positive finite number")
    return number
