"""Tests for per-case stand identities and scratch storage."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from resilient_browser_automation.test_runs import new_test_run, resume_test_run


def test_test_runs_get_independent_ids_and_storage(tmp_path: Path) -> None:
    first = new_test_run("http://127.0.0.1:52565/", tmp_path)
    second = new_test_run("http://127.0.0.1:52565", tmp_path)

    assert first.run_id != second.run_id
    assert first.storage_dir != second.storage_dir
    assert first.database_path != second.database_path
    assert first.storage_dir.is_dir()
    assert second.storage_dir.is_dir()
    assert not first.database_path.exists()
    assert not second.database_path.exists()


def test_scenario_url_carries_run_id_and_parameters(tmp_path: Path) -> None:
    run = new_test_run("http://127.0.0.1:52565/", tmp_path)

    url = run.scenario_url("transient", fail_for=2, protected=True)
    parsed = urlsplit(url)

    assert parsed.path == "/catalog"
    assert parse_qs(parsed.query) == {
        "scenario": ["transient"],
        "run_id": [run.run_id],
        "fail_for": ["2"],
        "protected": ["true"],
    }


def test_scenario_url_does_not_allow_replacing_run_id(tmp_path: Path) -> None:
    run = new_test_run("http://127.0.0.1:52565", tmp_path)

    with pytest.raises(ValueError, match="run_id is owned"):
        run.scenario_url("success", run_id="shared")


def test_resumed_test_run_keeps_identity_and_storage(tmp_path: Path) -> None:
    original = new_test_run("http://127.0.0.1:52565", tmp_path)
    resumed = resume_test_run("http://127.0.0.1:52565", original.run_id, original.storage_dir)

    assert resumed.run_id == original.run_id
    assert resumed.storage_dir == original.storage_dir
    assert resumed.scenario_url("resume", resume_page=3) == original.scenario_url(
        "resume", resume_page=3
    )
