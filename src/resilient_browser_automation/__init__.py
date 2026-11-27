"""Reliable browser automation tools."""

from resilient_browser_automation.authentication import BrowserAuthenticator
from resilient_browser_automation.browser import BrowserJob, BrowserManager
from resilient_browser_automation.catalog import (
    CatalogAdapter,
    CatalogEndReason,
    CatalogRecord,
    CatalogResult,
    CatalogSelectors,
)
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
    JobDeadlineExceeded,
    PermanentTargetError,
    StorageError,
    TransientTargetError,
)
from resilient_browser_automation.results import ExitCode, JobOutcome, JobResult
from resilient_browser_automation.retry import RetryPolicy, parse_retry_after
from resilient_browser_automation.storage import JobState, SQLiteStore, StoredJob

__version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "AutomationError",
    "BrowserAuthenticator",
    "BrowserJob",
    "BrowserManager",
    "CatalogAdapter",
    "CatalogEndReason",
    "CatalogRecord",
    "CatalogResult",
    "CatalogSelectors",
    "ConfigurationError",
    "ErrorCode",
    "ExitCode",
    "ExtractionContractError",
    "JobOutcome",
    "JobDeadlineExceeded",
    "JobResult",
    "JobSpec",
    "JobState",
    "RetrySettings",
    "RetryPolicy",
    "PermanentTargetError",
    "StorageError",
    "SQLiteStore",
    "StoredJob",
    "TargetConfig",
    "TransientTargetError",
    "WorkerConfig",
    "format_configuration_diagnostics",
    "parse_retry_after",
    "resolve_settings",
]
