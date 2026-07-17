# Template placeholder map

These files are drop-in scaffolds. Copy them into the new monorepo and replace the
placeholders below. They encode fixes for mistakes that are easy to rediscover the hard way —
prefer adapting them over writing from a blank page.

## Placeholders

| Placeholder | Meaning | Example |
|---|---|---|
| `<app>_api` | the FastAPI web-layer package name | `rag_api`, `shop_api` |
| `<app>_api.main:app` | the ASGI import path of the app object | `rag_api.main:app` |
| `<engine>` | the lifted domain-logic package | `rag`, `core`, `pricing` |
| `<EngineClass>` | the one heavy object built at startup | `RAGPipeline`, `Store` |
| `<PROJECT>` | human title for banners/README | `rag_system` |
| `<PORT>` | default base port | `8000` |

## What each file is for

- **Makefile** — the universal entrance. `make dev` (both servers, loopback, hot-reload),
  `make start` (single-origin, loopback), `make host` (single-origin, LAN), plus
  install/build/test/clean. Recipe lines are TAB-indented; keep `#` comments on their own line.
- **backend/main.py** — the `create_app(engine=None)` factory: lifespan builds one
  `<EngineClass>` on `app.state`, DI reads it back, routers mount under `/api`, and the built
  frontend is mounted at `/` for single-origin mode. Injecting `engine` skips the heavy build
  (tests) and the static mount.
- **backend/host.py** — the LAN launcher invoked by `make host`. Reads the machine's mDNS name,
  finds a free port by real bind test, prints URLs + a security banner, then serves on
  `0.0.0.0` with **one worker**. Set the `APP` constant to your `<app>_api.main:app`.
- **backend/pyproject-snippet.toml** — the hatch `src` layout config, the ruff/PEP 8 gate
  (declared dev dep, `preview = true`, the engine's `per-file-ignores` ledger), and the
  `filterwarnings` + `--frozen` notes. Merge into the backend `pyproject.toml`.
- **backend/.env.example** — config header including the hosting vars (`HOST`, `PORT`,
  static-dir override) and the "no-secret vs. set-your-secret" note.
- **frontend/vite.config.js** — dev server that proxies `/api` to the backend (same-origin
  dev, no CORS needed) and binds `127.0.0.1` (not IPv6-only `[::1]`, which some in-app browsers
  can't reach).
- **frontend/api.js** — the single HTTP wrapper + the manual `fetch`-stream SSE reader for POST
  streaming endpoints.
- **README-template.md** — the ONE comprehensive project-root README to write (quick start, the
  `make` commands incl. `make host`, architecture, config, and the single `uv run pytest` test
  command). Prefer this single root README over per-sub-project READMEs.
- **gitignore** — root ignore (rename to `.gitignore`). Each sub-project gets its own too.
- **No component or layout template — on purpose.** `vite.config.js` and `api.js` are plumbing
  (proxy + transport); there is deliberately no `App.jsx` to copy. The React UI is a *redesign*
  driven by the app's primary action (Phase 4), so a bundled layout would just be a second thing
  to transliterate. See `references/frontend-redesign.md`.
