# <PROJECT>

<One-line description of what the app does.>

A **monorepo** with a FastAPI backend and a React frontend:

```
<project>/
├── Makefile        one entrance: install / dev / start / host / build / test / clean
├── backend/        FastAPI service + the engine (Python, src layout)
└── frontend/       React + Vite single-page UI (JavaScript)
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
- **`frontend/src/`** — `api.js` (one HTTP + SSE wrapper) and the React components.

## Configuration

Settings are read from environment variables / a `.env` file (copy `backend/.env.example`).
<List the few that matter, e.g. connection host, models, data dir.>

## Development

```bash
uv run pytest           # run ALL backend tests (from backend/) — the single test command
uv run ruff check src tests   # lint the backend: PEP 8 via ruff (E/W/F/N, 100 cols) — zero errors
make test               # both of the above + a frontend build check
make build              # frontend/dist only
make clean              # remove build artifacts
```

## Requirements

<OS notes>, Python ≥ 3.<x>, Node ≥ 18, and <any external service, e.g. a local Ollama server>.
