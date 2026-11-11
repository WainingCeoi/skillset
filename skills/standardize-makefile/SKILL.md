---
name: standardize-makefile
description: >-
  Consolidate an existing project's Make commands into exactly four public entry
  points: make help, make dev, make init, and make test. Use when the user wants
  existing setup, startup, reset, and test behavior unified around the project's
  actual dependencies. Reuse existing implementations, retire superseded commands,
  and add only missing behavior; do not change the application stack.
---

# Standardize Makefile

Consolidate the project's existing command surface into **exactly `help`, `dev`,
`init`, and `test`**. Reuse compliant behavior, adapt partial implementations, and
add code only for missing behavior. Keep the Makefile thin and retain its useful
scripts, package-manager commands, and test runners. Do not import another project's
framework, directory layout, database, runtime versions, ports, or specialized services.

## Discover the project

Read repository instructions, the current Makefile, dependency manifests and lockfiles,
runtime pins, environment templates, development scripts, test fixtures, CI, and setup
documentation. Inspect actual callers and configuration rather than inferring the
architecture from directory names or an installed database driver alone.

Identify:

- Which frontend, backend, workers, and supporting services the app actually runs.
- Which dependencies are required for normal development versus optional features.
- Which databases or other persistent stores are used, where local data lives, and
  which settings can redirect the app to shared or production resources.
- How each existing test suite runs, what state it mutates, and whether its runner
  already provides isolation, concurrency limits, reports, and cleanup.
- Existing Make targets and their behavior, plus script, CI, and documentation callers
  that must migrate to the consolidated interface.

Classify each core behavior as compliant, partial, or missing. State an old-to-new
command mapping before implementation, including which targets will be removed and
how their callers move. Do not build a parallel implementation of behavior the project
already provides. Resolve ordinary choices from the repository. Clarify only
consequential ambiguity, such as a database that appears optional in the manifest
but is required by the application at startup.
Do not add PostgreSQL, Redis, Docker, a worker, or a test framework just to fill a template.

## Command contract

| Command | Required behavior |
| --- | --- |
| `make` / `make help` | Show available commands, relevant options, and where to find setup details; no preparation or service startup. |
| `make dev` | Prepare missing required dependencies, preserve local configuration and data, and launch the project's development services with supported hot reload. |
| `make init` | Preview and confirm a reset of this checkout's ignored local state, rebuild the development environment, then exit without leaving the app running. |
| `make test` | Run all existing frontend and backend test suites in non-watch mode, with isolated mutable state and a reliable aggregate result. |

Set `.DEFAULT_GOAL := help` and mark these four command targets `.PHONY`. Remove
superseded public targets and compatibility aliases after migrating their callers;
hiding them from help does not complete consolidation. Do not retain an `all`,
`install`, `test-backend`, or other public Make command alongside the four. Genuine
file-based build dependencies may remain internal implementation rules.

Map existing behavior by purpose:

- Dependency installation becomes shared preparation used by `dev` and `init`.
- Development launch commands become `dev`, reusing the existing service startup code.
- Existing lint/build gates remain part of `test` when already required there.
- Single-suite testing uses an explicit option such as `make test TEST_SUITE=backend`,
  with all existing suites as the default; do not keep separate Make targets.
- Consolidate cleanup into `init` and remove separate `clean` targets and aliases.
  Reuse cleanup internals within the confirmed reset contract, making its full
  configuration and local-data scope explicit.

Keep specialized production, deployment, scoring, or acceptance capabilities available
through documented native tools or scripts when still needed. Do not add extra Make
targets for them or force their side effects into `dev` or `test`. Do not introduce
one mode or wrapper for every retired target merely to reproduce the old interface.
Preserve existing test gates unless the user authorizes changing them.

Help must describe `init` as a destructive local reset, not a prerequisite for first
use. Advertise only supported options and services. Use overrideable defaults such as
`PORT ?= ...` where relevant; keep proxy/origin configuration in sync with selected
ports. If recipes require Bash, select it explicitly and respect the project's supported
OS and installed shell version.

## Implement development startup

Make `dev` work on first setup and subsequent runs through the same path. Preserve
existing `.env` files and data; create missing local configuration from maintained
templates without inventing secrets. Respect lockfiles and runtime/package-manager
pins. Prepare missing required tools and synchronize dependencies before launching
services, reusing a valid prepared environment where possible. Do not silently update
dependency versions or the user's global toolchain. Explain any required system-package
installation and use the environment's normal permission mechanism.

Start only services identified during discovery. A project without PostgreSQL must
not acquire a PostgreSQL install, cluster, startup probe, or migration step. Apply the
same rule to other databases, queues, workers, and optional readers. For a required
database, use the project's isolated local development instance and existing migration
tool. Ignore inherited production connection settings; never migrate an unverified
remote/shared database as part of this command. A configured optional service need not
be launched when the selected development mode does not use it.

Supervise the app as one foreground session:

- Detect incompatible runtime/data versions and occupied ports before mutating data;
  report conflicts rather than terminating an unknown listener.
- Start dependencies before their consumers. Verify readiness before printing usable
  URLs; show API documentation only if the application provides it.
- Enable the project's existing frontend/backend reload mechanisms and worker reload
  when supported. Do not invent a worker or replace the framework to provide reload.
- On Ctrl+C, startup failure, or unexpected service exit, stop and reap the session's
  processes, including reload children. Propagate failures. Track process ownership;
  do not kill by broad process name or port. Preserve pre-existing verified local
  services that this session did not start and retain development data.
- Serialize conflicting `dev` and `init` operations for the checkout, including when
  invoked through `make -j`; Make prerequisite order alone is not a session lock.

Share dependency preparation between `dev` and `init`. Never implement `dev: init`.

## Implement reset and tests

Read [references/reset.md](references/reset.md) when implementing `init`; its deletion
scope, concrete confirmation, and ownership checks are part of the command contract.
Creating this command does not authorize executing a reset of the user's checkout.

Read [references/testing.md](references/testing.md) when implementing `test`. Reuse
the existing test infrastructure; add only the orchestration needed to meet its
isolation, resource, and failure-reporting requirements.

## Integrate and verify

Migrate CI, scripts, setup instructions, and code comments to the four-command
interface or the retained native procedures. Remove superseded targets, aliases,
duplicate orchestration, and helpers whose last live caller was removed; search again
for stale references. Keep useful underlying implementations and their tests when
they still have callers. Follow the repository's testing and approval rules.

Update existing setup documentation with the four commands, prerequisites, supported
options, reset scope, and test report location. Keep durable behavior there and
one-off implementation notes outside tracked docs.

Verify the actual public Make command set is exactly the four core commands, not just
the displayed help list. Check that migrated CI and script callers use live commands.
Run `make help` and check changed scripts with the project's existing tooling. Exercise
startup, readiness, shutdown, and test orchestration in an isolated disposable checkout
or fixture with synthetic configuration. Verify that a failure in either test suite
fails the top-level command. Exercise reset cancellation and confirmed deletion only
against disposable data; preserve the user's live environment. A dry run alone does
not demonstrate process cleanup or reset safety. If runtime prerequisites prevent a
check, state the unverified behavior rather than claiming it passed.

Report the old-to-new mapping, targets merged or removed, implementations reused,
services detected or omitted, validation performed, and remaining prerequisites.
Keep implementation proportional to the project; a frontend-only app should not
inherit a backend process supervisor or database runner.
