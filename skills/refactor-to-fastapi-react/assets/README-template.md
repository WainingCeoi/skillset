# <PROJECT>

<One-line description of what the app does.>

A **monorepo** with a FastAPI backend and a React frontend:

```
<project>/
├── Makefile        one entrance: install / dev / start / host / build / test / clean
├── backend/        FastAPI service + the engine (Python, src layout)
└── frontend/       React + Vite single-page UI (TypeScript)
```

## Quick start

```bash
make install     # backend deps (uv) + frontend deps (npm)
make dev         # backend :<PORT> + frontend :5173 together, hot-reload
```

Open **http://localhost:5173**. One command runs both servers; one Ctrl-C stops both. The Vite
dev server proxies `/api` to the backend, so the UI calls same-origin and streaming needs no CORS.

Single-server (build the UI and serve it + the API from one process, loopback):

```bash
make start       # builds frontend/dist, then serves UI + API on 127.0.0.1:<PORT>
```

### Host it on your LAN

To reach the app from another device on the same Wi-Fi:

```bash
make host                    # serves API + UI on http://<this-machine>.local:<PORT>
make host PORT=9000          # different base port (auto-advances if busy)
HOST=127.0.0.1 make host     # local-only
```

> ⚠️ `make host` binds `0.0.0.0` — everyone on the Wi-Fi can reach the app. <State the auth
> posture: "This app has no authentication, so anyone on the network has full access" OR "set a
> real secret/admin password first".> It's plain HTTP; run it only on a network you trust.

## Architecture

```
frontend (React+Vite) ──/api (JSON + SSE)──▶ backend (FastAPI) ──▶ <engine / external services>
```

- **`backend/src/<engine>/`** — the domain logic (framework-free, importable).
- **`backend/src/<app>_api/`** — the web layer: `main.py` (app factory + lifespan builds one
  engine on `app.state`), `deps.py`, `schemas.py`, `routers/`.
- **`frontend/src/`** — `api.ts` (one typed HTTP + SSE wrapper, mirroring the backend's Pydantic
  models) and the React `.tsx` components. **TypeScript 7 only** — no `.js`/`.jsx` anywhere in the
  frontend, including tool configs; `make test` fails if one appears or if `typescript` resolves to
  an older major. Formatting is **prettier**, configured in `frontend/.prettierrc.json` (JSON, for
  the same no-JavaScript reason) at the same 100-column width as the backend's ruff config.

## Configuration

Settings are read from environment variables / a `.env` file (copy `backend/.env.example`).
<List the few that matter, e.g. connection host, models, data dir.>

## Development

```bash
make lint               # BOTH linters: ruff (backend, PEP 8) + prettier (frontend, formatting)
make test               # backend tests + TS7/no-JavaScript checks + the UI type-check/build + make lint
make build              # frontend/dist only
make clean              # remove build artifacts
```

Each half on its own, and the underlying commands:

```bash
make lint-backend       # = cd backend && uv run ruff check src tests   (E/W/F/N, 100 cols)
make lint-frontend      # = cd frontend && npm run lint                 (prettier --check .)
make -k lint            # run both halves even if the first one fails
uv run pytest           # from backend/ — ALL backend tests, the single test command
npm run format          # from frontend/ — prettier --write . : the fixer for a failing lint
npm run build           # from frontend/ — `tsc -b && vite build`, so this type-checks the UI too
npx tsc --version       # from frontend/ — must be 7.x; `npm ls typescript` confirms what resolved
```

Prettier is a formatter, not a linter: `make lint` green means the frontend is *formatted*, and
`npm run build` (`tsc -b`) is what checks it's *correct*.

## Requirements

<OS notes>, Python ≥ 3.<x>, Node ≥ 20.19 (or ≥ 22.12 — Vite's engine floor), TypeScript 7 (pinned in
`frontend/package.json`), and <any external service, e.g. a local Ollama server>.
