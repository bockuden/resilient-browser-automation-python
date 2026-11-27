"""Command-line entry point for running a single catalog job."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Never
from urllib.parse import urlsplit
from uuid import uuid4

from resilient_browser_automation import __version__
from resilient_browser_automation.authentication import BrowserAuthenticator
from resilient_browser_automation.browser import BrowserManager
from resilient_browser_automation.catalog import CatalogAdapter, CatalogRecord, CatalogSelectors
from resilient_browser_automation.config import (
    ConfigurationError,
    JobSpec,
    RetrySettings,
    TargetConfig,
    WorkerConfig,
)
from resilient_browser_automation.errors import PermanentTargetError, TransientTargetError
from resilient_browser_automation.results import JobOutcome
from resilient_browser_automation.retry import RetryPolicy
from resilient_browser_automation.storage import JobState, SQLiteStore

_INVALID_INPUT = 64
_EXECUTION_FAILURE = 1
_INCOMPLETE = 2
_CANCELLED = 130


class _InvalidInputError(Exception):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        self.print_usage(sys.stderr)
        raise _InvalidInputError(message)


@dataclass(frozen=True, slots=True)
class _RunOptions:
    job: JobSpec
    database: Path
    selectors: CatalogSelectors
    output_format: str
    worker: WorkerConfig
    max_login_attempts: int


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive finite number") from error
    if parsed <= 0 or not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""

    parser = _ArgumentParser(
        prog="resilient-browser-automation",
        description="Run a browser-based catalog collection job.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_ArgumentParser)
    run = commands.add_parser("run", help="collect one catalog into SQLite")
    run.add_argument("--url", required=True, help="absolute catalog URL")
    run.add_argument("--job-id", help="stable job identity (generated when omitted)")
    run.add_argument("--target-name", default="catalog", help="short target label")
    run.add_argument("--database", type=Path, default=Path("automation.sqlite3"))
    run.add_argument("--page-limit", type=_positive_integer, default=20)
    run.add_argument("--job-timeout-seconds", type=_positive_float, default=300.0)
    run.add_argument("--operation-timeout-seconds", type=_positive_float, default=30.0)
    run.add_argument("--retry-max-attempts", type=_positive_integer, default=3)
    run.add_argument("--retry-initial-delay-seconds", type=_positive_float, default=0.5)
    run.add_argument("--retry-max-delay-seconds", type=_positive_float, default=30.0)
    run.add_argument("--retry-multiplier", type=_positive_float, default=2.0)
    run.add_argument("--login-max-attempts", type=_positive_integer, default=2)
    run.add_argument("--output-format", choices=("human", "json"), default="human")
    run.add_argument("--catalog-testid", default="catalog")
    run.add_argument("--item-testid", default="catalog-item")
    run.add_argument("--item-id-attribute", default="data-item-id")
    run.add_argument("--name-testid", default="item-name")
    run.add_argument("--price-testid", default="item-price")
    run.add_argument("--next-page-testid", default="next-page")
    return parser


def _options_from_args(args: argparse.Namespace) -> _RunOptions:
    try:
        parts = urlsplit(args.url)
    except ValueError as error:
        raise ConfigurationError("--url is malformed") from error
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ConfigurationError("--url must be an absolute HTTP or HTTPS URL")
    try:
        origin = f"{parts.scheme}://{parts.netloc}"
    except ValueError as error:
        raise ConfigurationError("--url is malformed") from error
    target = TargetConfig(
        name=args.target_name,
        base_url=origin,
        username=os.environ.get("RBA_TARGET_USERNAME"),
        password=os.environ.get("RBA_TARGET_PASSWORD"),
    )
    job = JobSpec(
        job_id=args.job_id or str(uuid4()),
        target=target,
        target_url=args.url,
        page_limit=args.page_limit,
    )
    selectors = CatalogSelectors(
        catalog=args.catalog_testid,
        item=args.item_testid,
        item_id_attribute=args.item_id_attribute,
        item_name=args.name_testid,
        item_price=args.price_testid,
        next_page=args.next_page_testid,
    )
    worker = WorkerConfig(
        job_timeout_seconds=args.job_timeout_seconds,
        operation_timeout_seconds=args.operation_timeout_seconds,
        retry=RetrySettings(
            max_attempts=args.retry_max_attempts,
            initial_delay_seconds=args.retry_initial_delay_seconds,
            max_delay_seconds=args.retry_max_delay_seconds,
            multiplier=args.retry_multiplier,
        ),
    )
    return _RunOptions(
        job,
        args.database,
        selectors,
        args.output_format,
        worker,
        args.login_max_attempts,
    )


def _summary(
    job: JobSpec,
    database: Path,
    *,
    outcome: JobOutcome,
    checkpoint_page: int = 0,
    item_count: int = 0,
    end_reason: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "target": job.target.name,
        "outcome": outcome.value,
        "checkpoint_page": checkpoint_page,
        "pages_committed": checkpoint_page,
        "item_count": item_count,
        "end_reason": end_reason,
        "database": str(database),
        "error": error,
    }


async def _execute(options: _RunOptions) -> tuple[int, dict[str, Any], str | None]:
    job = options.job
    store = SQLiteStore(options.database)
    created = False
    outcome = JobOutcome.FAILED
    end_reason: str | None = None
    error_message: str | None = None
    exit_code = _EXECUTION_FAILURE

    try:
        await store.initialize()
        await store.create_job(job)
        created = True
        await store.set_job_state(job.job_id, JobState.RUNNING)

        async def collect_browser_job() -> str:
            async with BrowserManager() as browser:
                async with browser.open_job() as browser_job:
                    response = await browser_job.page.goto(job.target_url)
                    authenticator = BrowserAuthenticator(
                        job.target.username,
                        job.target.password,
                        max_attempts=options.max_login_attempts,
                        timeout_ms=int(options.worker.operation_timeout_seconds * 1000),
                    )
                    if response is None:
                        raise TransientTargetError("catalog navigation returned no response")
                    if response.status == 429 or 500 <= response.status <= 599:
                        retry_after = await response.header_value("Retry-After")
                        raise TransientTargetError(
                            f"catalog navigation failed: HTTP {response.status}",
                            retry_after=retry_after,
                        )
                    if response.status >= 400:
                        raise PermanentTargetError(
                            f"catalog navigation failed: HTTP {response.status}"
                        )
                    await authenticator.authenticate_if_required(browser_job.page)

                    async def persist_page(
                        page_number: int, records: tuple[CatalogRecord, ...]
                    ) -> None:
                        await store.save_page(job.job_id, page_number, records)

                    result = await CatalogAdapter(
                        browser_job.page,
                        selectors=options.selectors,
                        on_authentication_required=authenticator.authenticate_if_required,
                    ).extract(page_limit=job.page_limit, on_page=persist_page)
                    return result.end_reason.value
            raise AssertionError("browser job exited without a collection result")

        end_reason = await RetryPolicy(
            options.worker.retry,
            job_timeout_seconds=options.worker.job_timeout_seconds,
            operation_timeout_seconds=options.worker.operation_timeout_seconds,
        ).run(collect_browser_job)
        if end_reason == "page_limit":
            outcome = JobOutcome.INCOMPLETE
            exit_code = _INCOMPLETE
            await store.set_job_state(job.job_id, JobState.INCOMPLETE)
        else:
            outcome = JobOutcome.COMPLETED
            exit_code = 0
            await store.set_job_state(job.job_id, JobState.COMPLETED)
    except asyncio.CancelledError:
        outcome = JobOutcome.CANCELLED
        exit_code = _CANCELLED
        error_message = "job cancelled"
        if created:
            await asyncio.shield(store.set_job_state(job.job_id, JobState.CANCELLED))
    except Exception as error:
        outcome = JobOutcome.FAILED
        exit_code = _EXECUTION_FAILURE
        error_message = str(error) or type(error).__name__
        if created:
            try:
                await store.set_job_state(job.job_id, JobState.FAILED)
            except Exception as state_error:
                error_message = f"{error_message}; could not persist failed state: {state_error}"

    checkpoint_page = 0
    item_count = 0
    if created:
        try:
            checkpoint_page = await store.get_checkpoint(job.job_id)
            item_count = len(await store.get_records(job.job_id))
        except Exception as error:
            error_message = f"{error_message}; could not read committed progress: {error}"
            outcome = JobOutcome.FAILED
            exit_code = _EXECUTION_FAILURE

    return (
        exit_code,
        _summary(
            job,
            options.database,
            outcome=outcome,
            checkpoint_page=checkpoint_page,
            item_count=item_count,
            end_reason=end_reason,
            error=error_message,
        ),
        error_message,
    )


def _write_output(
    output_format: str,
    summary: dict[str, Any],
    diagnostic: str | None,
) -> None:
    if diagnostic:
        print(f"error: {diagnostic}", file=sys.stderr)
    if output_format == "json":
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        return
    print(f"Job: {summary['job_id']} ({summary['target']})")
    print(f"Outcome: {summary['outcome']}")
    print(f"Committed pages: {summary['pages_committed']}")
    print(f"Persisted items: {summary['item_count']}")
    print(f"Database: {summary['database']}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run one catalog job and return a stable command exit status."""

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        options = _options_from_args(args)
    except _InvalidInputError as error:
        print(f"error: {error}", file=sys.stderr)
        return _INVALID_INPUT
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return _INVALID_INPUT

    try:
        exit_code, summary, diagnostic = asyncio.run(_execute(options))
    except KeyboardInterrupt:
        summary = _summary(options.job, options.database, outcome=JobOutcome.CANCELLED)
        diagnostic = "job cancelled"
        exit_code = _CANCELLED
    _write_output(options.output_format, summary, diagnostic)
    return exit_code
