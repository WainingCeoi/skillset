# Frontend lint — prettier, and what it is *not*

The frontend half of `make lint` is **prettier**, run as a check: `prettier --check .` from
`frontend/`, zero findings. The backend half is ruff (`references/python-style.md`). One command
covers both:

```
make lint          # = make lint-backend (ruff) + make lint-frontend (prettier)
make lint-backend  # cd backend  && uv run --frozen ruff check src tests
make lint-frontend # cd frontend && npm run lint      -> prettier --check .
make -k lint       # both halves even if the first fails; still exits non-zero
```

`make lint` is also the last step of `make test`, so there is exactly one definition of "lint" in
the repo and no way for the two to drift.

## Prettier is a formatter, not a linter — say so out loud

It reformats; it does not reason. It will never tell you a variable is unused, a promise is
unawaited, a hook violates the rules of hooks, or a field name doesn't match the Pydantic model.
**`tsc -b` (inside `npm run build`) is the correctness gate**, and it is the one that holds the
HTTP contract this refactor just created. Prettier's job is narrower and still worth a gate: it
removes formatting from code review entirely and keeps every diff about behavior. Don't sell it
as more than that, and don't let a green `make lint` stand in for a type check.

What it *does* cover is wider than `src/**/*.tsx`: run over `.`, it also checks the CSS, the
`index.html`, the JSON configs, and the README in `frontend/`. That's the point — one formatter
for every file type the frontend has, rather than a per-language patchwork.

## Setup (four steps, in this order)

```bash
cd frontend
npm install -D --save-exact prettier                # exact, not ^ — see below
cp <skill>/assets/frontend/prettierrc.json .prettierrc.json
cp <skill>/assets/frontend/prettierignore .prettierignore   # optional; usually stays a stub
npm pkg set scripts.lint="prettier --check ." scripts.format="prettier --write ."
npm run format                                      # the scaffold is NOT formatted — see below
npm run lint                                        # must now pass
```

- **`--save-exact` is deliberate.** Prettier's output can change in a patch release, so a caret
  range turns `make lint` red on code nobody touched, in a commit that only ran `npm install`.
  Pin it and bump on purpose. This is the same argument the backend makes for pinning ruff via
  `uv.lock` (`assets/backend/pyproject-snippet.toml`), and it lands harder here because prettier
  *rewrites* files rather than merely reporting on them.
- **`npm pkg set` rather than hand-editing `package.json`** — it writes valid JSON and leaves the
  file prettier-clean. But look at what you're overwriting: **the `react-ts` template already
  ships `"lint": "oxlint"`**, and setting `scripts.lint` replaces it silently. Decide, don't
  clobber: keep it as `npm pkg set scripts.lint:oxlint="oxlint"` if you want it available, or
  drop it and say so. Prettier is this skill's required frontend gate; oxlint is optional and
  never a substitute for `tsc -b`.

## The config, and why it's three keys

```json
{ "semi": false, "singleQuote": true, "printWidth": 100 }
```

Everything else stays on prettier's defaults — the whole value of the tool is that nobody argues
about it, and every key you add is a key someone has to have an opinion about. These three earn
their place:

- **`printWidth: 100`** matches `line-length = 100` in the backend's `[tool.ruff]`. One number for
  the whole monorepo means a side-by-side of `schemas.py` and `api.ts` wraps the same way. (Note
  the tools disagree about what the number *means*: ruff reports a violation, prettier reflows to
  fit. Prettier at 100 will join JSX that the scaffold wrapped at 80.)
- **`semi: false` / `singleQuote: true`** match the bundled `assets/frontend/api.ts` and
  `vite.config.ts`, which are already prettier-clean under exactly this config — verified, so
  dropping them in doesn't produce a lint failure on your first `make lint`. Change these two if
  you prefer the defaults, but then reformat the two templates in the same commit.

**The config file must be JSON.** Prettier will happily read `prettier.config.js`, `.cjs` or
`.mjs` — and every one of those is a JavaScript file in a repo whose `make test` fails on any
`.js`/`.cjs`/`.mjs` anywhere (SKILL.md Phase 4). The `.ts` config forms exist in current prettier
but need a loader installed to be read at all. `.prettierrc.json` needs nothing, breaks nothing,
and is greppable. This is the same rule as "take the `.ts` config every time" — here the answer
happens to be JSON, because the no-JavaScript gate has no opinion about data files.

## The scaffold is not prettier-formatted — expect a red first run

A fresh `npm create vite@latest -- --template react-ts` fails `prettier --check .` on day one. On
a scaffold checked while writing this, four files were flagged: `src/App.tsx`, `src/App.css`,
`src/index.css`, and `tsconfig.json` (its `references` array fits on one line at width 100). That
is normal and it is not a sign the config is wrong.

Run `npm run format` **once, before you write any components**, and give it its own commit —
`style(frontend): prettier --write on the vite scaffold` — for the same reason the engine's lift
and its `ruff --fix` are two commits (`references/python-style.md`): a reformat is exactly the
commit a real change hides inside. Do it late instead and the formatting pass rewrites every
component you wrote, on top of the work you actually want reviewed.

After that, keep it green as you go: `npm run format` is one command and the fix is never
interesting. A frontend that gets formatted once at the end produces a final diff nobody can read.

## Ignore files: let the defaults work

Prettier skips `node_modules` on its own, and by default reads **both** `.gitignore` and
`.prettierignore`. Since `frontend/.gitignore` already lists `dist/` and `dist-ssr/`, the built
bundle is out of scope with no extra configuration — verified: after `npm run build`,
`prettier --check .` did not walk into `dist/`.

**The trap is `--ignore-path`.** Passing it *replaces* that default pair rather than adding to it,
so `prettier --check . --ignore-path .prettierignore` stops honoring `.gitignore` and immediately
reports `dist/assets/index-*.js` and `dist/index.html` as badly formatted — a minified bundle,
which is by definition not prettier-formatted and never will be. The failure looks like a
formatting problem and is actually a flag problem. Run plain `prettier --check .`.

So `.prettierignore` is usually a stub. It's for files that are committed *and* generated or
vendored — an OpenAPI-generated `types.ts`, a snapshot fixture — where prettier's reformat would
show up as a diff on every regeneration. Never list `dist/` in it; that's `.gitignore`'s job and
duplicating it is the same rot the three-way `.gitignore` split exists to avoid.

## Prove the gate fires

Same discipline as the ruff gate and the no-JavaScript `find` (Phase 7) — a gate you never watched
fail is a gate you're guessing about:

```bash
cd frontend
printf 'export const  x   =    1\n' >> src/main.tsx
npm run lint     # must print [warn] src/main.tsx and exit 1
git checkout src/main.tsx
```

**Read the exit code, not the message.** Prettier prints `All matched files use Prettier code
style!` unconditionally — it appears *underneath* an error, on the same run. A bad `cd` or a typo
in the path is caught anyway (`[error] No files matching the pattern were found` → exit **2**, and
an existing-but-empty directory gives `No supported files were found` → also exit 2), which is
already better than ruff's silent 0. But a directory that exists and holds only files prettier
doesn't handle — a `frontend/` that somehow contains nothing but `.py`, say — prints that same
cheerful line and exits **0**. `make` reads the exit code; a human skimming the log reads the
line. They don't always agree.
