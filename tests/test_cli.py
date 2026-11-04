"""Tests for the installed command-line entry point."""

from __future__ import annotations

import subprocess
import sys


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
