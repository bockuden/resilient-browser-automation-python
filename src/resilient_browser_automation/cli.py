"""Command-line entry point for the browser automation worker."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from resilient_browser_automation import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(
        prog="resilient-browser-automation",
        description="Reliable browser automation with bounded retries and durable recovery.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse command-line arguments."""
    build_parser().parse_args(argv)
    return 0
