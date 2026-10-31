# Resilient Browser Automation — Python

Reliable browser automation in Python with Playwright: bounded retries, durable
checkpoints, crash recovery, and reproducible failure tests. Includes practical
engineering walkthroughs.

**Status: planning.** The implementation is not available yet. The capabilities
below describe the intended project, not completed functionality.

## Project goal

Build an idiomatic asynchronous Python worker that extracts catalog data,
persists correct results, and recovers from reproducible failures. Validate its
behavior against the independently versioned
[Resilient Automation Test Stand](https://github.com/bockuden/resilient-automation-test-stand)
and document the engineering decisions through executable walkthroughs.

The companion
[C# implementation](https://github.com/bockuden/resilient-browser-automation)
provides a reference for behavioral guarantees. The Python implementation will
use its own appropriate structure and resource-management patterns.

## Roadmap

| Milestone | Intended outcome |
| --- | --- |
| M1 — Runnable browser-to-database flow | A real browser job with verified persisted output. |
| M2 — Recovery and correctness | Bounded retries, validation, checkpoint resume, and forced-process recovery. |
| M3 — Controlled execution and diagnostics | Bounded concurrency, target pacing, cancellation, and failure artifacts. |
| M4 — Reproducible evidence | Runtime evidence and real-browser verification of all ten Gauntlet levels. |
| M5 — Portfolio release | Documented guarantees, executable walkthroughs, a demo, and installable artifacts. |
| M6 — Optional extensions | Performance measurements, a second target, and HTTP/browser tradeoffs. |

See the [GitHub issues](https://github.com/bockuden/resilient-browser-automation-python/issues),
[milestones](https://github.com/bockuden/resilient-browser-automation-python/milestones),
and [detailed backlog](GITHUB_BACKLOG.md).

Start with [issue #1](https://github.com/bockuden/resilient-browser-automation-python/issues/1).
The initial release does not depend on the optional M6 extensions.

## Intended guarantees and scope

- Commit extracted records and the corresponding checkpoint atomically.
- Keep retry, timeout, concurrency, and cleanup budgets finite.
- Preserve cancellation and explicit resource ownership across async operations.
- Validate persisted results independently of worker-generated evidence.
- Use real browser execution for browser acceptance tests.
- Support one worker process per local state database initially.

Idempotent persisted results do not imply exactly-once network requests or
exactly-once external side effects. Distributed execution and production-scale
crawling are outside the initial scope.
