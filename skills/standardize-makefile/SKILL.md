---
name: standardize-makefile
description: >-
  Create or refactor a project's Makefile around make help, make dev, make init,
  and make test. Use when the user wants consistent development setup, a confirmed
  local reset, and frontend/backend test entry points adapted to the project's
  actual dependencies. This standardizes project commands without changing its
  application stack or replacing file-based build rules.
---

# Standardize Makefile

Give an existing project four predictable entry points. Keep the Makefile thin;
reuse or adapt its scripts, package-manager commands, and test runners. Standardize
observable behavior without importing another project's framework, directory layout,
database, runtime versions, ports, or specialized services.

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
- Existing Make targets, script callers, CI entry points, and documented commands
  that need to keep working.

State the resulting command mapping briefly before implementation. Resolve ordinary
choices from the repository. Clarify only consequential ambiguity, such as a database
that appears optional in the manifest but is required by the application at startup.
Do not add PostgreSQL, Redis, Docker, a worker, or a test framework just to fill a template.

## Command contract

| Command | Required behavior |
| --- | --- |
| `make` / `make help` | Show available commands, relevant options, and where to find setup details; no preparation or service startup. |
| `make dev` | Prepare missing required dependencies, preserve local configuration and data, and launch the project's development services with supported hot reload. |
| `make init` | Preview and confirm a reset of this checkout's ignored local state, rebuild the development environment, then exit without leaving the app running. |
| `make test` | Run all existing frontend and backend test suites in non-watch mode, with isolated mutable state and a reliable aggregate result. |

Set `.DEFAULT_GOAL := help` and mark these command targets `.PHONY`. Preserve existing
file-based build rules and useful project-specific targets. Keep lint, build, deployment,
scoring, and specialized acceptance commands where they already belong; do not add
them as mandatory parts of this standard. Preserve existing test gates unless the
user authorizes changing them.

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

Update existing setup documentation with the four commands, prerequisites, supported
options, reset scope, and test report location. Keep durable behavior there and
one-off implementation notes outside tracked docs. Follow the repository's testing
and approval rules. Remove replaced helpers only after checking their live callers;
do not remove unrelated targets or tests.

Run `make help` and check changed scripts with the project's existing tooling. Exercise
startup, readiness, shutdown, and test orchestration in an isolated disposable checkout
or fixture with synthetic configuration. Verify that a failure in either test suite
fails the top-level command. Exercise reset cancellation and confirmed deletion only
against disposable data; preserve the user's live environment. A dry run alone does
not demonstrate process cleanup or reset safety. If runtime prerequisites prevent a
check, state the unverified behavior rather than claiming it passed.

Report the command mapping, the services detected or omitted, validation performed,
and any remaining prerequisites. Keep implementation proportional to the project;
a frontend-only app should not inherit a backend process supervisor or database runner.
