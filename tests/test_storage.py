"""Persistence tests against real temporary SQLite databases."""

from __future__ import annotations

import asyncio
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from resilient_browser_automation import (
    CatalogRecord,
    JobSpec,
    StorageError,
    TargetConfig,
)
from resilient_browser_automation.storage import JobState, SQLiteStore, StoredJob


def _job() -> JobSpec:
    return JobSpec(
        job_id="job-001",
        target=TargetConfig(name="catalog", base_url="https://catalog.example"),
        target_url="https://catalog.example/items?category=books",
        page_limit=5,
    )


def _record(item_id: str, name: str | None = None) -> CatalogRecord:
    return CatalogRecord(
        item_id=item_id,
        name=name or f"Name for {item_id}",
        price=Decimal("19.95"),
        source_url="https://catalog.example/items?category=books",
    )


async def _store(path: Path) -> SQLiteStore:
    store = SQLiteStore(path)
    await store.initialize()
    await store.create_job(_job())
    return store


def test_failed_page_transaction_commits_neither_rows_nor_checkpoint(tmp_path: Path) -> None:
    async def run() -> None:
        database = tmp_path / "worker.sqlite3"
        store = await _store(database)
        with sqlite3.connect(database) as connection:
            connection.execute(
                """CREATE TRIGGER reject_test_record BEFORE INSERT ON catalog_records
                   WHEN NEW.item_id = 'item-002'
                   BEGIN SELECT RAISE(ABORT, 'injected write failure'); END"""
            )

        with pytest.raises(StorageError, match="could not commit page"):
            await store.save_page("job-001", 1, (_record("item-001"), _record("item-002")))

        assert await store.get_records("job-001") == ()
        assert await store.get_checkpoint("job-001") == 0
        job = await store.get_job("job-001")
        assert job is not None and job.state is JobState.PENDING

    asyncio.run(run())


def test_replaying_a_page_does_not_duplicate_persisted_items(tmp_path: Path) -> None:
    async def run() -> None:
        store = await _store(tmp_path / "worker.sqlite3")
        records = (_record("item-001"), _record("item-002"))

        await store.save_page("job-001", 1, records)
        await store.save_page("job-001", 1, records)

        stored_records = await store.get_records("job-001")
        assert stored_records == records
        assert await store.get_checkpoint("job-001") == 1

    asyncio.run(run())


def test_conflicting_item_values_use_last_successful_write(tmp_path: Path) -> None:
    async def run() -> None:
        store = await _store(tmp_path / "worker.sqlite3")
        original = _record("item-001", "Original name")
        revised = CatalogRecord(
            item_id="item-001",
            name="Revised name",
            price=Decimal("21.40"),
            source_url="https://catalog.example/items?page=2",
        )

        await store.save_page("job-001", 1, (original,))
        await store.save_page("job-001", 2, (revised,))

        assert await store.get_records("job-001") == (revised,)
        assert await store.get_checkpoint("job-001") == 2

    asyncio.run(run())


def test_real_database_persists_job_metadata_and_schema_version(tmp_path: Path) -> None:
    async def run() -> None:
        database = tmp_path / "worker.sqlite3"
        store = await _store(database)
        await store.set_job_state("job-001", JobState.RUNNING)
        await store.save_page("job-001", 3, (_record("item-003"),))

        assert await store.get_job("job-001") == StoredJob(
            job_id="job-001",
            target_name="catalog",
            target_url="https://catalog.example/items?category=books",
            page_limit=5,
            state=JobState.RUNNING,
            checkpoint_page=3,
        )
        assert await store.get_records("job-001") == (_record("item-003"),)

        with sqlite3.connect(database) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
            assert connection.execute(
                "SELECT price, source_url FROM catalog_records WHERE job_id = ? AND item_id = ?",
                ("job-001", "item-003"),
            ).fetchone() == (
                "19.95",
                "https://catalog.example/items?category=books",
            )

    asyncio.run(run())
