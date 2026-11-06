"""Safety checks for ownership-scoped Test Stand cleanup."""

from __future__ import annotations

import subprocess

import pytest

from resilient_browser_automation.test_stand import stop_stand


def test_stop_refuses_container_outside_harness_namespace() -> None:
    with pytest.raises(ValueError, match="outside the harness namespace"):
        stop_stand("shared-test-stand")


def test_stop_refuses_container_without_harness_owner_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def inspect(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="false\n", stderr="")

    monkeypatch.setattr(subprocess, "run", inspect)

    with pytest.raises(RuntimeError, match="not owned by this harness"):
        stop_stand("rba-test-stand-foreign")

    assert len(calls) == 1
    assert calls[0][0] == "docker"
    assert "inspect" in calls[0]
    assert "stop" not in calls[0]
