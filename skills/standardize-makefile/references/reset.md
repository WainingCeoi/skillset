# Confirmed local reset

`make init` means reset and rebuild, including when a development environment already
exists. First-time setup is also supported by `make dev`; `init` is never an automatic
dependency of `dev` or `test`.

## Scope and preview

Use the checkout's effective Git ignore rules, including local/global exclusions, to
inventory ignored local state. This can include configuration, dependency environments,
build output, database clusters and workspace databases, uploaded files, integration
sessions, AI settings, ignored notes, and editor settings. Show the actual affected
paths and data categories; do not describe this as merely clearing a build cache.

Preserve tracked files and their modifications, ordinary untracked non-ignored files,
and the current checkout's Git metadata, history, and branches. Never delete a parent
directory containing protected content. When an ignored directory contains tracked
files, preserve those files and their ancestors while planning individual ignored
siblings for deletion. Stop only if a safe boundary cannot be established or preserved
content prevents rebuilding; do not expand the reset's scope. For a non-Git project,
establish and document an explicit local reset inventory with the user before
implementing deletion.

Treat nested repositories and worktrees inside the proposed scope separately. Present
delete, skip, and cancel choices before final confirmation; skipping must protect
their ancestors from recursive deletion. If a skipped path prevents rebuilding the
environment, stop before deleting anything and explain the conflict.

The reset must stay within the selected checkout and verified checkout-owned local
resources. Do not traverse symlinks into external directories. Never prune shared
Docker volumes, reset global databases, remove another checkout's state, or treat an
inherited connection URL as ownership proof. For external local storage used by the
project, establish its exact ownership and approved reset scope separately; do not
silently include it in the ignored-file sweep.

## Confirm and execute

Before deleting anything:

1. Acquire a checkout-scoped lock shared with `dev`. Check for running consumers,
   including workers and manually launched processes; ask the operator to stop them.
2. Check prerequisite tools, configuration templates, data ownership, and compatibility
   without resetting data. The reset planner must run outside directories it will
   delete, including its interpreter and dependencies.
3. Present the concrete deletion plan, nested-repository choices, and a clear statement
   that local configuration and data in that plan will be lost. Require explicit final
   confirmation, such as typing `reset`. Cancellation, EOF, and unattended input must
   leave data unchanged. Do not add a blanket `--yes` bypass to this workflow.
4. Revalidate the approved paths, filesystem identities, protected content, and service
   state immediately before deletion. Refuse a changed or uncertain plan; newly found
   content must not be swept into an earlier approval.
5. Stop only the verified local data services whose state will be reset. Abort if
   ownership or shutdown cannot be verified. Delete only the approved scope.

Reuse established cleanup mechanisms where they provide these guarantees. A bare
`git clean -fdx`, `git reset --hard`, or recursive delete is not the reset planner.
Do not copy Git-ignored secrets into a tracked backup as a reset precaution.

## Rebuild and exit

Recreate missing local configuration from templates, prepare the pinned dependencies
through the shared development setup path, and initialize/migrate only required
local stores. A project without a database skips database setup completely. Preserve
existing migration files; this command rebuilds local state, not migration history.

Stop data services started for reconstruction and exit with a clear `make dev` next
step. Do not leave frontend, API, or worker processes running. On failure, report the
failed stage, propagate a nonzero status, and clean up owned processes; do not imply
deleted data was restored or silently broaden the deletion plan on retry.
