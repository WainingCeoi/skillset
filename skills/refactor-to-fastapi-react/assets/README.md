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
  `make start` (single-origin, loopback), `make host` (single-origin, LAN), `make lint` (ruff +
  prettier, as `lint-backend` + `lint-frontend`), plus install/build/test/clean. `make test` calls
  `$(MAKE) lint` instead of repeating either command, so there's one definition of "lint" in the
  repo. Recipe lines are TAB-indented; keep `#` comments on their own line.
- **backend/src/<app>_api/main.py** — the `create_app(engine=None)` factory: lifespan builds one
  `<EngineClass>` on `app.state`, DI reads it back, routers mount under `/api`, and the built
  frontend is mounted at `/` for single-origin mode. Injecting `engine` skips the heavy build
  (tests) and the static mount.
- **backend/src/<app>_api/host.py** — the LAN launcher invoked by `make host`. Copy the asset
  there so `python -m <app>_api.host` can import it. It reads the machine's mDNS name,
  finds a free port by real bind test, prints URLs + a security banner, then serves on
  `0.0.0.0` with **one worker**. Set the `APP` constant to your `<app>_api.main:app`.
- **backend/pyproject-snippet.toml** — the hatch `src` layout config, the ruff/PEP 8 gate
  (declared dev dep, `preview = true`, the engine's `per-file-ignores` ledger), and the
  `filterwarnings` + `--frozen` notes. Merge into the backend `pyproject.toml`.
- **backend/.env.example** — config header including the hosting vars (`HOST`, `PORT`,
  static-dir override) and the "no-secret vs. set-your-secret" note.
- **frontend/vite.config.ts** — dev server that proxies `/api` to the backend (same-origin
  dev, no CORS needed) and binds `127.0.0.1` (not IPv6-only `[::1]`, which some in-app browsers
  can't reach).
- **frontend/api.ts** — the single HTTP wrapper + the manual `fetch`-stream SSE reader for POST
  streaming endpoints. Typed: `request<T>` carries each endpoint's response shape (mirror the
  Pydantic model), and `StreamEvent` is the union of the SSE events the backend frames — a union,
  not an `enum`, because the scaffold compiles with `erasableSyntaxOnly` and `enum` is a hard error
  there. Keep the `getStatus` wrapper (or replace it with a real one): with every endpoint
  commented out, `noUnusedLocals` fails the build on `request` itself.
- **frontend/prettierrc.json** — rename to `.prettierrc.json`. Three keys, each a deliberate
  deviation from prettier's defaults: `printWidth: 100` matches `line-length = 100` in
  `[tool.ruff]` (one number for the whole monorepo), and `semi: false` + `singleQuote: true` match
  `api.ts`/`vite.config.ts`, which are prettier-clean under exactly this config — so dropping the
  templates in costs no lint failure. Everything else stays default on purpose: the value of
  prettier is that nobody argues about it. **JSON, not `prettier.config.js`** — that form is a
  JavaScript file, which `make test` fails on; the `.ts` forms need a loader installed.
- **frontend/prettierignore** — rename to `.prettierignore`; usually stays a stub. Prettier skips
  `node_modules` by default and reads **both** `.gitignore` and `.prettierignore`, so `dist/` is
  already out of scope — don't repeat it. Passing `--ignore-path` *replaces* that default pair
  rather than extending it, at which point prettier lints the minified bundle in `dist/`. See
  `references/frontend-lint.md`.
- **The frontend's `package.json` scripts** — `npm pkg set scripts.lint="prettier --check ."
  scripts.format="prettier --write ."`. `make lint-frontend` runs `npm run lint`, so the gate and
  the command a developer types by hand are the same thing. Note the `react-ts` template already
  defines `"lint": "oxlint"` and `npm pkg set` overwrites it silently — keep it as
  `scripts.lint:oxlint` or drop it, but decide. Install prettier with `--save-exact`: its output
  can change in a patch release, and a caret range turns the gate red on untouched code.
- **Both frontend templates are `.ts`, and the frontend has no `.js` in it at all.** Scaffold with
  `npm create vite@latest frontend -- --template react-ts`, then `npm install -D typescript@7` —
  the template pins an older major, so the upgrade is a required step, and `npx tsc --version`
  is how you know it took. Phase 4 has the rest (strict-by-default, `verbatimModuleSyntax`).
- **README-template.md** — the ONE comprehensive project-root README to write (quick start, the
  `make` commands incl. `make host`, architecture, config, and the single `uv run --frozen pytest` test
  command). Prefer this single root README over per-sub-project READMEs.
- **gitignore** (three of them: root, `backend/`, `frontend/`) — rename each to `.gitignore` in
  its own directory. **One rule: the root file holds only what belongs to no sub-project** (OS
  noise, editor state, `.claude/`); each sub-project ignores its own caches (`backend/`: `.venv`,
  `__pycache__`, `.env`, `data/`; `frontend/`: `node_modules`, `dist`). Nothing appears in two
  files. Git reads the nearest `.gitignore`, so a `backend/.venv/` line at the root adds nothing
  and only rots — and since a bare `.venv/` already matches at any depth, it was the same rule
  written twice anyway.
- **No component or layout template — on purpose.** `vite.config.ts` and `api.ts` are plumbing
  (proxy + transport); there is deliberately no `App.tsx` to copy. The React UI is a *redesign*
  driven by the app's primary action (Phase 4), so a bundled layout would just be a second thing
  to transliterate. See `references/frontend-redesign.md`.
