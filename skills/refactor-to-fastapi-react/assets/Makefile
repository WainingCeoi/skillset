# Universal entry point for the monorepo (backend + frontend).
# Run `make` (or `make help`) to see the targets. Recipe lines MUST be TAB-indented.
# Replace <app>_api with your web-layer package and <PORT> with your base port.
SHELL := /bin/bash

.PHONY: help install dev backend frontend build start host lint lint-backend lint-frontend test clean

help:
	@echo "make install   install backend (uv) + frontend (npm) dependencies"
	@echo "make dev       run backend (:<PORT>) + frontend (:5173) together, hot-reload"
	@echo "make start     build the frontend, then serve API + UI from ONE server (127.0.0.1:<PORT>)"
	@echo "make host      build + serve API + UI to the whole LAN (http://<this-machine>.local:<PORT>)"
	@echo "make build     build the frontend for production (frontend/dist)"
	@echo "make lint      lint BOTH halves: ruff (backend, PEP 8) + prettier (frontend format)"
	@echo "make test      backend tests + TS7/no-JS checks + frontend type-check/build + make lint"
	@echo "make clean     remove build artifacts and caches"

# `npm install` obeys package.json, where TypeScript is pinned to ^7 (Phase 4) — don't re-run
# `npm install -D typescript@7` here: it rewrites package.json/package-lock.json on every install,
# which is the same side effect `uv run --frozen` exists to avoid on the backend. `make test`
# asserts the resolved version instead.
install:
	cd backend && uv sync
	cd frontend && npm install

# Development: both servers, one command, one Ctrl-C. Vite proxies /api -> :<PORT>.
dev:
	@echo "backend  -> http://127.0.0.1:<PORT>"
	@echo "frontend -> http://localhost:5173"
	@trap 'kill 0' EXIT INT TERM; \
	( cd backend && uv run uvicorn <app>_api.main:app --reload --port <PORT> ) & \
	( cd frontend && npm run dev ) & \
	wait

# Production-style: one process serves the built UI and the API on :<PORT> (loopback).
start: build
	@echo "serving API + UI -> http://127.0.0.1:<PORT>"
	cd backend && uv run uvicorn <app>_api.main:app --port <PORT>

# LAN host: build the UI, then serve API + UI from ONE process bound to 0.0.0.0 so every
# device on the same Wi-Fi can reach it at http://<this-machine>.local:<port>. The launcher
# prints the real URLs, auto-advances past a busy port, and warns about LAN exposure.
# Overrides: HOST=127.0.0.1 (local-only), PORT=<n> (base port). --frozen: never rewrite the lock.
host: build
	cd backend && uv run --frozen python -m <app>_api.host

build:
	cd frontend && npm run build

backend:
	cd backend && uv run uvicorn <app>_api.main:app --reload --port <PORT>

frontend:
	cd frontend && npm run dev

# ONE lint entrance for both languages: ruff for Python, prettier for the frontend. Split into
# two named halves so you can run either alone while you're working in one of them; `make lint`
# just depends on both. Make stops at the first failing prerequisite — deliberate, so you fix one
# language at a time — while `make -k lint` runs both halves and still exits non-zero if either
# failed, which is the form you want in CI when you'd rather see every finding at once.
lint: lint-backend lint-frontend

# Explicit `src tests` paths, not a bare `ruff check`: an explicit path overrides `exclude`, so a
# stray ignore can't quietly shrink the gate to nothing, and a bad `cd` fails loudly with E902.
# Ruff still prints "All checks passed!" and exits 0 when it linted ZERO files, so prove the gate
# fires (Phase 7) rather than trusting the message.
lint-backend:
	cd backend && uv run ruff check src tests

# `npm run lint` is `prettier --check .` (defined once, in frontend/package.json) so a dev running
# it by hand gets exactly what this gate runs. Prettier is a FORMATTER: green here means the
# frontend is formatted, NOT that it is correct — `npm run build` (tsc -b) is that gate.
# `prettier --write .` (= `npm run format`) is the fixer. Never add `--ignore-path` to either:
# prettier reads BOTH .gitignore and .prettierignore by default, and naming one DROPS the other —
# at which point it lints frontend/dist and flags the minified bundle you just built.
lint-frontend:
	cd frontend && npm run lint

# Correctness first, cosmetics last: every line above `make lint` answers "does the code still
# work?", and a missing blank line or an unformatted JSX prop should never be what hides the
# answer. Each recipe line aborts the target on a non-zero exit, so the first real failure wins.
# The frontend build line is the TypeScript gate too: the react-ts template's build script is
# `tsc -b && vite build`, so a type error fails here. If someone trims it to a bare `vite build`,
# types stop being checked (Vite only strips them) and this stops testing anything but bundling.
# The two checks before it are the ones a green build would NOT catch: the build passes just as
# happily on an older typescript, and it never notices a .js file nobody imports yet — anywhere in
# the repo, not just under frontend/. The prunes are anchored by PATH, not name: a bare
# `-name dist` would also prune a source dir called dist and hide a real violation inside it.
test:
	cd backend && uv run pytest -q
	cd frontend && { npx tsc --version | grep -qE 'Version 7\.' || { echo "frontend: TypeScript 7 required, got $$(npx tsc --version)"; exit 1; }; }
	@if find . -type d \( -name node_modules -o -name .git -o -name .claude -o -name .venv -o -path './frontend/dist' -o -path './frontend/dist-ssr' \) -prune -o \( -name '*.js' -o -name '*.jsx' -o -name '*.cjs' -o -name '*.mjs' \) -print | grep .; then echo "^ JavaScript in this repo — this project is TypeScript-only"; exit 1; fi
	cd frontend && npm run build
	@$(MAKE) lint

clean:
	rm -rf frontend/dist
	find backend -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
