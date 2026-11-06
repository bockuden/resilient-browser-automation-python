"""Live checks for Test Stand run state across retries and reattachment."""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from resilient_browser_automation.test_runs import TestRun as RunContext
from resilient_browser_automation.test_runs import resume_test_run

pytestmark = pytest.mark.integration


def _get_status(url: str) -> tuple[int, bytes]:
    try:
        with urlopen(url, timeout=5) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def test_retry_and_reattachment_preserve_run_state(test_run: RunContext) -> None:
    request_url = test_run.scenario_api_url("transient", page=1, fail_for=1)

    first_status, _ = _get_status(request_url)
    resumed = resume_test_run(test_run.base_url, test_run.run_id, test_run.storage_dir)
    retry_status, retry_body = _get_status(
        resumed.scenario_api_url("transient", page=1, fail_for=1)
    )

    assert first_status == 503
    assert retry_status == 200
    assert json.loads(retry_body)["attempt"] == 2
    assert resumed.run_id == test_run.run_id
    assert resumed.database_path == test_run.database_path
