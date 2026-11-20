"""End-to-end single-job CLI checks against the pinned browser Test Stand."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import pytest

from resilient_browser_automation.cli import main
from resilient_browser_automation.storage import JobState, SQLiteStore
from resilient_browser_automation.test_runs import TestRun as RunContext

pytestmark = pytest.mark.integration


def test_cli_runs_catalog_and_persists_records(
    test_run: RunContext, capsys: pytest.CaptureFixture[str]
) -> None:
    database = test_run.storage_dir / "cli.sqlite3"
    job_id = "cli-success"

    exit_code = main(
        [
            "run",
            "--url",
            test_run.scenario_url("success", total_pages=2),
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
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert output.err == ""
    summary = json.loads(output.out)
    assert summary["job_id"] == job_id
    assert summary["outcome"] == "completed"
    assert summary["checkpoint_page"] == 2
    assert summary["pages_committed"] == 2
    assert summary["item_count"] == 10
    assert summary["end_reason"] == "natural_end"

    async def read_storage() -> None:
        store = SQLiteStore(database)
        persisted_job = await store.get_job(job_id)
        records = await store.get_records(job_id)
        assert persisted_job is not None and persisted_job.state is JobState.COMPLETED
        assert persisted_job.checkpoint_page == 2
        assert len(records) == 10
        assert records[0].item_id == "item-001"
        assert records[0].name == "Catalog item 1"
        assert records[0].price == Decimal("1.99")
        assert records[0].source_url == test_run.scenario_url("success", total_pages=2)

    asyncio.run(read_storage())
