"""End-to-end CLI checks against the pinned browser Test Stand."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from decimal import Decimal
from urllib.request import urlopen

import pytest

from resilient_browser_automation.storage import JobState, SQLiteStore
from resilient_browser_automation.test_runs import TestRun as RunContext

pytestmark = pytest.mark.integration

_CLI_TIMEOUT_SECONDS = 60


def _run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "resilient_browser_automation", *arguments]
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=_CLI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(
            f"CLI exceeded {_CLI_TIMEOUT_SECONDS}s timeout.\n"
            f"Command: {command!r}\n"
            f"stdout: {_output_text(error.stdout)}\n"
            f"stderr: {_output_text(error.stderr)}"
        )


def _output_text(output: str | bytes | None) -> str:
    if output is None:
        return "<empty>"
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output or "<empty>"


def _failure_details(command: list[str], result: subprocess.CompletedProcess[str]) -> str:
    return (
        f"Command: {command!r}\n"
        f"Exit status: {result.returncode}\n"
        f"stdout:\n{result.stdout or '<empty>'}\n"
        f"stderr:\n{result.stderr or '<empty>'}"
    )


def test_cli_runs_catalog_and_persists_records(test_run: RunContext) -> None:
    database = test_run.storage_dir / "cli.sqlite3"
    job_id = "cli-success"
    scenario_url = test_run.scenario_url("success", total_pages=2)
    arguments = [
        "run",
        "--url",
        scenario_url,
        "--job-id",
        job_id,
        "--target-name",
        "test-catalog",
        "--database",
        str(database),
        "--page-limit",
        "3",
        "--output-format",
        "json",
    ]

    result = _run_cli(arguments)
    command = [sys.executable, "-m", "resilient_browser_automation", *arguments]
    details = _failure_details(command, result)
    assert result.returncode == 0, details
    assert result.stderr == "", details
    try:
        summary = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        pytest.fail(f"CLI did not produce valid JSON.\n{details}\n{error}")

    assert summary["job_id"] == job_id, details
    assert summary["outcome"] == "completed", details
    assert summary["checkpoint_page"] == 2, details
    assert summary["pages_committed"] == 2, details
    assert summary["item_count"] == 10, details
    assert summary["end_reason"] == "natural_end", details

    async def assert_persisted_results() -> None:
        store = SQLiteStore(database)
        persisted_job = await store.get_job(job_id)
        records = await store.get_records(job_id)
        assert persisted_job is not None
        assert persisted_job.state is JobState.COMPLETED
        assert persisted_job.checkpoint_page == 2
        assert tuple(record.item_id for record in records) == tuple(
            f"item-{number:03}" for number in range(1, 11)
        )
        assert records[0].name == "Catalog item 1"
        assert records[0].price == Decimal("1.99")
        assert records[0].source_url == scenario_url

    asyncio.run(assert_persisted_results())


def test_cli_rejects_invalid_page_limit() -> None:
    arguments = ["run", "--url", "http://127.0.0.1:1/catalog", "--page-limit", "0"]
    result = _run_cli(arguments)
    command = [sys.executable, "-m", "resilient_browser_automation", *arguments]
    details = _failure_details(command, result)

    assert result.returncode == 64, details
    assert result.stdout == "", details
    assert "page-limit" in result.stderr, details
    assert "positive integer" in result.stderr, details


@pytest.mark.parametrize(
    ("scenario", "parameters"),
    [
        ("transient", {"fail_for": 2}),
        ("rate-limit", {"rate_limit_for": 2, "retry_after_seconds": 1}),
    ],
)
def test_cli_recovers_from_classified_503_and_429_responses(
    test_run: RunContext,
    scenario: str,
    parameters: dict[str, int],
) -> None:
    database = test_run.storage_dir / f"{scenario}.sqlite3"
    job_id = f"retry-{scenario}"
    scenario_url = test_run.scenario_url(scenario, total_pages=1, **parameters)
    arguments = [
        "run",
        "--url",
        scenario_url,
        "--job-id",
        job_id,
        "--database",
        str(database),
        "--page-limit",
        "1",
        "--job-timeout-seconds",
        "30",
        "--operation-timeout-seconds",
        "10",
        "--retry-max-attempts",
        "3",
        "--retry-initial-delay-seconds",
        "0.01",
        "--retry-max-delay-seconds",
        "0.1",
        "--output-format",
        "json",
    ]
    command = [sys.executable, "-m", "resilient_browser_automation", *arguments]
    result = _run_cli(arguments)
    details = _failure_details(command, result)

    assert result.returncode == 0, details
    summary = json.loads(result.stdout)
    assert summary["outcome"] == "completed", details
    assert summary["checkpoint_page"] == 1, details
    assert summary["item_count"] == 5, details

    api_parameters = {
        **parameters,
        "page": 1,
        "total_pages": 1,
    }
    api_url = test_run.scenario_api_url(scenario, **api_parameters)
    with urlopen(api_url, timeout=5) as response:
        last_attempt = json.loads(response.read())
    assert last_attempt["attempt"] == 4
