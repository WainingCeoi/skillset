# Backend architecture — why these patterns

The backend is a *thin* web layer in front of the lifted engine. Its whole job is: build the
engine once, share it, expose it over `/api`, and (in production) serve the built UI. The
patterns below exist to make that reliable and testable. See `assets/backend/main.py` for the
skeleton these describe.

## App factory: `create_app(engine=None)`

A factory (not a module-level `app` built by side effect) lets tests construct an app with a
**fake engine injected** — no models loaded, no network, no disk. The `engine=None` default
means real runs build the real thing; tests pass a stub. The same parameter also gates the
static-file mount (tests only exercise `/api`, so they skip it). A module-level
`app = create_app()` still exists at the bottom for `uvicorn <app>_api.main:app` to import.

## Lifespan: build once, share on `app.state`

These apps are single-user / on-device, so one engine instance serves the whole process. Build
it in the lifespan (startup) and put it on `app.state.engine`; dependencies read it back. This
is better than a module global because it's tied to the app's lifecycle and swappable in tests.

**Warm expensive resources in the background.** If the engine loads a big model, don't block
startup on it — spawn a daemon thread that warms it while the server starts accepting
connections. The first real request then hits a warm cache instead of paying the load cost. The
server binds immediately regardless.

## Dependency injection

`get_engine(request)` / `get_settings(request)` pull off `app.state`. Routers depend on these
via `Depends`, so they never construct anything and are trivial to test. Keep routers thin:
parse/validate the request (Pydantic), call one engine method, shape the response. **No domain
logic in routers** — if a router grows real logic, that logic belongs in the engine.

## Routers + Pydantic schemas = the contract

One router module per resource, mounted under `/api`. Every request and response gets a
Pydantic model in `schemas.py`. This schema *is* the contract the frontend codes against and
what FastAPI renders at `/docs` — keep it honest and typed.

## Single worker

If the app has any of: a big in-memory model, an in-process cache, a single-active-job
registry, module-global coordination state, or boot migrations — it must run **one worker**.
Multiple uvicorn workers are independent processes: they'd each load their own copy of the
model (N× RAM), each keep their own cache (incoherent), and each keep their own job registry
(so a job started on worker A is invisible to a status poll routed to worker B, and any
"one active job" invariant breaks). `make dev`/`make start`/`make host` all run one worker. Do
not reach for `--workers >1` to "scale" these apps; scale by making the engine faster instead.

## Single-origin production mount

In production you want one port, not two servers. Mount the built frontend
(`frontend/dist`) at `/` with an SPA-aware `StaticFiles` subclass **after** the `/api` routers
and `/docs`. Its 404 fallback serves `index.html` only for HTML navigation, never unknown `/api`
paths or missing assets, so client-side routes work without masking real 404s. Gate the mount on
the dist folder existing (so a dev run without a build doesn't crash) and on not being in test
mode. Because the UI is then same-origin with the API, CORS is not exercised in production — it
only matters for the dev proxy and any direct API access.
