"""Isolated scenario identity and scratch storage for stand-backed tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias
from urllib.parse import urlencode
from uuid import uuid4

QueryValue: TypeAlias = str | int | bool


@dataclass(frozen=True, slots=True)
class TestRun:
    """One test case's identity, browser URL, and disposable consumer storage."""

    run_id: str
    base_url: str
    storage_dir: Path

    @property
    def database_path(self) -> Path:
        """Return a run-specific database path without creating a database."""

        return self.storage_dir / "automation.sqlite3"

    def scenario_url(self, scenario: str, **parameters: QueryValue) -> str:
        """Build a browser scenario URL with this run's stable identity."""

        return self._url("/catalog", scenario, parameters)

    def scenario_api_url(self, scenario: str, **parameters: QueryValue) -> str:
        """Build a catalog API URL for retry and response-contract checks."""

        return self._url("/api/catalog", scenario, parameters)

    def _url(self, path: str, scenario: str, parameters: dict[str, QueryValue]) -> str:
        if "run_id" in parameters:
            raise ValueError("run_id is owned by TestRun and cannot be overridden")
        query: dict[str, str] = {"scenario": scenario, "run_id": self.run_id}
        query.update({key: _query_value(value) for key, value in parameters.items()})
        return f"{self.base_url.rstrip('/')}{path}?{urlencode(query)}"


def new_test_run(base_url: str, storage_root: Path) -> TestRun:
    """Allocate a unique stand run ID and isolated temporary storage directory."""

    run_id = uuid4().hex
    storage_dir = storage_root / run_id
    storage_dir.mkdir(parents=True, exist_ok=False)
    return TestRun(run_id=run_id, base_url=base_url.rstrip("/"), storage_dir=storage_dir)


def resume_test_run(base_url: str, run_id: str, storage_dir: Path) -> TestRun:
    """Reattach to an existing test run after a process restart without resetting it."""

    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("run_id must be a non-empty path-safe identifier")
    if not storage_dir.is_dir():
        raise FileNotFoundError(f"Cannot resume run {run_id!r}: storage directory does not exist")
    return TestRun(run_id=run_id, base_url=base_url.rstrip("/"), storage_dir=storage_dir)


def _query_value(value: QueryValue) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
