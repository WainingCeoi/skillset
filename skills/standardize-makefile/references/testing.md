# Frontend and backend test entry point

## Suite selection and preparation

With no filters, `make test` runs all existing frontend and backend test suites once
in non-watch mode. Discover native commands from manifests, fixtures, and CI. Respect
existing test gates; do not replace behavioral tests with a build or lint command.
Do not introduce a new test framework or E2E suite merely to standardize the entry point.

For a genuinely absent layer or a layer with no existing suite, report that absence
clearly. Do not invent tests to populate the command. An expected suite that cannot
be discovered, collects zero selected tests, or lacks required dependencies is a
failure, not a successful skip. If no tests exist anywhere, report that fact and return
nonzero rather than asserting the project passed.

Use already prepared dependencies and pinned tool versions. Fail with actionable
preparation instructions if they are missing; tests must not silently install packages
or download models. Point to the documented setup path or `make dev`, not the destructive
`make init`, as the preparation route.

If exposing selectors, route frontend and backend arguments independently, for example
`FRONTEND_TEST_ARGS` and `BACKEND_TEST_ARGS`. Document quoting and partial-suite output;
do not forward pytest options to a different runner or silently skip the other layer.
Preserve compatible existing selector names where useful. Avoid shell `eval` of supplied
arguments; use the runner's native argument interface.

## Isolate mutable state

Each invocation has a private run directory. Establish isolation before application
imports or configuration loading can capture inherited settings. Give concurrent
workers distinct databases or equivalent storage, output paths, caches, and ports as
needed; never share mutable fixtures with development or production.

Start database services only for suites that actually use them. PostgreSQL integration
tests use real isolated PostgreSQL, with temporary clusters or an existing equivalently
isolated fixture, created lazily when practical. Reuse the project's configured database
type and shared test helpers; do not substitute SQLite or mock database behavior to make
integration tests easier. A SQLite project can isolate files; a database-free project
requires no database provisioning at all.

Override inherited connection URLs and production/tenant paths before tests load the
app. Use synthetic accounts and data. Keep external paid calls, company email, and
production integrations out of ordinary `make test`; reuse fake external boundaries
and keep explicitly authorized live-integration tests behind their existing opt-in path.

## Concurrency and completeness

Prefer the native runner's scheduling and result accounting. Where the runner supports
safe parallelism, expose `TEST_WORKERS=auto|N|0`: `auto` uses available CPU and memory,
positive `N` requests that count in capable suites, and `0` forces serial execution
across all suites. An inherently serial suite stays serial and reports that fact;
do not shard it just because another suite supports parallelism. Help must identify
the suites controlled by this option. If none supports safe parallelism, document
`auto`, `0`, and `1` as serial and reject values greater than one. Reject invalid
values without adding a framework or pretending unsupported parallelism works.

Choose resource reserves and per-worker budgets from the project's workload. Account
for container limits when applicable. Do not copy another project's fixed GiB values
or start frontend and backend pools that each consume the machine's entire budget;
running the suites sequentially is a reasonable default. For an owned resource-budgeted
runner, monitor the reserve and fail cleanly if it is breached or cannot be measured.

Schedule tests that cannot safely run concurrently in a serial phase without dropping
them. If adding custom worker/shard orchestration, reconcile collected test identities
with results: each selected test must produce exactly one terminal outcome under the
runner's retry policy. Missing, duplicate, or corrupt results, collection errors, and
worker crashes must fail the invocation. Reuse native reports when they already provide
this guarantee; do not build a second reporting framework for a simple serial runner.

## Exit status, cleanup, and evidence

Attempt both suites when feasible, even if one reports test failures, then aggregate
their outcomes. An interruption or unsafe shared prerequisite can stop the run, but
must not be reported as success. Do not allow a later successful suite to overwrite an
earlier failure. Tests, runner errors, and failure to stop owned data services all make
the top-level command return nonzero.

Handle normal completion, failure, and Ctrl+C by stopping and reaping owned processes
and databases only. Do not stop another developer's server by port or process name.
Preserve failure logs and useful diagnostics in a Git-ignored or temporary run directory;
print the location and a concise per-suite summary. Preserve existing CI report formats
and shared entry points where possible, without importing an unrelated CI sharding,
Docker, or deployment system.
