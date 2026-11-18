"""Asynchronous SQLite persistence for jobs, catalog pages, and checkpoints."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from resilient_browser_automation.catalog import CatalogRecord
from resilient_browser_automation.config import JobSpec
from resilient_browser_automation.errors import StorageError

_SCHEMA_VERSION = 1


class JobState(StrEnum):
    """Persisted state of a collection job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class StoredJob:
    """Job metadata and the last fully committed page."""

    job_id: str
    target_name: str
    target_url: str
    page_limit: int
    state: JobState
    checkpoint_page: int


class SQLiteStore:
    """Persist job progress using short SQLite transactions outside the event loop.

    A catalog item's stable key is ``(job_id, item_id)``. Replaying a page is
    idempotent; if a later successful write contains changed values, that write
    replaces the existing values (last successful write wins).
    """

    def __init__(self, path: str | Path, *, timeout_seconds: float = 5.0) -> None:
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._path = Path(path)
        self._timeout_seconds = timeout_seconds

    async def initialize(self) -> None:
        """Create the versioned schema, without blocking browser event-loop work."""

        await asyncio.to_thread(self._initialize)

    async def create_job(self, job: JobSpec) -> None:
        """Insert the initial pending job row."""

        await asyncio.to_thread(self._create_job, job)

    async def set_job_state(self, job_id: str, state: JobState) -> None:
        """Update a job's observable lifecycle state."""

        await asyncio.to_thread(self._set_job_state, job_id, state)

    async def save_page(
        self, job_id: str, page_number: int, records: tuple[CatalogRecord, ...]
    ) -> None:
        """Commit page records and advance the checkpoint in one transaction."""

        if isinstance(page_number, bool) or not isinstance(page_number, int) or page_number <= 0:
            raise ValueError("page_number must be a positive integer")
        await asyncio.to_thread(self._save_page, job_id, page_number, records)

    async def get_checkpoint(self, job_id: str) -> int:
        """Return the last committed page, or zero for a job without progress."""

        return await asyncio.to_thread(self._get_checkpoint, job_id)

    async def get_job(self, job_id: str) -> StoredJob | None:
        """Return persisted job metadata, if it exists."""

        return await asyncio.to_thread(self._get_job, job_id)

    async def get_records(self, job_id: str) -> tuple[CatalogRecord, ...]:
        """Load all persisted catalog records in stable item-ID order."""

        return await asyncio.to_thread(self._get_records, job_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=self._timeout_seconds)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > _SCHEMA_VERSION:
                    raise StorageError(
                        f"database schema version {version} is newer than supported version "
                        f"{_SCHEMA_VERSION}"
                    )
                if version == 0:
                    connection.executescript(
                        """
                        BEGIN IMMEDIATE;
                        CREATE TABLE jobs (
                            job_id TEXT PRIMARY KEY,
                            target_name TEXT NOT NULL,
                            target_url TEXT NOT NULL,
                            page_limit INTEGER NOT NULL CHECK (page_limit > 0),
                            state TEXT NOT NULL CHECK (state IN (
                                'pending', 'running', 'completed', 'failed',
                                'incomplete', 'cancelled'
                            )),
                            checkpoint_page INTEGER NOT NULL DEFAULT 0
                                CHECK (checkpoint_page >= 0),
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE TABLE catalog_records (
                            job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                            item_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            price TEXT NOT NULL,
                            source_url TEXT NOT NULL,
                            PRIMARY KEY (job_id, item_id)
                        );
                        PRAGMA user_version = 1;
                        COMMIT;
                        """
                    )
        except StorageError:
            raise
        except sqlite3.Error as error:
            raise StorageError("could not initialize SQLite schema") from error

    def _create_job(self, job: JobSpec) -> None:
        now = _utc_now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO jobs (
                        job_id, target_name, target_url, page_limit, state,
                        checkpoint_page, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
                    (
                        job.job_id,
                        job.target.name,
                        job.target_url,
                        job.page_limit,
                        JobState.PENDING.value,
                        now,
                        now,
                    ),
                )
        except sqlite3.Error as error:
            raise StorageError(f"could not create job {job.job_id!r}") from error

    def _set_job_state(self, job_id: str, state: JobState) -> None:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE jobs SET state = ?, updated_at = ? WHERE job_id = ?",
                    (state.value, _utc_now(), job_id),
                )
                if cursor.rowcount != 1:
                    raise StorageError(f"job {job_id!r} does not exist")
        except sqlite3.Error as error:
            raise StorageError(f"could not update job {job_id!r}") from error

    def _save_page(self, job_id: str, page_number: int, records: tuple[CatalogRecord, ...]) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE jobs SET checkpoint_page = max(checkpoint_page, ?), updated_at = ? "
                "WHERE job_id = ?",
                (page_number, _utc_now(), job_id),
            )
            if cursor.rowcount != 1:
                raise StorageError(f"job {job_id!r} does not exist")
            for record in records:
                connection.execute(
                    """INSERT INTO catalog_records (
                        job_id, item_id, name, price, source_url
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (job_id, item_id) DO UPDATE SET
                        name = excluded.name,
                        price = excluded.price,
                        source_url = excluded.source_url""",
                    (
                        job_id,
                        record.item_id,
                        record.name,
                        str(record.price),
                        record.source_url,
                    ),
                )
            connection.commit()
        except StorageError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise StorageError(f"could not commit page {page_number} for job {job_id!r}") from error
        finally:
            connection.close()

    def _get_checkpoint(self, job_id: str) -> int:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT checkpoint_page FROM jobs WHERE job_id = ?", (job_id,)
                ).fetchone()
                if row is None:
                    raise StorageError(f"job {job_id!r} does not exist")
                return int(row[0])
        except sqlite3.Error as error:
            raise StorageError(f"could not read checkpoint for job {job_id!r}") from error

    def _get_job(self, job_id: str) -> StoredJob | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT job_id, target_name, target_url, page_limit, state,
                              checkpoint_page
                       FROM jobs WHERE job_id = ?""",
                    (job_id,),
                ).fetchone()
                if row is None:
                    return None
                return StoredJob(
                    job_id=row["job_id"],
                    target_name=row["target_name"],
                    target_url=row["target_url"],
                    page_limit=row["page_limit"],
                    state=JobState(row["state"]),
                    checkpoint_page=row["checkpoint_page"],
                )
        except (sqlite3.Error, ValueError) as error:
            raise StorageError(f"could not read job {job_id!r}") from error

    def _get_records(self, job_id: str) -> tuple[CatalogRecord, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT item_id, name, price, source_url
                       FROM catalog_records WHERE job_id = ? ORDER BY item_id""",
                    (job_id,),
                ).fetchall()
                return tuple(
                    CatalogRecord(
                        item_id=row["item_id"],
                        name=row["name"],
                        price=_decimal_from_storage(row["price"]),
                        source_url=row["source_url"],
                    )
                    for row in rows
                )
        except sqlite3.Error as error:
            raise StorageError(f"could not read records for job {job_id!r}") from error


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _decimal_from_storage(value: str) -> Decimal:
    return Decimal(value)
