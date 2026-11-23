"""End-to-end CLI checks against the pinned browser Test Stand."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def _failure_details(
    command: list[str], result: subprocess.CompletedProcess[str]
) -> str:
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


def test_cli_rejects_invalid_page_limit() -> None:
    arguments = ["run", "--url", "http://127.0.0.1:1/catalog", "--page-limit", "0"]
    result = _run_cli(arguments)
    command = [sys.executable, "-m", "resilient_browser_automation", *arguments]
    details = _failure_details(command, result)

    assert result.returncode == 64, details
    assert result.stdout == "", details
    assert "page-limit" in result.stderr, details
    assert "positive integer" in result.stderr, details

