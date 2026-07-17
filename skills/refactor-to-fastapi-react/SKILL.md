---
name: refactor-to-fastapi-react
description: >-
  Refactor a Python app that mixes UI and logic — Streamlit, Gradio, Flask+templates, a
  Tkinter/CLI tool, or any monolith — into a clean FastAPI backend + React (Vite) frontend
  monorepo, with a one-command Makefile entrance and an optional one-command LAN host. Use
  this whenever the user wants to "add a real frontend/backend", "get off Streamlit", "split
  this into backend and frontend", "give this a proper web API and UI", "make a REST/JSON API
  for this", "serve this to my phone / other devices on the Wi-Fi", or "productionize" a
  script-shaped app — even if they don't say "FastAPI" or "React" by name. Also triggers for
  "app factory", "SSE streaming endpoint", "single-origin deploy", or "universal make dev"
  requests in a Python web context. It carries battle-tested scaffold templates and a
  discover-before-you-change workflow, so prefer it over hand-rolling the conversion.
---

# Refactor a Python app to a FastAPI + React monorepo

The job is to take an app where the UI and the logic are tangled together — the classic
Streamlit/Gradio shape where a button callback also does the database write — and pull them
apart into two clean halves that talk over a small HTTP + Server-Sent-Events API, wrapped in a
monorepo that runs with one command.

The single most important principle: **the domain logic (the "engine") should survive the
refactor almost untouched.** The value of the app is in that code; the UI framework is
disposable. So the goal is to *lift the engine out intact*, put a thin FastAPI layer in front
of it, and redesign the UI in React — not to rewrite the engine. If you find yourself editing
core algorithm code to make the web layer work, stop: that's a design smell, and the seam is
in the wrong place.

Work the way a careful engineer would: **discover before you change, and verify by observing
real behavior — never claim success from a dry run.** A refactor that "looks done" but was
never booted is not done.

## The target shape

```
project/
├── Makefile              # one entrance: install / dev / start / host / build / test / clean
├── README.md             # comprehensive: quick start, architecture, API table, config
├── .gitignore
├── backend/              # FastAPI service + the lifted engine (src layout)
│   ├── pyproject.toml
│   ├── .env.example
│   ├── .gitignore
│   └── src/
│       ├── <engine>/     # the domain logic, lifted in ~verbatim (its own package)
│       └── <app>_api/    # the thin web layer: main.py, deps.py, schemas.py, routers/
└── frontend/             # React + Vite single-page app
    ├── package.json
    ├── vite.config.js    # dev-proxies /api → backend, so calls are same-origin
    └── src/              # api.js (fetch + SSE wrapper) + components
```

`assets/` in this skill holds drop-in versions of every non-obvious file — the **Bundled
resources** table below maps each one to the phase that needs it. **Copy them and adapt the
placeholders**
rather than writing from a blank page — they encode fixes for mistakes that are easy to
rediscover the hard way (Vite binding IPv6-only, `uv run` rewriting the lockfile, the SSE
threadpool trap, the single-worker requirement). Read `assets/README.md` for the placeholder
map.

## Version control

A refactor touches many files, so keep the work isolated, reviewable, and in the user's hands
to land. This is the default workflow — follow it unless the user says otherwise:

- **Branch first.** Before any edits, create a new branch off the current one (e.g.
  `refactor/fastapi-react`) and do all the work there. Never commit the refactor onto the
  default branch — the first action of Phase 1 is creating the branch.
- **Commit per phase.** As each phase completes *and verifies*, commit just that phase's files
  with a clear, conventional-style message. Small, phase-sized commits make the conversion easy
  to follow and cheap to revert if a step goes wrong.
- **Trailer-free messages.** Plain subject + body only — **no `Co-Authored-By`, no "Generated
  with …", no co-contributor or attribution trailer of any kind.** Just describe the change.
- **Stop at commit — the user pushes and merges.** Do NOT push, and do NOT merge to the default
  branch. Leave the branch in place for the user to review, push, and merge back when they're
  ready. That decision is theirs, not the skill's.

Example messages:
`feat(backend): app factory + lifespan building one engine on app.state`
`style(engine): ruff --fix on the lifted engine (no behavior change)`

## Phases

Do these in order. Each builds on the last, and several early decisions (where the engine seam
is, what streams) determine later structure. Commit at each phase boundary once it verifies, per
**Version control** above — the gates are judged at the boundary, not at every commit inside it.

### Phase 0 — Discover (read only; report before editing)

You cannot design the API until you know the shape of what exists. Produce a short written
map, then proceed. See `references/discovery-checklist.md` for the full checklist; the
essentials:

- **Entrypoints & launch**: how is it started today, what host:port does it bind, what's the
  package manager (uv / poetry / pip / npm / pnpm)? Note that some managers (e.g. `uv run`)
  rewrite the lockfile as a side effect of *running* — plan to use `--frozen`.
- **The engine ↔ UI seam**: which modules are pure logic (importable, no UI imports) vs. which
  are view/callback code? The pure logic is what you lift. If logic and `st.*`/`gr.*` calls are
  interleaved in one function, your first real task is to extract the logic into a plain
  function the UI merely calls.
- **State**: what's held in memory between interactions (caches, a loaded model, a DB handle,
  session state)? In FastAPI this becomes one object built at startup and shared on
  `app.state` — see Phase 2.
- **Long-running / streaming operations**: anything that shows a progress bar, streams tokens,
  or takes many seconds. These need SSE (Phase 3) and drive whether the app must stay
  single-worker.
- **Config / secrets**: grep for every env var the *code actually reads* (don't trust the
  `.env` template). Flag real secrets/signing keys/passwords — they matter for Phase 6.
- **Data / database**: does the app persist anything (a SQL/NoSQL DB, a vector store, files on
  disk)? Note where it lives and whether it looks empty, like a throwaway sample, or like real
  data. How to *handle* it is a user decision, not one to assume — see below.

> **Ask the user how to handle existing data — never decide it yourself.** Projects differ, so
> classify the data *with the user* and act only on their answer:
> - **(a) No database** — nothing to carry over.
> - **(b) Disposable sample/test database** — safe to delete and recreate fresh in the new
>   layout, but confirm first ("current DB is just sample, you can delete it" is the kind of
>   explicit go-ahead to wait for).
> - **(c) Production database with real data** — **never delete it.** Plan an import/migration
>   into the new backend's store as an explicit step, and verify the data survived (row/document
>   counts + spot checks) before considering the refactor done. A stale comment or filename
>   calling a store "test data" is not permission to drop it — the user's explicit answer is.

### Phase 1 — Scaffold the monorepo

**First create the working branch** (e.g. `refactor/fastapi-react`) off the current branch — all
subsequent phases commit onto it. Then create `backend/` and `frontend/` and the backend **src
layout**.

**Three `.gitignore`s, nothing duplicated between them** (templates: `assets/gitignore`,
`assets/backend/gitignore`, `assets/frontend/gitignore`). The root file gets only what belongs to
no sub-project — `.DS_Store`, editor state, `.claude/`. Each sub-project ignores its own caches:
`backend/` takes `.venv`/`__pycache__`/`.env`/`data/`, `frontend/` takes `node_modules`/`dist`.
Git reads the nearest `.gitignore`, so a `backend/.venv/` line at the root covers nothing the
sub-project file misses — it just rots on the first rename and splits one answer across two
files. (Docs go the other way — **one** comprehensive project-root `README.md`, from
`assets/README-template.md`: quick start, the `make` commands incl. `make host`, architecture,
config, the single test command. **Don't scatter docs across per-sub-project READMEs** unless one
genuinely needs its own. The asymmetry is real: git resolves ignores bottom-up from the file
being checked, so scoping them helps; a human reads docs top-down and wants one place.)

Use the `pyproject.toml` block from `assets/backend/pyproject-snippet.toml`: `sources = ["src"]`
strips the `src/` prefix so the engine and API install at the wheel root and import cleanly. Lift
the engine package into `backend/src/<engine>/` **unchanged** — same module names, same internal
imports — so existing `from <engine> import X` lines keep working verbatim. A top-level `config`
module can stay a module (not a package) if the engine imports it as `from config import ...`.
Commit that lift with **zero content edits** — `git diff -M` then shows pure renames, so the
reviewer confirms the engine is intact without reading it. Lint fixes come next, separately
(Phase 2); folding them in here is how a real change hides inside a 40-file diff.

### Phase 2 — Backend: app factory, lifespan, DI

Build the web layer in `backend/src/<app>_api/`. Use `assets/backend/main.py` as the skeleton.
Key patterns (rationale in `references/backend-architecture.md`):

- **App factory** `create_app(engine=None)` returning a `FastAPI` — the `engine=None` param
  lets tests inject a fake and skip the heavy real build.
- **Lifespan** builds the one heavy engine object once and stashes it on `app.state`; a single
  shared instance for the whole process (these apps are single-user / on-device). Warm
  expensive resources (models) here, in a background thread if they're slow, so the first real
  request isn't the one that pays for it.
- **Dependency injection**: `get_engine`/`get_settings` read off `app.state` so routers stay
  thin and testable.
- **Routers under `/api`**, one module per resource, with **Pydantic schemas** for every
  request/response. This is the contract the frontend codes against.
- **CORS** allowing the Vite dev origin (`http://localhost:5173`), overridable by env. In
  single-origin production the UI is same-origin so CORS isn't exercised — but you need it in
  dev.
- **Tests**: put backend tests under `backend/tests/` and configure `testpaths` so the whole
  suite runs with **one command, `uv run pytest`** (no per-package invocations). Exercise the app
  through `create_app(engine=<fake>)` with an injected fake engine — fast, no models, no network.
- **Lint gate — PEP 8 and `ruff check`-clean, zero errors.** Defined by the snippet's
  `[tool.ruff]` block (ruff a *declared* dev dep, `preview = true`); run from `backend/` as
  `uv run ruff check src tests`, and part of `make test`. New code in `<app>_api/` has no excuse:
  fix every finding. The lifted engine is the hard case — read `references/python-style.md`
  before running `--fix` on it. The short version: **the engine's tests are the oracle, not your
  sense of which fixes "look mechanical"** — ruff's *safe* `--fix` silently deletes side-effect
  imports (that unused-looking `from models import User` registers a table) and rewrites
  expressions inside your algorithm. So: `--fix`, then run the engine's tests. Green, keep. Red,
  revert and declare the code in `per-file-ignores` for `src/<engine>/**` — named codes, with
  reasons: a **ledger of inherited debt**, never a family, never `ALL`, never for `<app>_api/**`.
  No engine tests → don't `--fix` the engine; a refactor is not where you acquire coverage.

### Phase 3 — Streaming (SSE), if anything streams

This is the part that's easy to get subtly wrong; read `references/sse-streaming.md` before
writing streaming endpoints. The short version:

- **Token/answer streaming (POST)**: a browser `EventSource` can't POST, so the frontend reads
  a `fetch` stream manually. On the server, if the underlying work is a *blocking* call (most
  LLM/DB SDKs are), emit from a **synchronous generator** returned via Starlette's
  `StreamingResponse` — Starlette runs a sync generator in a threadpool, so the blocking call
  doesn't stall the event loop. An `async def` generator that makes a blocking call *will*
  freeze the whole server. This is the trap.
- **Progress streaming (GET)**: use `EventSource` on the frontend and an async generator
  (e.g. `sse_starlette.EventSourceResponse`) that polls a job's snapshot on the server.
- Frame events explicitly (`event: token` / `event: done` / `event: error` with `data:` JSON)
  and make the frontend parser break only after reading a terminal event's `data:`.

### Phase 4 — Frontend: React + Vite SPA

Scaffold Vite (`assets/frontend/vite.config.js` proxies `/api` → backend so dev calls are
same-origin and SSE needs no CORS). Centralize all HTTP in one `api.js`
(`assets/frontend/api.js`) that wraps every endpoint and provides the SSE reader — components
never call `fetch` directly. Default to plain JS unless the project already uses TypeScript.
**The UI is a redesign, not a port.** Refer to the old screen freely — it's the source of
requirements — but the old *layout* carries no design information: one top-to-bottom column,
`st.sidebar`, `st.expander`, a full-page rerun on every change is what the Streamlit execution
model *permits*, not what anyone chose. Transliterate it and you inherit every constraint while
abandoning the reason you left. Design around the primary action Phase 0 named; read
`references/frontend-redesign.md` before writing components for the old-idiom→React translation
table. Two checks, and a port fails the first:

- **The delta list.** Name three things the React UI does that the Streamlit model structurally
  could not, and point at the code: state surviving an interaction without a rerun; a region that
  loads or fails independently; a deep-linkable view; tokens appended to the DOM without a
  redraw; a keyboard path to the primary action. Fewer than three and you ported it.
- **The parity inventory.** Phase 0's capability list is the contract — layout is discarded,
  features are not. Say where each item now lives. A port passes this trivially; it catches the
  opposite failure, "redesign" as a euphemism for dropping what you didn't rebuild.

Carry the old app's **brand** forward — theme colors, page title, favicon, logo (Phase 0 found
them): that config is the one part of the old UI a human actually chose, and the Vite default
palette titled "Vite + React" is a downgrade, not a redesign. Visual direction beyond that is the
**`frontend-design` skill's** call — use it, and don't gold-plate past a layout that runs and
works at 390px wide.

### Phase 5 — Universal entrance (Makefile)

Copy `assets/Makefile`. It gives one entrance for everything:

- `make dev` — both servers with one Ctrl-C; Vite HMR proxying `/api` to a hot-reload backend
  on loopback. **Never expose this dev server on the LAN.**
- `make start` — build the frontend, then serve UI + API from **one** process (single-origin),
  loopback.
- `make install` / `make build` / `make test` / `make clean`.

Makefile gotchas: recipe lines need **TAB** indentation, and a trailing `# comment` after
`VAR = value` captures the whitespace into the value — put such comments on their own line.

### Phase 6 — LAN host (one command, bound to the network)

Copy `assets/backend/host.py` and add the `host` target (already in `assets/Makefile`). It
builds the UI, then serves API + UI from one process bound to `0.0.0.0` so every device on the
Wi-Fi can reach it — reading the machine's **own mDNS name** at runtime (never hardcoded) and
printing `http://<name>.local:<port>`, auto-advancing past a busy port, and running **one
worker**. Full rationale in `references/lan-host.md`. Two things that must carry through:

- **One worker, always**, if the app has any of: a big in-memory model, an in-process cache, a
  single-active-job registry, or boot migrations. Never enable `--workers >1` for these apps;
  `references/backend-architecture.md` has the why.
- **Security — 0.0.0.0 is not localhost.** Surface it loudly (the template's banner does):
  binding to the LAN exposes the app to everyone on the network. If the app has auth, its
  secret/admin password must be real before exposing. **Cookie foot-gun**: if the framework
  sets a `Secure` (HTTPS-only) session cookie in "production" mode and you serve plain HTTP, the
  browser silently drops it and login won't stick — never enable production/HTTPS-cookie mode for
  a plain-HTTP LAN host. If the app has no auth at all, say so — unauthenticated access, not a
  cookie, is then the real risk. Don't add HTTPS/PWA unless asked (`references/lan-host.md`
  explains both). Keep a `HOST=127.0.0.1` override for local-only.

### Phase 7 — Verify by observation

Prove it works by booting it the way each command does and watching real behavior — not by
asserting it should work:

- `make dev`: both servers up, UI loads, an API call round-trips, streaming streams.
- `make start`: build first (a bare run 404s with no `dist`), then one process serves UI + API
  same-origin on loopback.
- `make host`: `lsof -iTCP:<port> -sTCP:LISTEN` shows `*:<port>` (0.0.0.0), not 127.0.0.1;
  `curl` the LAN IP **and** `<name>.local` → 2xx; occupy the base port and confirm it advances.
- `uv run ruff check src tests` (from `backend/`): zero errors. **`All checks passed!` is not
  evidence on its own** — ruff prints it and exits 0 even when it linted *zero files*, and the
  `warning: No Python files found` goes to stderr, where a stdout capture loses it. Prove the
  gate fires: add `import os` to a file, watch F401 fail it, undo.
- Run the whole test suite with the single command the README documents — **`uv run pytest`**
  (all backend tests live under `backend/tests/`, so one invocation collects them). Then
  `git status`: confirm the package manager didn't rewrite `pyproject`/lockfiles as a side effect
  (use `uv run --frozen`); restore them if it did.

## Anti-patterns

- Rewriting the engine instead of lifting it. Editing algorithm code to satisfy the web layer.
- Putting logic in routers instead of in the engine behind a thin router.
- An `async def` streaming generator that makes a blocking call (freezes the server).
- Exposing the hot-reload dev server on the LAN, or running the LAN host with multiple workers.
- Binding `0.0.0.0` without loudly flagging the security implications.
- Hardcoding a hostname/IP for the LAN host instead of reading the machine's mDNS name.
- Claiming success from a dry run. Blind-deleting config a user calls "old" without grepping
  to confirm it's unused. Blanket-muting a warning instead of fixing it — or, in code you've
  promised not to rewrite, declaring it narrowly and by name.
- Transliterating the old UI — a component per `st.*` call, stacked in the original order — or
  rebuilding the full-page rerun in React by refetching everything on every change.
- "Redesigning" by quietly dropping features, or by discarding the old app's brand along with its
  layout. Layout parity is optional; feature and brand parity are not.
- Renaming or restructuring lifted engine code to satisfy a linter — that's rewriting the engine,
  not lifting it. So is `ruff format` across it. So is trusting `--fix` on an engine with no tests.
- Squashing the verbatim lift and the lint fixes into one commit, so the reviewer can no longer
  tell which lines the refactor actually changed.
- Ignoring version control: committing to the default branch instead of a working branch, adding
  a `Co-Authored-By`/"Generated with" trailer, or pushing/merging — all the user's call.
- Deleting or recreating a database the user hasn't confirmed is disposable, or migrating/
  dropping production data without their explicit go-ahead.

## Bundled resources

| File | Read / use when |
|---|---|
| `assets/README.md` | Before using any template — maps the `<placeholders>` to your project |
| `assets/Makefile` | Phase 5/6 — the universal entrance incl. the `host` target |
| `assets/backend/main.py` | Phase 2 — `create_app` + lifespan + DI + single-origin mount skeleton |
| `assets/backend/host.py` | Phase 6 — the LAN launcher (mDNS name, free port, 0.0.0.0, banner) |
| `assets/backend/pyproject-snippet.toml` | Phase 1/2 — src-layout hatch config + the ruff/PEP 8 gate + `--frozen` note |
| `assets/backend/.env.example` | Phase 2/6 — config header incl. hosting vars |
| `assets/frontend/vite.config.js` | Phase 4 — the `/api` dev proxy |
| `assets/frontend/api.js` | Phase 4 — HTTP wrapper + the manual SSE stream reader |
| `assets/README-template.md` | Phase 1 — the single comprehensive project-root README skeleton |
| `assets/gitignore`, `assets/backend/gitignore`, `assets/frontend/gitignore` | Phase 1 — the three ignores: root = shared only, sub-projects own their caches |
| `references/discovery-checklist.md` | Phase 0 — full discover checklist |
| `references/backend-architecture.md` | Phase 2 — why app-factory/lifespan/single-shared-object/single-worker |
| `references/python-style.md` | Phase 2 — read before `--fix`ing the lifted engine: the gate, the tests-as-oracle rule, the ledger |
| `references/frontend-redesign.md` | Phase 4 — read before writing components: old-idiom→React table, the delta list, the parity inventory |
| `references/sse-streaming.md` | Phase 3 — the two SSE flows, with the threadpool trap explained |
| `references/lan-host.md` | Phase 6 — mDNS, free-port scan, single worker, security guardrails |
