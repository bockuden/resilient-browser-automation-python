"""Tests for the installed command-line entry point."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

import resilient_browser_automation.cli as cli
from resilient_browser_automation.cli import _write_output, main
from resilient_browser_automation.storage import JobState, SQLiteStore


def test_module_help_is_available() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resilient_browser_automation", "--help"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "usage: resilient-browser-automation" in result.stdout
    assert "--version" in result.stdout
    assert result.stderr == ""


def test_module_reports_package_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resilient_browser_automation", "--version"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "resilient-browser-automation 0.1.0"


def test_invalid_command_input_has_a_distinct_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", "--url", "not-a-url"]) == 64

    output = capsys.readouterr()
    assert output.out == ""
    assert "--url must be an absolute HTTP or HTTPS URL" in output.err


@pytest.mark.parametrize(
    ("cancel", "expected_code", "expected_outcome", "expected_state"),
    [
        (False, 1, "failed", JobState.FAILED),
        (True, 130, "cancelled", JobState.CANCELLED),
    ],
)
def test_execution_failure_and_cancellation_have_distinct_exit_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    cancel: bool,
    expected_code: int,
    expected_outcome: str,
    expected_state: JobState,
) -> None:
    class FakePage:
        async def goto(self, url: str) -> None:
            if cancel:
                raise asyncio.CancelledError
            raise RuntimeError("browser unavailable")

    class FakeBrowserJobContext:
        async def __aenter__(self) -> FakeBrowserJobContext:
            return self

        async def __aexit__(self, *exc_info: object) -> None:
            return None

        page = FakePage()

    class FakeBrowserManager:
        async def __aenter__(self) -> FakeBrowserManager:
            return self

        async def __aexit__(self, *exc_info: object) -> None:
            return None

        def open_job(self) -> FakeBrowserJobContext:
            return FakeBrowserJobContext()

    monkeypatch.setattr(cli, "BrowserManager", FakeBrowserManager)
    database = tmp_path / "failed-job.sqlite3"
    exit_code = main(
        [
            "run",
            "--url",
            "https://catalog.example/items",
            "--job-id",
            "failed-job",
            "--database",
            str(database),
            "--output-format",
            "json",
        ]
    )

    output = capsys.readouterr()
    summary = json.loads(output.out)
    assert exit_code == expected_code
    assert summary["outcome"] == expected_outcome
    assert summary["checkpoint_page"] == 0
    assert output.err.startswith("error:")

    async def read_state() -> None:
        job = await SQLiteStore(database).get_job("failed-job")
        assert job is not None and job.state is expected_state

    asyncio.run(read_state())


def test_human_diagnostics_are_separate_from_machine_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary = {
        "job_id": "job-001",
        "target": "catalog",
        "outcome": "failed",
        "checkpoint_page": 2,
        "pages_committed": 2,
        "item_count": 7,
        "end_reason": None,
        "database": "data.sqlite3",
        "error": "target unavailable",
    }

    _write_output("json", summary, "target unavailable")
    machine_output = capsys.readouterr()
    assert json.loads(machine_output.out) == summary
    assert machine_output.err == "error: target unavailable\n"

    _write_output("human", summary, "target unavailable")
    human_output = capsys.readouterr()
    assert "Outcome: failed" in human_output.out
    assert "Committed pages: 2" in human_output.out
    assert not human_output.out.startswith("{")
    assert human_output.err == "error: target unavailable\n"
