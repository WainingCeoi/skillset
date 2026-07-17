# Phase 0 — Discovery checklist

You cannot design a good API before you understand the app you're converting. Spend real
effort here; every later phase depends on it. Produce a short written map and, if the user
asked you to check in, report it before editing. When the codebase is large, fan these out
across parallel read-only subagents (one per dimension) and synthesize.

## 1. Entrypoints & launch
- Every way the app starts today (scripts, `Makefile`, `package.json`, `if __name__`,
  `streamlit run`, `flask run`, Docker/compose/Procfile) and the host:port each binds.
- Which are hot-reload dev servers vs. production-style.

## 2. The engine ↔ UI seam (the most important finding)
- Which modules are **pure logic** — importable with no UI framework import? Those lift
  cleanly into `src/<engine>/`.
- Which are **view/callback** code (`st.*`, `gr.*`, request handlers, `print`/`input`)?
- Where are they **interleaved** — a function that both computes and renders? Extracting the
  computation into a plain function the UI merely calls is your first real refactor task, and
  it's worth doing in the *old* codebase first if that's low-risk, so the seam is proven before
  you move files.

## 2b. The UI: capabilities and brand (Phase 4's inputs)
- What is the app's single most important user action? The redesign is organized around it, and
  knowing it means you don't have to run a design questionnaire — you can decide and show.
- **Capability inventory** — one line per feature, input, output, and piece of state shown to the
  user. Write it now, while you're already reading the UI code. Phase 4 discards the *layout* and
  rebuilds against this list; anything not on it silently disappears.
- **Brand & assets** — `.streamlit/config.toml` `[theme]` (primaryColor, background, font),
  `st.set_page_config(page_title=, page_icon=)`, logo/image files the UI loads, any custom CSS in
  `st.markdown(..., unsafe_allow_html=True)`. **The layout is discarded; the brand is not.** The
  theme config is the one artifact in the old UI where a human actually made a design decision —
  everything else is what the framework permitted. Carry it forward; ask before changing it.

## 3. In-memory state
- What lives between interactions: a loaded model, a DB/client handle, a cache, `st.session_state`,
  module globals? Each becomes either (a) one object built at startup and shared on `app.state`,
  or (b) per-request state passed explicitly. Prefer (a) for expensive singletons.
- Anything that assumes a single process/single user? That constrains you to one worker.

## 4. Long-running & streaming operations
- Progress bars, token streams, multi-second jobs, background pollers, file ingest.
- These become SSE endpoints (see `sse-streaming.md`) and often force single-worker + a job
  registry. Note which are POST (need manual fetch-stream) vs. pollable GET (EventSource).

## 5. Config & secrets
- Grep for **every env var the code actually reads** (`os.environ`, `os.getenv`, settings
  classes, `import.meta.env`/`VITE_` on the frontend). Do NOT trust the `.env` template — it
  drifts from the code in both directions (dead entries; undocumented live vars).
- Flag real **secrets / signing keys / admin passwords** — they gate LAN exposure (Phase 6).
- Note **dead** vars (in template, unread by code) as deletion candidates — but only after
  grepping to confirm each is truly unused. Never delete a live security var over a stale
  comment; fix the comment.

## 6. Data & database (a decision for the user)
- Does the app persist data — a SQL/NoSQL DB, a vector store (Chroma/etc.), or files on disk?
  Where does it live, and how big / real does it look?
- **Classify it with the user; don't assume.** Three cases, each handled differently:
  - **(a) No database** — nothing to carry over.
  - **(b) Disposable sample/test store** — fine to delete and recreate fresh in the new layout,
    *after* the user confirms.
  - **(c) Production store with real data** — **never delete.** Plan an explicit import/migration
    into the new backend's store and verify the data survived (row/document counts + spot checks).
- Never delete or migrate data on your own read of a filename/comment — wait for the user's
  explicit go-ahead.

## 7. Package manager & side effects
- Backend: uv / poetry / pip? Frontend: npm / pnpm / yarn? Which lockfiles exist?
- **Side-effect warning**: `uv run` re-resolves and can rewrite `uv.lock` just from running;
  `npm install` can rewrite `package-lock.json`. Plan `uv run --frozen` / `npm ci` where the
  lock must not move, and check `git status` after (Phase 7).
- **Existing lint/style config**: a `.flake8`, `setup.cfg`, `[tool.black]`, `[tool.ruff]`, or
  `.editorconfig`. You only care about one number: the old **max line length**. Tighter than our
  100 is a non-event. **Looser** (120, or none) means the lifted engine will trip E501 — which is
  *not* autofixable at any safety level — so it goes on the ledger, not through a rewrap.

## Output of Phase 0
A short map: launch commands + ports; the engine/UI seam (what lifts, what gets rewritten); the
UI capability inventory + brand/theme assets (Phase 4's contract); the shared-state objects; the
streaming operations; the real config vars + any secrets; the data/database situation + the
user's chosen handling (none / disposable / migrate); the package manager + lockfile risk + the
old max line length. That's enough to design the routers, the app-state model, and the UI.
