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
of it, and rebuild the UI in React — not to rewrite the engine. If you find yourself editing
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

`assets/` in this skill holds drop-in versions of every non-obvious file (Makefile, the LAN
`host.py`, the `create_app` skeleton, `vite.config.js`, `api.js`, `.env.example`, the
`pyproject.toml` src-layout block, `.gitignore`). **Copy them and adapt the placeholders**
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

Example messages (one per phase):
`feat(backend): app factory + lifespan building one engine on app.state`
`feat(frontend): React+Vite SPA calling /api through a single api.js`
`feat(host): make host — LAN launcher on 0.0.0.0 with mDNS name + free-port scan`

## Phases

Do these in order. Each builds on the last, and several early decisions (where the engine seam
is, what streams) determine later structure. Commit at each phase boundary once it verifies, per
**Version control** above.

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
>   counts + spot checks) before considering the refactor done.
>
> This mirrors *verify before deleting*: a stale comment or filename calling a store "test data"
> is not permission to drop it — the user's explicit answer is.

### Phase 1 — Scaffold the monorepo

**First create the working branch** (e.g. `refactor/fastapi-react`) off the current branch — all
subsequent phases commit onto it. Then create `backend/` and `frontend/`, each with its own
`.gitignore`, a root `.gitignore`, and the backend **src layout**. For docs, write **one comprehensive project-root `README.md`** — start
from `assets/README-template.md`. It covers quick start, the `make` commands (incl. `make host`),
architecture, config, and the single test command. That one root README is what most users
actually want; **don't scatter docs across per-sub-project READMEs** unless a sub-project
genuinely needs its own.

Use the `pyproject.toml` block from `assets/backend/pyproject-snippet.toml`: `sources = ["src"]`
strips the `src/` prefix so the engine and API install at the wheel root and import cleanly. Lift
the engine package into `backend/src/<engine>/` **unchanged** — same module names, same internal
imports — so existing `from <engine> import X` lines keep working verbatim. A top-level `config`
module can stay a module (not a package) if the engine imports it as `from config import ...`.

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
Design the UI around the app's primary action (chat-first, dashboard-first, etc.); don't
mechanically transliterate the old Streamlit layout — a sidebar + focused main pane usually
beats a wall of stacked widgets. (If the user wants help with visual design, the
`frontend-design` skill pairs well here.)

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
  single-active-job registry, or boot migrations. Multiple workers would double-load the model
  and break in-process invariants. Never enable `--workers >1` for these apps.
- **Security — 0.0.0.0 is not localhost.** Surface it loudly (the template's banner does):
  binding to the LAN exposes the app to everyone on the network. If the app has auth, its
  secret/admin password must be real before exposing. **Cookie foot-gun**: if the framework
  sets a `Secure` (HTTPS-only) session cookie in "production" mode and you serve plain HTTP,
  the browser silently drops it and login won't stick — do *not* enable HTTPS-cookie/production
  mode for a plain-HTTP LAN host. If the app has no auth/cookies at all, say so — the exposure
  (unauthenticated access), not a cookie, is the real risk. Don't add HTTPS/PWA unless asked (a
  LAN cert means trusting a local CA on every device; a PWA/service worker needs a secure
  context and won't work over plain HTTP). Keep a `HOST=127.0.0.1` override for local-only.

### Phase 7 — Verify by observation

Prove it works by booting it the way each command does and watching real behavior — not by
asserting it should work:

- `make dev`: both servers up, UI loads, an API call round-trips, streaming streams.
- `make start`: build first (a bare run 404s with no `dist`), then one process serves UI + API
  same-origin on loopback.
- `make host`: `lsof -iTCP:<port> -sTCP:LISTEN` shows `*:<port>` (0.0.0.0), not 127.0.0.1;
  `curl` the machine's LAN IP **and** `<name>.local` → 2xx; occupy the base port and confirm it
  advances; tear down and confirm no leftover listeners.
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
  to confirm it's unused. Silencing a warning instead of fixing it.
- Committing the refactor straight onto the default branch instead of a working branch.
- Adding a `Co-Authored-By` / "Generated with" / attribution trailer to commit messages.
- Pushing or merging to the default branch — that's the user's decision, not the skill's.
- Deleting or recreating a database the user hasn't confirmed is disposable, or migrating/
  dropping production data without their explicit go-ahead.

## Bundled resources

| File | Read / use when |
|---|---|
| `assets/README.md` | Before using any template — maps the `<placeholders>` to your project |
| `assets/Makefile` | Phase 5/6 — the universal entrance incl. the `host` target |
| `assets/backend/main.py` | Phase 2 — `create_app` + lifespan + DI + single-origin mount skeleton |
| `assets/backend/host.py` | Phase 6 — the LAN launcher (mDNS name, free port, 0.0.0.0, banner) |
| `assets/backend/pyproject-snippet.toml` | Phase 1 — src-layout hatch config + `--frozen` note |
| `assets/backend/.env.example` | Phase 2/6 — config header incl. hosting vars |
| `assets/frontend/vite.config.js` | Phase 4 — the `/api` dev proxy |
| `assets/frontend/api.js` | Phase 4 — HTTP wrapper + the manual SSE stream reader |
| `assets/README-template.md` | Phase 1 — the single comprehensive project-root README skeleton |
| `assets/gitignore` | Phase 1 — root ignore |
| `references/discovery-checklist.md` | Phase 0 — full discover checklist |
| `references/backend-architecture.md` | Phase 2 — why app-factory/lifespan/single-shared-object/single-worker |
| `references/sse-streaming.md` | Phase 3 — the two SSE flows, with the threadpool trap explained |
| `references/lan-host.md` | Phase 6 — mDNS, free-port scan, single worker, security guardrails |
