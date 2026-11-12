"""Reliable browser automation tools."""

from resilient_browser_automation.browser import BrowserJob, BrowserManager
from resilient_browser_automation.config import (
    ConfigurationError,
    JobSpec,
    RetrySettings,
    TargetConfig,
    WorkerConfig,
    format_configuration_diagnostics,
    resolve_settings,
)
from resilient_browser_automation.errors import (
    AuthenticationError,
    AutomationError,
    ErrorCode,
    ExtractionContractError,
    StorageError,
    TransientTargetError,
)
from resilient_browser_automation.results import ExitCode, JobOutcome, JobResult

__version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "AutomationError",
    "BrowserJob",
    "BrowserManager",
    "ConfigurationError",
    "ErrorCode",
    "ExitCode",
    "ExtractionContractError",
    "JobOutcome",
    "JobResult",
    "JobSpec",
    "RetrySettings",
    "StorageError",
    "TargetConfig",
    "TransientTargetError",
    "WorkerConfig",
    "format_configuration_diagnostics",
    "resolve_settings",
]
