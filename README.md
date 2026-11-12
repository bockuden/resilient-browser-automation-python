# Resilient Browser Automation — Python

**Browser automation designed around correct data, bounded recovery, and reproducible evidence.**

[![Python package checks](https://github.com/bockuden/resilient-browser-automation-python/actions/workflows/python-package.yml/badge.svg)](https://github.com/bockuden/resilient-browser-automation-python/actions/workflows/python-package.yml)
[![Status: Planning](https://img.shields.io/badge/status-planning-FBCA04)](#project-status)
[![Python 3.11–3.14](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](#planned-stack)
[![Playwright](https://img.shields.io/badge/Playwright-async_API-2EAD33)](#planned-stack)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Open issues](https://img.shields.io/github/issues/bockuden/resilient-browser-automation-python)](https://github.com/bockuden/resilient-browser-automation-python/issues)
[![Last commit](https://img.shields.io/github/last-commit/bockuden/resilient-browser-automation-python)](https://github.com/bockuden/resilient-browser-automation-python/commits/main/)

A Python and Playwright browser worker being built to handle interrupted jobs,
transient failures, expired sessions, changing selectors, and duplicate records.
The project combines a working implementation with practical walkthroughs of
the decisions behind reliable web data extraction.

[Roadmap](#roadmap) · [Engineering walkthroughs](#engineering-walkthroughs) ·
[Issues](https://github.com/bockuden/resilient-browser-automation-python/issues) ·
[Test Stand](https://github.com/bockuden/resilient-automation-test-stand) ·
[C# companion](https://github.com/bockuden/resilient-browser-automation)

## Project status

**Planning — the worker is under development.** The initial installable package
and CLI help command are in place. Browser extraction, persistence, recovery,
and diagnostics are planned and not available as a working worker yet.

There is no published Python package release or passing CI claim yet. Start with
[issue #1: package and development toolchain](https://github.com/bockuden/resilient-browser-automation-python/issues/1)
or browse the
[milestones](https://github.com/bockuden/resilient-browser-automation-python/milestones).

## The problem

A browser script can work once and still fail as a data collection system.
Pages load late, sessions expire halfway through a job, targets return rate
limits, and processes stop after some results have already been saved.

This project focuses on what happens at those boundaries: which operations may
be retried, what state must survive a restart, how to recognize invalid data,
and what evidence explains a failure afterward.

The goal is a compact, inspectable Python implementation with explicit
guarantees, validated against a deterministic target and explained through
runnable examples.

## Planned capabilities

| Area | Intended behavior |
| --- | --- |
| Browser extraction | Asynchronous Playwright, observable readiness, validated records, and natural pagination end. |
| Retry policy | Classified transient failures, bounded backoff, `Retry-After`, and a total job deadline. |
| Authentication | Isolated job contexts, browser login, and bounded recovery after session expiry. |
| Selector changes | Explicit semantic fallbacks; ambiguous controls fail visibly. |
| Durable state | SQLite transactions that commit page records and their checkpoint together. |
| Idempotency | Stable job/item identities and duplicate delivery without duplicate persisted results. |
| Restart recovery | Continuation from durable progress, tested after forced process termination. |
| Controlled execution | Bounded intake, concurrency, per-target pacing, and graceful cancellation. |
| Diagnostics | Structured events, execution summaries, and bounded screenshot, HTML, and trace capture. |
| Verification | Real-browser E2E, independent database checks, and evidence generated from actual runs. |

## Planned architecture

```mermaid
flowchart LR
    Input["CLI / job input"] --> Worker["Bounded async worker"]
    Worker --> Runner["Job runner"]
    Runner --> Policy["Retry and deadline policy"]
    Runner --> Browser["Playwright catalog adapter"]
    Runner --> Storage["SQLite records and checkpoints"]
    Browser --> Stand["Pinned Test Stand"]
    Runner --> Evidence["Events and failure artifacts"]
    Browser --> Evidence
    Evidence --> Validator["Gauntlet evidence validator"]
```

The runner will own execution rules. The browser adapter will own target
interaction. Storage will own durable state and transaction boundaries.
Target-specific selectors and stand configuration will stay outside the
general execution logic.

The Python design will share useful behavioral guarantees with the C# companion
while using Python's own async resource management, cancellation, typing, and
testing conventions.

## Job and configuration contract

`JobSpec` contains a stable job ID, a target configuration, the target URL, and
a positive page limit. `TargetConfig` owns target-specific settings such as its
base URL and optional credentials. `WorkerConfig` owns operation and total job
timeouts plus `RetrySettings`. These immutable models validate URLs, origins,
limits, and incompatible time budgets at construction time, before a browser
can be created.

When the same setting appears in multiple sources, values resolve in this
order, from lowest to highest priority: built-in defaults, configuration file,
environment, then explicit command-line values. Callers pass normalized
environment settings to `resolve_settings`; the helper does not read or log the
process environment itself.

Configuration diagnostics report job and target names, limits, timeouts, and
retry budgets. They intentionally omit target URLs and credentials. Target
credentials are excluded from model representations as well.

Jobs report one of four terminal outcomes with stable process exit codes:

| Outcome | Exit code |
| --- | ---: |
| `completed` | 0 |
| `failed` | 1 |
| `incomplete` | 2 |
| `cancelled` | 130 |

Expected operational failures use distinct codes: transient target failures
are retryable, while authentication, extraction-contract, and storage failures
are classified separately and are not retried by default. These types define
the worker contract; data collection is being added in subsequent issues.

## Browser ownership

`BrowserManager` owns one Playwright driver and one Chromium process. That
process is shared by the jobs opened through that manager; each call to
`open_job()` creates a fresh `BrowserContext` and page, so cookies and other
authentication state are isolated by default. Exiting a job scope closes its
context, and exiting the manager closes Chromium and Playwright:

```python
async with BrowserManager() as browser:
    async with browser.open_job() as job:
        await job.page.goto("https://example.com/")
```

Use one manager per worker session and one job scope per active job. The
integration suite opens the local Test Stand with Chromium and checks context
isolation without relying on third-party websites.

## How correctness will be demonstrated

The worker will run against the independently released
[Resilient Automation Test Stand](https://github.com/bockuden/resilient-automation-test-stand).
Its
[Automation Gauntlet](https://github.com/bockuden/resilient-automation-test-stand/blob/main/CHALLENGE.md)
defines ten levels covering pagination, retries, authentication, selector
changes, deduplication, checkpoint recovery, session expiry, rate limiting,
and combined failures.

The planned acceptance path is:

1. Run a real browser against a pinned stand release with an isolated run ID.
2. Record observed statuses, retry waits, raw item IDs, and recovery events.
3. Validate the generated evidence with the stand's published validator.
4. Independently inspect committed records and checkpoints in SQLite.
5. Retain the consumer revision, environment details, and diagnostic artifacts.

Worker-level tests will also cover forced process termination, transaction
failure windows, browser loss, and cancellation. These checks complement the
target-server scenarios.

**All ten Gauntlet levels are planned; no level is currently claimed as passed
by this Python implementation.** Track the work in
[M4 — Reproducible evidence](https://github.com/bockuden/resilient-browser-automation-python/milestone/4).

## Engineering walkthroughs

Six short walkthroughs will connect the implementation to practical automation
problems:

| Walkthrough | Question it answers |
| --- | --- |
| Readiness and extraction | How do we distinguish a ready page, a valid empty result, and a loading failure? |
| Retries and rate limits | What can we repeat safely, and when must we stop waiting? |
| Authentication and sessions | How do we restore a session and continue the intended work? |
| Transactions and recovery | What survives if the process stops while saving a page? |
| Concurrency and cancellation | How do we bound resource use and stop cleanly? |
| Diagnosis and artifacts | How do we explain a failed run without reproducing it first? |

Each chapter will include a reproducible failure, the implemented remedy, a
verification command, and its limitations. Examples will use the tested worker
modules rather than a separate tutorial implementation.

## Planned stack

- **Python 3.11–3.14** — supported runtime range; Python 3.13 is the local default.
- **uv** — dependency groups, virtual environments, and a committed lockfile.
- **pytest, Ruff, and mypy** — planned test, lint, formatting, and type-check tools.
- **Playwright / Chromium, SQLite, Docker, and GitHub Actions** — planned worker and integration infrastructure.

The package currently exposes `--help` and `--version`. Worker commands will be
added as their functionality is implemented.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Python 3.11–3.14](https://www.python.org/downloads/), then sync the project and
its development tools:

```powershell
uv sync --locked --all-groups
```

Run the CLI and the project checks:

```powershell
uv run --locked resilient-browser-automation --help
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests
```

### Start the integration Test Stand

Docker must be running. The harness starts the released Test Stand `1.2.0`
using its pinned OCI image digest, binds it to an ephemeral localhost port, and
waits for `GET /health` before reporting the base URL:

```powershell
uv run --locked python -m resilient_browser_automation.test_stand up
```

The command prints the container name, base URL, version, and image reference.
Stop only that harness-owned container with the printed command:

```powershell
uv run --locked python -m resilient_browser_automation.test_stand down rba-test-stand-<name>
```

Each invocation gets its own container and host port, so concurrent runs do not
share a container or reset each other's scenario state. The stand's scenario
state is isolated further by a unique `run_id` per test case. Its container
uses ephemeral storage and is removed when stopped. Pytest cleanup verifies a
harness ownership label before stopping a container; the helper exposes no
reset operation, and its scenario URLs reject a caller-supplied shared `run_id`.

Stand-backed pytest cases can request the `test_run` fixture. It provides a
fresh `run_id`, a scenario URL builder, and a per-case directory under pytest's
`tmp_path`; use `test_run.database_path` for temporary consumer state:

```python
def test_transient_recovery(test_run):
    url = test_run.scenario_url("transient", fail_for=2)
```

`test_run` starts the session-scoped stand on first use. Pytest stops only the
container it started after the session ends. `test_run.run_id` stays fixed for
every URL built from that fixture. A test that restarts its worker can attach to
the same scenario and storage by calling `resume_test_run(base_url, run_id,
storage_dir)` with the values retained alongside its checkpoint; this does not
reset the stand. For example, run the integration checks against the live
container with:

```powershell
uv run --locked pytest tests/integration -m integration
```

The commands above use the committed `uv.lock` so contributors get the same
resolved versions. After intentionally changing dependency constraints, refresh
that lockfile with `uv lock` and verify it with `uv lock --check`.

## Roadmap

| Milestone | Issues | Completion goal |
| --- | --- | --- |
| [M1 — Runnable browser-to-database flow](https://github.com/bockuden/resilient-browser-automation-python/milestone/1) | #1–#8 | A real browser job with verified persisted output. |
| [M2 — Recovery and correctness](https://github.com/bockuden/resilient-browser-automation-python/milestone/2) | #9–#15 | Retries, validation, checkpoint resume, and forced-process recovery. |
| [M3 — Controlled execution and diagnostics](https://github.com/bockuden/resilient-browser-automation-python/milestone/3) | #16–#21 | Bounded concurrency, target pacing, cancellation, and artifacts. |
| [M4 — Reproducible evidence](https://github.com/bockuden/resilient-browser-automation-python/milestone/4) | #22–#27 | Live evidence, ten Gauntlet levels, and CI verification. |
| [M5 — Portfolio release](https://github.com/bockuden/resilient-browser-automation-python/milestone/5) | #28–#33 | Compatibility matrix, walkthroughs, demo, and release artifacts. |
| [M6 — Optional extensions](https://github.com/bockuden/resilient-browser-automation-python/milestone/6) | #34–#36 | Measurements, a second target, and HTTP/browser tradeoffs. |

M6 is optional and does not block the initial release. Every issue has scope,
acceptance criteria, priority, and dependency links. See the
[detailed backlog](GITHUB_BACKLOG.md) for the original plan; GitHub issues track
ongoing progress.

## Scope and guarantee boundaries

The initial deployment will support one worker process per local state database.
Distributed execution and production-scale crawling are outside the initial
scope.

Idempotent persisted results do not imply exactly-once network requests or
exactly-once external side effects. Resume behavior also depends on the target's
pagination and dataset stability; those assumptions will be documented per
adapter.

Screenshots, HTML, and traces may contain target data. Artifact capture will
have explicit controls and documented privacy limits. Deterministic test-stand
success establishes behavior for the tested contract, not universal website
compatibility.

## Related projects

| Project | Role |
| --- | --- |
| [Resilient Automation Test Stand](https://github.com/bockuden/resilient-automation-test-stand) | Independently versioned deterministic failure scenarios and the Gauntlet validator. |
| [Resilient Browser Automation — C#](https://github.com/bockuden/resilient-browser-automation) | Companion implementation for comparing tested behavioral guarantees across languages. |

## Author and license

Created by [Yehor Maksimov](https://github.com/bockuden).

[MIT License](LICENSE) — Copyright (c) 2026 Yehor Maksimov.
