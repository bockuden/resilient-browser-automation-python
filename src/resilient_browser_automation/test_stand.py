"""Start and stop the pinned integration Test Stand container."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from uuid import uuid4

STAND_VERSION = "1.2.0"
STAND_IMAGE = (
    "ghcr.io/bockuden/resilient-automation-test-stand:1.2.0"
    "@sha256:70620181e3223fa787134b5ab59c6fc014642f13165c60e42905b525ec3b88de"
)
_CONTAINER_PREFIX = "rba-test-stand-"
_OWNER_LABEL = "dev.bockuden.resilient-browser-automation.test-stand"
_READY_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class StandInstance:
    """Connection details for one isolated stand container."""

    container_name: str
    base_url: str
    version: str = STAND_VERSION
    image: str = STAND_IMAGE


def start_stand(*, timeout: float = _READY_TIMEOUT_SECONDS) -> StandInstance:
    """Start a uniquely named stand, publish an ephemeral port, and await /health."""

    name = f"{_CONTAINER_PREFIX}{uuid4().hex[:12]}"
    _docker(
        "run",
        "--detach",
        "--rm",
        "--name",
        name,
        "--label",
        f"{_OWNER_LABEL}=true",
        "--publish",
        "127.0.0.1::8080",
        STAND_IMAGE,
    )
    try:
        published = _docker("port", name, "8080/tcp").strip().splitlines()[0]
        host, port_text = published.rsplit(":", maxsplit=1)
        if host not in {"127.0.0.1", "0.0.0.0", "[::]"}:
            raise RuntimeError(f"Docker published the Test Stand on unexpected host {host!r}")
        instance = StandInstance(name, f"http://127.0.0.1:{int(port_text)}")
        _wait_until_ready(instance.base_url, timeout)
        return instance
    except BaseException:
        stop_stand(name, ignore_missing=True)
        raise


def stop_stand(container_name: str, *, ignore_missing: bool = False) -> None:
    """Stop only a container created by this harness; never target shared services."""

    if not container_name.startswith(_CONTAINER_PREFIX):
        raise ValueError(
            f"Refusing to stop a container outside the harness namespace: {container_name!r}"
        )
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            f'{{{{ index .Config.Labels "{_OWNER_LABEL}" }}}}',
            container_name,
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        if ignore_missing:
            return
        raise RuntimeError(
            f"Cannot inspect Test Stand container {container_name!r}: {result.stderr.strip()}"
        )
    if result.stdout.strip() != "true":
        raise RuntimeError(
            f"Refusing to stop container not owned by this harness: {container_name!r}"
        )
    _docker("stop", container_name)


def _docker(*args: str) -> str:
    result = subprocess.run(
        ["docker", *args],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Docker command failed ({' '.join(args)}): {result.stderr.strip()}")
    return result.stdout


def _wait_until_ready(base_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status == 200:
                    return
                last_error = f"HTTP {response.status}"
        except (OSError, urllib.error.URLError) as error:
            last_error = str(error)
        time.sleep(0.5)
    raise TimeoutError(f"Test Stand did not become ready at {base_url}/health: {last_error}")


def _command() -> int:
    parser = argparse.ArgumentParser(
        description="Manage the pinned Resilient Automation Test Stand."
    )
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("up", help="start an isolated stand and wait for /health")
    down = commands.add_parser("down", help="stop a stand created by this harness")
    down.add_argument("container_name", help="name printed by the up command")
    args = parser.parse_args()
    if args.action == "up":
        instance = start_stand()
        print(json.dumps(asdict(instance), indent=2))
        print(
            "Stop this instance with: resilient-browser-automation-test-stand down "
            + instance.container_name
        )
        return 0
    stop_stand(args.container_name)
    print(f"Stopped {args.container_name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(_command())
    except (RuntimeError, TimeoutError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
