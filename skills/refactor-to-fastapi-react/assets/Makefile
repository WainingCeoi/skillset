# Universal entry point for the monorepo (backend + frontend).
# Run `make` (or `make help`) to see the targets. Recipe lines MUST be TAB-indented.
# Replace <app>_api with your web-layer package and <PORT> with your base port.
SHELL := /bin/bash

.PHONY: help install dev backend frontend build start host test clean

help:
	@echo "make install   install backend (uv) + frontend (npm) dependencies"
	@echo "make dev       run backend (:<PORT>) + frontend (:5173) together, hot-reload"
	@echo "make start     build the frontend, then serve API + UI from ONE server (127.0.0.1:<PORT>)"
	@echo "make host      build + serve API + UI to the whole LAN (http://<this-machine>.local:<PORT>)"
	@echo "make build     build the frontend for production (frontend/dist)"
	@echo "make test      backend tests + lint + a frontend build check"
	@echo "make clean     remove build artifacts and caches"

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

test:
	cd backend && uv run pytest -q && uv run ruff check
	cd frontend && npm run build

clean:
	rm -rf frontend/dist
	find backend -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
