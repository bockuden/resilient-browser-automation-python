"""Shared fixtures for Test Stand backed integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from resilient_browser_automation.test_runs import TestRun, new_test_run
from resilient_browser_automation.test_stand import StandInstance, start_stand, stop_stand


@pytest.fixture(scope="session")
def stand_instance() -> Iterator[StandInstance]:
    """Start one session-scoped stand container and stop only that container."""

    instance = start_stand()
    try:
        yield instance
    finally:
        stop_stand(instance.container_name)


@pytest.fixture
def test_run(stand_instance: StandInstance, tmp_path: Path) -> TestRun:
    """Give each integration test a fresh run ID and temporary storage directory."""

    return new_test_run(stand_instance.base_url, tmp_path)
