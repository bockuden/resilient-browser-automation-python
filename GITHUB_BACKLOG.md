# Resilient Browser Automation — Python

Repository: [bockuden/resilient-browser-automation-python](https://github.com/bockuden/resilient-browser-automation-python)

Project description:

> Reliable browser automation in Python with Playwright: bounded retries, durable checkpoints, crash recovery, and reproducible failure tests. Includes practical engineering walkthroughs.

All 36 issues have been published on GitHub with labels, milestones, and linked dependencies. `B01`–`B36` remain stable planning identifiers. The mapping to GitHub issue numbers is stored in [docs/backlog-issues.json](docs/backlog-issues.json). GitHub issues are the source of truth for ongoing progress; this document preserves the initial plan.

## Product goal

Build an idiomatic Python browser worker that extracts a catalog, persists correct results, and recovers from reproducible failures. Demonstrate its behavior against the independently versioned Resilient Automation Test Stand. Explain the implementation through runnable engineering walkthroughs.

Preserve useful behavioral guarantees from the C# implementation, while choosing Python-specific structure and resource management. Do not require matching class hierarchies or identical database schemas.

## Milestones and priorities

| Milestone | Issues | Exit condition |
| --- | --- | --- |
| M1 — Runnable browser-to-database flow | B01–B08 | A clean checkout can run a real browser job and verify its persisted output. |
| M2 — Recovery and correctness | B09–B15 | The worker recovers from supported failures and process interruption without losing committed results. |
| M3 — Controlled execution and diagnostics | B16–B21 | Work, cancellation, resource recovery, logs, and artifacts have explicit limits. |
| M4 — Reproducible evidence | B22–B27 | Live browser runs produce evidence checked by CI and the stand validator. |
| M5 — Portfolio release | B28–B33 | The project has documented guarantees, executable walkthroughs, and a reproducible release. |
| M6 — Optional extensions | B34–B36 | Additional evidence of performance, portability, or HTTP/browser tradeoffs. |

Priority labels: `priority:p0` for B01–B15; `priority:p1` for B16–B33; `priority:p2` for B34–B36. Priority describes delivery order, not incident severity. M1 is a functional baseline; M2 is the first useful recovery demo; M5 is the intended public portfolio release.

Suggested type labels: `type:feature`, `type:test`, `type:docs`, `type:infra`, `type:research`.

Suggested area labels: `area:browser`, `area:storage`, `area:resilience`, `area:worker`, `area:evidence`, `area:tooling`, `area:docs`.

Keep all issues in the backlog, but work on only one small dependency-ready slice at a time. An issue is complete when its acceptance criteria are met; adding more abstractions or more coverage is not a completion criterion.

## Shared implementation constraints

- Use the real browser path for browser acceptance tests. An HTTP client must not silently replace browser extraction.
- Pin the stand release used for acceptance. The initial proposed release is `1.2.0`, which was inspected during planning; record the chosen image digest when implementing the harness.
- Keep the general runner separate from the stand-specific catalog adapter.
- Give one process ownership of a local state database in the initial supported deployment. Distributed execution is outside the initial scope.
- Promise idempotent persisted results within the defined job and item keys. Do not claim global exactly-once execution or absence of repeated network requests after a crash.
- Record evidence from observed execution. Expected values belong in assertions, not in generated evidence.
- Do not modify the stand merely to make a failing consumer test pass. Contract defects should be reproduced and handled separately.
- Avoid maintaining a second, independent implementation just for the tutorial. Walkthroughs should use the same tested worker modules.

---

## B01 — Bootstrap an installable Python package and development toolchain

**GitHub:** [#1](https://github.com/bockuden/resilient-browser-automation-python/issues/1)

**Milestone:** M1

**Labels:** `priority:p0`, `type:infra`, `area:tooling`

**Depends on:** None

### Goal
Create a small, idiomatic package that can be installed and developed from a clean checkout.

### Scope
Add a `src/` layout, `pyproject.toml`, a CLI entry point, dependency locking, pytest, Ruff, and one static type checker. Choose and document supported Python versions. Avoid reproducing the C# solution structure.

### Acceptance criteria
- [ ] A fresh environment can install the package and run the CLI help command.
- [ ] Formatting, lint, type checking, and tests have documented commands.
- [ ] The chosen dependency workflow reproduces the development environment.
- [ ] Browser binaries, databases, credentials, and generated artifacts are excluded from Git.

---

## B02 — Add a pinned Test Stand integration harness

**GitHub:** [#2](https://github.com/bockuden/resilient-browser-automation-python/issues/2)

**Milestone:** M1

**Labels:** `priority:p0`, `type:infra`, `area:tooling`

**Depends on:** [B01 / #1](https://github.com/bockuden/resilient-browser-automation-python/issues/1)

### Goal
Make integration failures reproducible without depending on third-party websites.

### Scope
Start the pinned stand, wait for readiness, allocate an isolated run ID, expose scenario URLs to tests, and clean up owned resources. Record the stand version and image digest. Provide separate setup for tests that intentionally preserve a run across process restarts.

### Acceptance criteria
- [ ] A documented command starts the exact selected stand release and verifies readiness.
- [ ] Independent test cases use independent run IDs and temporary storage.
- [ ] Retries and resume within one scenario preserve its run ID; no reset occurs between retry attempts.
- [ ] Tests cannot accidentally reset a shared stand used by concurrently running scenarios.

---

## B03 — Define typed jobs, configuration, outcomes, and error categories

**GitHub:** [#3](https://github.com/bockuden/resilient-browser-automation-python/issues/3)

**Milestone:** M1

**Labels:** `priority:p0`, `type:feature`, `area:worker`

**Depends on:** [B01 / #1](https://github.com/bockuden/resilient-browser-automation-python/issues/1)

### Goal
Make invalid input and execution outcomes explicit before browser work starts.

### Scope
Define job identity, target URL, page limits, timeout budgets, retry settings, result types, and a small error taxonomy. Separate target-specific configuration from worker configuration. Specify configuration precedence and stable exit outcomes.

### Acceptance criteria
- [ ] Invalid URLs, nonpositive limits, and incompatible configuration fail before browser startup.
- [ ] Completion, failure, cancellation, and incomplete work have distinguishable outcomes.
- [ ] Transient target failures, authentication failures, extraction contract failures, and storage failures can be distinguished.
- [ ] Configuration diagnostics avoid printing credential values.

---

## B04 — Implement asynchronous browser and context lifecycle management

**GitHub:** [#4](https://github.com/bockuden/resilient-browser-automation-python/issues/4)

**Milestone:** M1

**Labels:** `priority:p0`, `type:feature`, `area:browser`

**Depends on:** [B01 / #1](https://github.com/bockuden/resilient-browser-automation-python/issues/1), [B03 / #3](https://github.com/bockuden/resilient-browser-automation-python/issues/3)

### Goal
Provide a reliable resource boundary around Playwright and each browser job.

### Scope
Use Playwright's asynchronous API and explicit resource ownership. Give each active job an isolated browser context. Document whether the browser process is shared. Clean up partially initialized resources as well as successful sessions.

### Acceptance criteria
- [ ] A real Chromium smoke test opens a page and closes its owned resources.
- [ ] Two contexts do not share authentication state by default.
- [ ] Initialization and operation failures do not leave owned contexts open.
- [ ] Cleanup failure does not obscure the original operation failure.

---

## B05 — Extract catalog records and follow pagination through the browser

**GitHub:** [#5](https://github.com/bockuden/resilient-browser-automation-python/issues/5)

**Milestone:** M1

**Labels:** `priority:p0`, `type:feature`, `area:browser`

**Depends on:** [B02 / #2](https://github.com/bockuden/resilient-browser-automation-python/issues/2), [B03 / #3](https://github.com/bockuden/resilient-browser-automation-python/issues/3), [B04 / #4](https://github.com/bockuden/resilient-browser-automation-python/issues/4)

### Goal
Implement the smallest complete browser extraction adapter.

### Scope
Read stable item IDs, names, prices, and source provenance. Follow the next-page control. Wait for observable readiness rather than arbitrary sleeps. Distinguish a legitimate catalog end from loading failure, missing required structure, or exhaustion of a configured page limit.

### Acceptance criteria
- [ ] The success scenario produces the expected records through actual browser interaction.
- [ ] Prices retain their intended decimal value.
- [ ] Natural pagination end and configured truncation are reported distinctly.
- [ ] A loading or navigation failure cannot silently become successful empty output.

---

## B06 — Persist page results and checkpoints atomically in SQLite

**GitHub:** [#6](https://github.com/bockuden/resilient-browser-automation-python/issues/6)

**Milestone:** M1

**Labels:** `priority:p0`, `type:feature`, `area:storage`

**Depends on:** [B03 / #3](https://github.com/bockuden/resilient-browser-automation-python/issues/3)

### Goal
Ensure that a committed checkpoint never refers to page data that was not committed.

### Scope
Add schema creation/versioning, job state, catalog records, and checkpoints. Store records and the associated page checkpoint in one transaction. Choose a stable uniqueness key and an explicit policy for conflicting duplicates. Choose a database access model that does not block unrelated browser work during long operations.

### Acceptance criteria
- [ ] A failed page transaction commits neither partial records nor an advanced checkpoint.
- [ ] Replaying the same page does not create duplicate persisted records.
- [ ] Conflicting values for an existing item follow a documented policy.
- [ ] Tests use a real temporary SQLite database and verify stored values, not only row counts.

---

## B07 — Wire a single-job CLI from browser input to persisted result

**GitHub:** [#7](https://github.com/bockuden/resilient-browser-automation-python/issues/7)

**Milestone:** M1

**Labels:** `priority:p0`, `type:feature`, `area:worker`

**Depends on:** [B03 / #3](https://github.com/bockuden/resilient-browser-automation-python/issues/3), [B05 / #5](https://github.com/bockuden/resilient-browser-automation-python/issues/5), [B06 / #6](https://github.com/bockuden/resilient-browser-automation-python/issues/6)

### Goal
Allow a user to run one complete extraction without writing Python code.

### Scope
Connect configuration, browser adapter, page persistence, and a machine-readable final summary. Keep orchestration independent of stand-specific selectors. Establish a small, stable command interface.

### Acceptance criteria
- [ ] One documented command runs a catalog job and writes durable results.
- [ ] The summary includes job identity, outcome, committed progress, and item count.
- [ ] Exit codes distinguish success, invalid input, execution failure, and cancellation.
- [ ] Human diagnostics and machine-readable output can be consumed separately.

---

## B08 — Add a real-browser end-to-end test for the complete vertical slice

**GitHub:** [#8](https://github.com/bockuden/resilient-browser-automation-python/issues/8)

**Milestone:** M1

**Labels:** `priority:p0`, `type:test`, `area:browser`

**Depends on:** [B02 / #2](https://github.com/bockuden/resilient-browser-automation-python/issues/2), [B07 / #7](https://github.com/bockuden/resilient-browser-automation-python/issues/7)

### Goal
Prove the installed CLI works with Chromium, the stand, and SQLite together.

### Scope
Run the CLI as a subprocess against the pinned stand and assert its exit status, summary, database contents, and cleanup. Include natural pagination end and a small invalid-input case.

### Acceptance criteria
- [ ] The test launches a real browser and does not use fake page objects.
- [ ] The exact expected IDs and representative field values are persisted.
- [ ] The subprocess finishes within a bounded timeout and resources are cleaned up.
- [ ] Failure output provides enough information to reproduce the run.

---

## B09 — Implement classified retries, Retry-After, and a total job deadline

**GitHub:** [#9](https://github.com/bockuden/resilient-browser-automation-python/issues/9)

**Milestone:** M2

**Labels:** `priority:p0`, `type:feature`, `area:resilience`

**Depends on:** [B03 / #3](https://github.com/bockuden/resilient-browser-automation-python/issues/3), [B07 / #7](https://github.com/bockuden/resilient-browser-automation-python/issues/7)

### Goal
Recover from supported transient failures while keeping work and waiting bounded.

### Scope
Retry only classified, safely repeatable operations. Support bounded backoff with jitter and `Retry-After` delay-seconds and HTTP-date values. Use a monotonic clock for elapsed budgets and deadline calculations; handle HTTP-date conversion explicitly. Keep permanent errors and cancellation outside retry handling.

### Acceptance criteria
- [ ] The stand's 503 and 429 scenarios recover within the configured budget.
- [ ] Invalid headers have a documented fallback, and an excessive wait ends the job rather than violating its deadline.
- [ ] Permanent failures and cancellation do not trigger retries.
- [ ] Clock, sleep, and randomness can be controlled in policy tests; a real-browser case verifies integration.

---

## B10 — Support browser login and bounded recovery from session expiry

**GitHub:** [#10](https://github.com/bockuden/resilient-browser-automation-python/issues/10)

**Milestone:** M2

**Labels:** `priority:p0`, `type:feature`, `area:browser`

**Depends on:** [B05 / #5](https://github.com/bockuden/resilient-browser-automation-python/issues/5), [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9)

### Goal
Continue a protected catalog job when its authenticated session expires.

### Scope
Implement initial login and reauthentication through the browser. Preserve the intended continuation location. Bound reauthentication attempts and distinguish invalid credentials from a recoverable session expiry.

### Acceptance criteria
- [ ] A protected catalog succeeds with valid configured credentials.
- [ ] Session expiry causes bounded reauthentication and continuation of the intended work.
- [ ] Invalid credentials terminate with an explicit error and no login loop.
- [ ] Authentication details are excluded from application logs and summaries.

---

## B11 — Handle selector changes with explicit and observable fallback rules

**GitHub:** [#11](https://github.com/bockuden/resilient-browser-automation-python/issues/11)

**Milestone:** M2

**Labels:** `priority:p0`, `type:feature`, `area:browser`

**Depends on:** [B05 / #5](https://github.com/bockuden/resilient-browser-automation-python/issues/5)

### Goal
Survive supported presentation changes without silently interacting with the wrong element.

### Scope
Define selector resolution and semantic fallback inside the catalog adapter. Distinguish missing, delayed, hidden, disabled, and ambiguous controls. Record which supported fallback was used. Keep stand selector metadata out of the generic runner.

### Acceptance criteria
- [ ] Supported selector-change scenarios complete with the correct dataset.
- [ ] Ambiguous actionable controls fail explicitly instead of selecting the first match.
- [ ] A missing required field is not interpreted as an empty successful record.
- [ ] Fallback use is observable and covered by focused browser tests.

---

## B12 — Validate extracted data and detect silent corruption

**GitHub:** [#12](https://github.com/bockuden/resilient-browser-automation-python/issues/12)

**Milestone:** M2

**Labels:** `priority:p0`, `type:feature`, `area:resilience`

**Depends on:** [B05 / #5](https://github.com/bockuden/resilient-browser-automation-python/issues/5), [B06 / #6](https://github.com/bockuden/resilient-browser-automation-python/issues/6)

### Goal
Prevent apparently successful jobs from persisting incomplete or invalid output.

### Scope
Validate required fields, stable IDs, price representation, page-level structure, and pagination consistency before commit. Document what makes an empty catalog valid. Distinguish acceptable duplicate records from invalid records and conflicting data.

### Acceptance criteria
- [ ] Malformed required data fails with a meaningful extraction error.
- [ ] An invalid page leaves its checkpoint unchanged.
- [ ] Cross-page duplicates follow the persistence policy without hiding malformed records.
- [ ] Tests assert exact record content and cover a legitimate empty-result case where supported.

---

## B13 — Resume failed jobs from durable checkpoints with explicit continuation semantics

**GitHub:** [#13](https://github.com/bockuden/resilient-browser-automation-python/issues/13)

**Milestone:** M2

**Labels:** `priority:p0`, `type:feature`, `area:storage`

**Depends on:** [B06 / #6](https://github.com/bockuden/resilient-browser-automation-python/issues/6), [B07 / #7](https://github.com/bockuden/resilient-browser-automation-python/issues/7), [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9)

### Goal
Allow a new execution to continue an incomplete job from its committed state.

### Scope
Load the checkpoint before new extraction and persist any continuation information required by the adapter. Define behavior for completed jobs, missing state, incompatible state, and interrupted finalization. Distinguish resume of extraction from network requests required to restore browser navigation.

### Acceptance criteria
- [ ] A new process can resume after a deterministic failure on page 3 with pages 1–2 already committed.
- [ ] Committed data remains intact and the final dataset is correct.
- [ ] The stand-specific resume path can satisfy its no-refetch objective; any general target limitations are documented.
- [ ] A crash after the final page commit but before final job status is recoverable.

---

## B14 — Prove recovery after forced process termination

**GitHub:** [#14](https://github.com/bockuden/resilient-browser-automation-python/issues/14)

**Milestone:** M2

**Labels:** `priority:p0`, `type:test`, `area:resilience`

**Depends on:** [B08 / #8](https://github.com/bockuden/resilient-browser-automation-python/issues/8), [B13 / #13](https://github.com/bockuden/resilient-browser-automation-python/issues/13)

### Goal
Prove recovery from abrupt process death, beyond exception handling and graceful shutdown.

### Scope
Build a subprocess test with deterministic synchronization around durable page boundaries. Terminate the worker forcibly, restart it against the same database and scenario, and check the output. Keep test synchronization hooks outside normal product behavior.

### Acceptance criteria
- [ ] The harness kills a real worker process rather than raising a normal application exception.
- [ ] Restart produces the exact final dataset without duplicate persisted keys or lost committed items.
- [ ] The test avoids timing guesses such as sleeping for an arbitrary number of seconds before killing the worker.
- [ ] Owned browser processes are cleaned up, and the supported test platform is documented.

---

## B15 — Define job identity, idempotent redelivery, and local database ownership

**GitHub:** [#15](https://github.com/bockuden/resilient-browser-automation-python/issues/15)

**Milestone:** M2

**Labels:** `priority:p0`, `type:feature`, `area:storage`

**Depends on:** [B03 / #3](https://github.com/bockuden/resilient-browser-automation-python/issues/3), [B06 / #6](https://github.com/bockuden/resilient-browser-automation-python/issues/6), [B13 / #13](https://github.com/bockuden/resilient-browser-automation-python/issues/13)

### Goal
Prevent duplicate delivery or incompatible job reuse from corrupting state.

### Scope
Define which fields establish job identity and checkpoint compatibility. Separate target identity from operational retry settings and controlled failure/recovery scenario changes. Enforce the initial one-process-per-state-database contract with crash-safe ownership, and reject duplicate active jobs within that process.

### Acceptance criteria
- [ ] Re-delivery of an already completed compatible job returns without opening a browser.
- [ ] Incompatible reuse of a job ID is rejected with an actionable explanation.
- [ ] Concurrent active delivery of the same job cannot create competing writers.
- [ ] A second worker process is rejected while the database is owned; ownership can be reacquired after process death without an unsafe stale-lock guess.

---

## B16 — Add bounded job intake, concurrency, and backpressure

**GitHub:** [#16](https://github.com/bockuden/resilient-browser-automation-python/issues/16)

**Milestone:** M3

**Labels:** `priority:p1`, `type:feature`, `area:worker`

**Depends on:** [B07 / #7](https://github.com/bockuden/resilient-browser-automation-python/issues/7), [B15 / #15](https://github.com/bockuden/resilient-browser-automation-python/issues/15)

### Goal
Process multiple jobs without creating unbounded tasks, contexts, or buffered input.

### Scope
Introduce bounded intake and a fixed concurrency limit. Isolate per-job failures and define how invalid input records affect a batch. Preserve serial page progression within one job unless a future design explicitly changes its checkpoint model.

### Acceptance criteria
- [ ] Active jobs and queued jobs never exceed their configured bounds.
- [ ] Large input is consumed incrementally rather than loaded fully into memory.
- [ ] Failure of one job follows a documented batch policy and does not accidentally cancel unrelated jobs.
- [ ] Context isolation and storage correctness hold under concurrent execution.

---

## B17 — Pace target operations and coordinate rate-limit cooldowns

**GitHub:** [#17](https://github.com/bockuden/resilient-browser-automation-python/issues/17)

**Milestone:** M3

**Labels:** `priority:p1`, `type:feature`, `area:worker`

**Depends on:** [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9), [B16 / #16](https://github.com/bockuden/resilient-browser-automation-python/issues/16)

### Goal
Control the rate of relevant target operations across jobs in one worker process.

### Scope
Define a target key and a shared limiter for worker-initiated catalog operations, including pagination and retries. Coordinate target cooldown after 429 responses. Specify the scope clearly: this is not automatically a limiter for every browser subresource or for multiple machines.

### Acceptance criteria
- [ ] Jobs sharing a target respect the configured aggregate operation limit.
- [ ] An unrelated target can progress while another target is cooling down.
- [ ] Retries cannot bypass target pacing and remain within the total job deadline.
- [ ] Timing behavior is checked with a controllable clock and an integration scenario.

---

## B18 — Implement graceful shutdown and cancellation across asynchronous boundaries

**GitHub:** [#18](https://github.com/bockuden/resilient-browser-automation-python/issues/18)

**Milestone:** M3

**Labels:** `priority:p1`, `type:feature`, `area:worker`

**Depends on:** [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9), [B13 / #13](https://github.com/bockuden/resilient-browser-automation-python/issues/13), [B16 / #16](https://github.com/bockuden/resilient-browser-automation-python/issues/16)

### Goal
Stop predictably during browser operations, queue waits, retry delays, and persistence.

### Scope
Stop intake first, apply a configurable grace period, then cancel remaining work. Preserve asyncio cancellation semantics. Define transaction behavior if cancellation arrives during commit and bound cleanup operations. Document supported shutdown signals per platform.

### Acceptance criteria
- [ ] Cancellation during navigation, retry waiting, and queue waiting completes within a documented bound.
- [ ] Cancellation is not converted into a transient failure or a successful result.
- [ ] Persisted state remains consistent and resumable.
- [ ] Owned browser resources are closed and the CLI returns the documented outcome.

---

## B19 — Recover from browser or context loss within a finite restart budget

**GitHub:** [#19](https://github.com/bockuden/resilient-browser-automation-python/issues/19)

**Milestone:** M3

**Labels:** `priority:p1`, `type:feature`, `area:browser`

**Depends on:** [B04 / #4](https://github.com/bockuden/resilient-browser-automation-python/issues/4), [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9), [B13 / #13](https://github.com/bockuden/resilient-browser-automation-python/issues/13), [B16 / #16](https://github.com/bockuden/resilient-browser-automation-python/issues/16)

### Goal
Handle browser infrastructure failure separately from target HTTP failures.

### Scope
Detect closed contexts and disconnected browser processes. Recreate necessary resources and continue from durable progress where safe. Bound restarts and define behavior when a shared browser failure affects multiple jobs.

### Acceptance criteria
- [ ] A controlled browser/context termination is reproduced by an integration test.
- [ ] Eligible jobs recover without losing committed results or duplicating persisted keys.
- [ ] Concurrent jobs do not trigger competing uncontrolled browser restarts.
- [ ] Exhausting the restart budget terminates with a clear failure category.

---

## B20 — Add structured execution events and useful operational summaries

**GitHub:** [#20](https://github.com/bockuden/resilient-browser-automation-python/issues/20)

**Milestone:** M3

**Labels:** `priority:p1`, `type:feature`, `area:evidence`

**Depends on:** [B07 / #7](https://github.com/bockuden/resilient-browser-automation-python/issues/7), [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9), [B16 / #16](https://github.com/bockuden/resilient-browser-automation-python/issues/16)

### Goal
Make progress, retries, recovery, and terminal outcomes explainable from one run.

### Scope
Define structured events with job/run identity, page, attempt, failure category, and timing. Distinguish unique saved records, raw extracted records, retries, and recovery events. Keep logging separate from domain decisions and avoid unnecessary observability infrastructure.

### Acceptance criteria
- [ ] Events can be correlated across retries and process restarts.
- [ ] A machine-readable summary reports meaningful counts and completion status.
- [ ] URL query credentials, passwords, and cookies do not appear in application logs.
- [ ] Observability failures do not replace the original execution failure.

---

## B21 — Capture bounded failure artifacts and document their privacy limits

**GitHub:** [#21](https://github.com/bockuden/resilient-browser-automation-python/issues/21)

**Milestone:** M3

**Labels:** `priority:p1`, `type:feature`, `area:evidence`

**Depends on:** [B04 / #4](https://github.com/bockuden/resilient-browser-automation-python/issues/4), [B20 / #20](https://github.com/bockuden/resilient-browser-automation-python/issues/20)

### Goal
Leave actionable evidence when a browser job fails terminally.

### Scope
Capture error metadata, screenshot, HTML, and Playwright trace where available. Define directory naming, attempt identity, retention, capture time limits, and opt-out behavior. Redact application-controlled metadata; explain that raw HTML, screenshots, and traces may still contain page/session data.

### Acceptance criteria
- [ ] A terminal failure produces a discoverable manifest and all artifacts available at that point.
- [ ] Capture failure or browser loss preserves the original error and produces a partial-artifact explanation.
- [ ] Capture and retention are bounded and configurable.
- [ ] CI uploads only controlled demo data; documentation does not imply arbitrary traces are fully sanitized.

---

## B22 — Generate Gauntlet evidence from actual runtime observations

**GitHub:** [#22](https://github.com/bockuden/resilient-browser-automation-python/issues/22)

**Milestone:** M4

**Labels:** `priority:p1`, `type:feature`, `area:evidence`

**Depends on:** [B10 / #10](https://github.com/bockuden/resilient-browser-automation-python/issues/10), [B11 / #11](https://github.com/bockuden/resilient-browser-automation-python/issues/11), [B13 / #13](https://github.com/bockuden/resilient-browser-automation-python/issues/13), [B20 / #20](https://github.com/bockuden/resilient-browser-automation-python/issues/20)

### Goal
Produce portable evidence that describes what the worker actually did.

### Scope
Record observed status sequences, measured retry waits, raw item IDs before deduplication, successful login counts, session expiry, selector fallback, and committed/resumed progress. Map these observations to the stand's evidence schema. Use a separate manifest for producer version and environment metadata if the validator rejects unknown fields.

### Acceptance criteria
- [ ] Evidence is generated during the run and is not copied from expected fixtures.
- [ ] The published stand validator accepts a valid supported live scenario.
- [ ] Tampering with an observed sequence or dataset causes validation failure.
- [ ] Evidence collection observes browser activity without replacing browser extraction with a direct HTTP solution.

---

## B23 — Verify Gauntlet levels 1–5 with live browser evidence

**GitHub:** [#23](https://github.com/bockuden/resilient-browser-automation-python/issues/23)

**Milestone:** M4

**Labels:** `priority:p1`, `type:test`, `area:evidence`

**Depends on:** [B08 / #8](https://github.com/bockuden/resilient-browser-automation-python/issues/8), [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9), [B10 / #10](https://github.com/bockuden/resilient-browser-automation-python/issues/10), [B11 / #11](https://github.com/bockuden/resilient-browser-automation-python/issues/11), [B12 / #12](https://github.com/bockuden/resilient-browser-automation-python/issues/12), [B22 / #22](https://github.com/bockuden/resilient-browser-automation-python/issues/22)

### Goal
Prove pagination, retries, authentication, selector adaptation, and deduplication against the published objectives.

### Scope
Run each level with a fresh run ID, generate evidence, invoke the external validator, and independently inspect persisted results. Derive expected criteria from the pinned challenge contract.

### Acceptance criteria
- [ ] All five levels run through the real browser and pass their exact objectives.
- [ ] Status sequences, login counts, waits, raw IDs, and unique datasets are checked where relevant.
- [ ] Tests inspect actual database values in addition to validating evidence.
- [ ] Each level has one documented reproduction command.

---

## B24 — Verify Gauntlet levels 6–8 with restart and session recovery evidence

**GitHub:** [#24](https://github.com/bockuden/resilient-browser-automation-python/issues/24)

**Milestone:** M4

**Labels:** `priority:p1`, `type:test`, `area:evidence`

**Depends on:** [B09 / #9](https://github.com/bockuden/resilient-browser-automation-python/issues/9), [B10 / #10](https://github.com/bockuden/resilient-browser-automation-python/issues/10), [B13 / #13](https://github.com/bockuden/resilient-browser-automation-python/issues/13), [B14 / #14](https://github.com/bockuden/resilient-browser-automation-python/issues/14), [B22 / #22](https://github.com/bockuden/resilient-browser-automation-python/issues/22)

### Goal
Prove checkpoint continuation, session expiry recovery, and rate-limit handling.

### Scope
Execute the exact level-specific scenarios. Preserve run identity across recovery. Validate continuation behavior using observed requests and committed state. Keep the Gauntlet's scripted failure/recovery scenario distinct from the additional forced-termination test.

### Acceptance criteria
- [ ] Levels 6–8 pass the published validator using newly generated evidence.
- [ ] Already committed pages are not fetched again where the level objective prohibits it.
- [ ] Login counts and actual retry waits satisfy the pinned contract.
- [ ] The final dataset and checkpoint agree with independent database assertions.

---

## B25 — Verify Gauntlet levels 9–10 under composite failures

**GitHub:** [#25](https://github.com/bockuden/resilient-browser-automation-python/issues/25)

**Milestone:** M4

**Labels:** `priority:p1`, `type:test`, `area:evidence`

**Depends on:** [B23 / #23](https://github.com/bockuden/resilient-browser-automation-python/issues/23), [B24 / #24](https://github.com/bockuden/resilient-browser-automation-python/issues/24)

### Goal
Prove that individual recovery mechanisms remain correct when combined.

### Scope
Exercise the published composite event sequences, including transient errors, duplicates, delayed responses, session expiry, and selector changes. Repeat each composite scenario with a fresh run ID and compare normalized results.

### Acceptance criteria
- [ ] Both levels pass the exact external validator objectives.
- [ ] Independent runs produce the same expected dataset and recovery sequence, allowing genuine timing variation.
- [ ] Earlier committed records remain valid after later failures.
- [ ] Failure diagnostics identify the first violated invariant rather than only reporting a timeout.

---

## B26 — Test failure windows around persistence, deadlines, and shutdown

**GitHub:** [#26](https://github.com/bockuden/resilient-browser-automation-python/issues/26)

**Milestone:** M4

**Labels:** `priority:p1`, `type:test`, `area:resilience`

**Depends on:** [B14 / #14](https://github.com/bockuden/resilient-browser-automation-python/issues/14), [B15 / #15](https://github.com/bockuden/resilient-browser-automation-python/issues/15), [B18 / #18](https://github.com/bockuden/resilient-browser-automation-python/issues/18), [B19 / #19](https://github.com/bockuden/resilient-browser-automation-python/issues/19), [B21 / #21](https://github.com/bockuden/resilient-browser-automation-python/issues/21)

### Goal
Test important worker invariants that a target-server challenge cannot establish by itself.

### Scope
Inject failures before and during page commit, after commit but before job finalization, during retry waiting, and during cleanup. Add a bounded database-lock contention case and a simulated write failure. Test actual rollback/state transitions rather than mocking the successful result.

### Acceptance criteria
- [ ] Each selected failure window has an explicit expected durable state.
- [ ] Checkpoints never advance past data committed in the same transaction.
- [ ] Deadlines and cancellation remain bounded under failure.
- [ ] Lost resources or diagnostic failures do not mask the root cause or mark an incomplete job successful.

---

## B27 — Run static checks, browser acceptance, and evidence validation in CI

**GitHub:** [#27](https://github.com/bockuden/resilient-browser-automation-python/issues/27)

**Milestone:** M4

**Labels:** `priority:p1`, `type:infra`, `area:tooling`

**Depends on:** [B08 / #8](https://github.com/bockuden/resilient-browser-automation-python/issues/8), [B23 / #23](https://github.com/bockuden/resilient-browser-automation-python/issues/23), [B24 / #24](https://github.com/bockuden/resilient-browser-automation-python/issues/24), [B25 / #25](https://github.com/bockuden/resilient-browser-automation-python/issues/25), [B26 / #26](https://github.com/bockuden/resilient-browser-automation-python/issues/26)

### Goal
Make the project's guarantees independently reproducible from a commit.

### Scope
Add fast checks, storage/integration tests, real-browser tests against the pinned stand, and Gauntlet validation. Keep expensive platform coverage deliberate: a primary browser platform plus a justified Python compatibility matrix. Save useful reports and bounded failure artifacts.

### Acceptance criteria
- [ ] Pull requests run the required static, unit, integration, and browser checks.
- [ ] All claimed Gauntlet levels generate and validate fresh evidence in CI.
- [ ] Jobs have timeouts, deterministic cleanup, and useful failure reports.
- [ ] Workflow output records the consumer commit and the exact stand/browser environment.

---

## B28 — Publish a C# and Python behavioral compatibility matrix

**GitHub:** [#28](https://github.com/bockuden/resilient-browser-automation-python/issues/28)

**Milestone:** M5

**Labels:** `priority:p1`, `type:docs`, `area:evidence`

**Depends on:** [B27 / #27](https://github.com/bockuden/resilient-browser-automation-python/issues/27)

### Goal
Show which reliability guarantees are demonstrated in each language.

### Scope
Map equivalent scenarios, outcomes, and proof links across pinned C# and Python revisions. Separate ordinary integration coverage, exact Gauntlet evidence, and documented limitations. Do not require adding unimplemented features to the C# repository as part of this issue.

### Acceptance criteria
- [ ] Each claimed capability links to a test or reproducible run at a known revision.
- [ ] Unsupported and unverified behavior is stated explicitly.
- [ ] Equivalent results are compared without demanding identical internal implementation or event counts where contracts differ.
- [ ] The matrix makes no speed or scalability claim without measurements.

---

## B29 — Document architecture, Python design choices, and guarantee boundaries

**GitHub:** [#29](https://github.com/bockuden/resilient-browser-automation-python/issues/29)

**Milestone:** M5

**Labels:** `priority:p1`, `type:docs`, `area:docs`

**Depends on:** [B15 / #15](https://github.com/bockuden/resilient-browser-automation-python/issues/15), [B16 / #16](https://github.com/bockuden/resilient-browser-automation-python/issues/16), [B18 / #18](https://github.com/bockuden/resilient-browser-automation-python/issues/18), [B19 / #19](https://github.com/bockuden/resilient-browser-automation-python/issues/19)

### Goal
Help a technical reviewer understand the decisions that make the worker reliable.

### Scope
Explain resource ownership, module boundaries, async cancellation, retry scope, transaction boundaries, job identity, and continuation semantics. Record a few meaningful tradeoffs, including the single-process SQLite deployment boundary and differences from the C# implementation.

### Acceptance criteria
- [ ] An architecture diagram and execution sequence match the implemented code.
- [ ] The documentation explains why abstractions exist and where simpler functions are sufficient.
- [ ] Guarantees distinguish persisted-result idempotency from repeated network requests and external side effects.
- [ ] Limitations include target-specific selectors, dynamic dataset assumptions, and deployment scope.

---

## B30 — Assemble six executable engineering walkthroughs from the tested worker

**GitHub:** [#30](https://github.com/bockuden/resilient-browser-automation-python/issues/30)

**Milestone:** M5

**Labels:** `priority:p1`, `type:docs`, `area:docs`

**Depends on:** [B27 / #27](https://github.com/bockuden/resilient-browser-automation-python/issues/27), [B29 / #29](https://github.com/bockuden/resilient-browser-automation-python/issues/29)

### Goal
Turn the implementation into a practical explanation of browser automation failure handling.

### Scope
Create short chapters for: (1) readiness and extraction, (2) retries and rate limits, (3) authentication and session recovery, (4) transactions and restart recovery, (5) concurrency and cancellation, and (6) diagnosis and artifacts. Draft each chapter alongside its implementation issue; this issue assembles and verifies the learning path.

### Acceptance criteria
- [ ] Each chapter includes a reproducible failure, the implemented remedy, a verification command, and a limitation or tradeoff.
- [ ] Commands use the shared implementation and pinned environment.
- [ ] Happy-path-only snippets and intentionally fragile snippets are clearly identified.
- [ ] A documented verification script runs the chapter commands and checks their expected success or failure outcomes.

---

## B31 — Create a one-command recovery demo and a short visual walkthrough

**GitHub:** [#31](https://github.com/bockuden/resilient-browser-automation-python/issues/31)

**Milestone:** M5

**Labels:** `priority:p1`, `type:feature`, `area:docs`

**Depends on:** [B14 / #14](https://github.com/bockuden/resilient-browser-automation-python/issues/14), [B21 / #21](https://github.com/bockuden/resilient-browser-automation-python/issues/21), [B25 / #25](https://github.com/bockuden/resilient-browser-automation-python/issues/25)

### Goal
Let a reviewer see the project's value before reading the implementation.

### Scope
Provide a command that prepares the controlled environment, runs a representative failure/recovery scenario, verifies saved output, and prints artifact locations. Record a short video or animation from a real run. State prerequisites and expected setup cost.

### Acceptance criteria
- [ ] A clean checkout can reproduce the demo using the documented prerequisites.
- [ ] Expected failures are reported as part of the scenario, while unexpected failures fail the demo.
- [ ] The final output shows committed progress, resumed work, final record correctness, and evidence paths.
- [ ] The visual walkthrough is tied to a reproducible command and identifies illustrative material if any is used.

---

## B32 — Build verified release artifacts and a reproducible release workflow

**GitHub:** [#32](https://github.com/bockuden/resilient-browser-automation-python/issues/32)

**Milestone:** M5

**Labels:** `priority:p1`, `type:infra`, `area:tooling`

**Depends on:** [B27 / #27](https://github.com/bockuden/resilient-browser-automation-python/issues/27), [B31 / #31](https://github.com/bockuden/resilient-browser-automation-python/issues/31)

### Goal
Deliver the worker as an installable, versioned artifact rather than a checkout-only script.

### Scope
Build wheel and source distribution, verify clean installation, and document browser provisioning. Add a container only if it is used by the chosen demo/deployment path. Prepare release notes and a tag-triggered workflow. A PyPI publication is optional, not a prerequisite for portfolio value.

### Acceptance criteria
- [ ] Built distributions pass metadata checks and install in a clean environment.
- [ ] The installed CLI completes a smoke scenario without relying on repository-relative files.
- [ ] The release workflow runs required checks and attaches reproducible artifacts and version metadata.
- [ ] Publication targets, credentials, and release permissions are documented before the first publication.

---

## B33 — Package the portfolio presentation and publish the first documented release

**GitHub:** [#33](https://github.com/bockuden/resilient-browser-automation-python/issues/33)

**Milestone:** M5

**Labels:** `priority:p1`, `type:docs`, `area:docs`

**Depends on:** [B28 / #28](https://github.com/bockuden/resilient-browser-automation-python/issues/28), [B29 / #29](https://github.com/bockuden/resilient-browser-automation-python/issues/29), [B30 / #30](https://github.com/bockuden/resilient-browser-automation-python/issues/30), [B31 / #31](https://github.com/bockuden/resilient-browser-automation-python/issues/31), [B32 / #32](https://github.com/bockuden/resilient-browser-automation-python/issues/32)

### Goal
Make the project's engineering evidence easy to evaluate for consulting or hiring.

### Scope
Finish the README, repository description/topics, supported-capability table, release notes, and links between the stand, C# consumer, and Python consumer. Prepare a concise GitHub profile entry. Publish the release and profile update when implementation work is explicitly taken through publication.

### Acceptance criteria
- [ ] The first README screen explains the problem, result, and shortest reproduction path.
- [ ] Claims link to actual tests, fresh evidence, or documented limitations.
- [ ] The README has distinct short paths for running the demo, reviewing code, and following walkthroughs.
- [ ] Release notes identify exact tested versions; profile wording reflects demonstrated Python work and accurately stated experience.

---

## B34 — Measure throughput, resource use, and recovery cost under controlled workloads

**GitHub:** [#34](https://github.com/bockuden/resilient-browser-automation-python/issues/34)

**Milestone:** M6

**Labels:** `priority:p2`, `type:research`, `area:evidence`

**Depends on:** [B27 / #27](https://github.com/bockuden/resilient-browser-automation-python/issues/27)

### Goal
Add measured performance evidence only after correctness is established.

### Scope
Benchmark fixed workloads at several concurrency settings, with and without controlled failures. Separate browser startup cost from steady execution. Record machine details, versions, repetitions, success rate, timing distribution, and resource measurement method. Compare C# only under equivalent work and environment.

### Acceptance criteria
- [ ] Benchmarks are reproducible and retain their raw measurements.
- [ ] Timing and resource figures identify what is included, including browser processes where relevant.
- [ ] Failed or incomplete runs remain visible rather than disappearing from results.
- [ ] Conclusions stay within the tested workload and do not imply general production scalability.

---

## B35 — Add a second controlled target adapter to test architectural portability

**GitHub:** [#35](https://github.com/bockuden/resilient-browser-automation-python/issues/35)

**Milestone:** M6

**Labels:** `priority:p2`, `type:feature`, `area:browser`

**Depends on:** [B27 / #27](https://github.com/bockuden/resilient-browser-automation-python/issues/27), [B29 / #29](https://github.com/bockuden/resilient-browser-automation-python/issues/29)

### Goal
Demonstrate that the runner is reusable beyond one purpose-built catalog.

### Scope
Use a second local target with meaningfully different DOM or pagination behavior, such as cursor-based navigation or load-more interaction. Reuse storage, retries, cancellation, and diagnostics. Keep network dependence on uncontrolled third-party websites out of acceptance tests.

### Acceptance criteria
- [ ] A second adapter produces a verified dataset through a real browser.
- [ ] Target-specific branching remains outside the generic runner.
- [ ] Continuation semantics and limitations are documented for this target.
- [ ] At least one failure/recovery case demonstrates reuse of the existing infrastructure.

---

## B36 — Add an explicit HTTP-versus-browser tradeoff case study

**GitHub:** [#36](https://github.com/bockuden/resilient-browser-automation-python/issues/36)

**Milestone:** M6

**Labels:** `priority:p2`, `type:research`, `area:docs`

**Depends on:** [B27 / #27](https://github.com/bockuden/resilient-browser-automation-python/issues/27), [B29 / #29](https://github.com/bockuden/resilient-browser-automation-python/issues/29)

### Goal
Show engineering judgment about when browser automation is warranted.

### Scope
Implement one small, explicit HTTP extraction path against a controlled endpoint and compare it with browser interaction for the same permitted dataset. Explain authentication, observable UI behavior, maintenance, and execution cost. Keep HTTP and browser modes separately named and tested.

### Acceptance criteria
- [ ] Both paths validate their final data using the same applicable dataset contract.
- [ ] Browser-only objectives remain verified through browser execution.
- [ ] The explanation states when the simpler HTTP path is sufficient and when browser behavior is part of the requirement.
- [ ] Any performance comparison includes reproducible measurements and its limitations.

## Suggested first work sequence

1. B01 → B02 and B03 → B04 → B05; implement B06 once B03 is stable.
2. B07 → B08 produces the first complete runnable slice.
3. B09 → B13 → B14 → B15 produces the first strong recovery demo.
4. Complete B10–B12, then work through M3 and M4 by dependency readiness.
5. Draft documentation during implementation; assemble M5 after the evidence is stable.
6. Select M6 extensions only if they strengthen the intended portfolio story.

The optional milestone is not a requirement for declaring the initial project finished.
