# Python style — PEP 8, ruff, and the lifted engine

The backend must be PEP 8 and `ruff check`-clean, zero errors. For the web layer you write from
scratch that's a matter of typing it correctly the first time — the checklist below is the whole
job. For the engine you just lifted it collides head-on with this skill's first principle — *the
engine should survive the refactor almost untouched* — and resolving that collision is what most
of this file is for. Read it before you run `--fix` on `src/<engine>/`.

The rule set and every "why not X" argument live in `assets/backend/pyproject-snippet.toml`,
commented. Don't restate them here; this file is about writing the new code clean and keeping the
engine intact.

## The gate

From `backend/`: `uv run ruff check src tests` — or `make lint-backend` from the repo root, which
runs exactly that. `make lint` adds the frontend half (prettier — `references/frontend-lint.md`),
and `make test` ends with `make lint`, so there is one definition of "lint" and no way for the two
to drift. Two properties are load-bearing and both are easy to lose — the snippet explains both:

- **ruff is a declared dev dependency.** Undeclared, `uv run` silently falls back to whatever
  ruff is on your PATH. The gate doesn't fail; it lints with a different rule set than your
  colleague's.
- **The paths are explicit.** An explicit path overrides `exclude`, so a stray ignore can't
  quietly shrink the gate; a bad `cd` gives `E902` and exit 1 instead of passing nothing.

Neither is a cure for the zero-files case: `src tests` that *exist* but hold no `.py` still exits
0 with `All checks passed!`. Only breaking it on purpose proves it fires (Phase 7).

**Scope: the gate covers the generated project, not this skill.** `assets/backend/main.py` does
not even parse — `from <engine> import <EngineClass>` is a placeholder. Don't lint `assets/`.

## Write it clean the first time — the web layer has no excuse

Everything in `src/<app>_api/` (and `tests/`) is code *you* are authoring during this refactor.
There is no inherited-debt argument for any of it, so the target isn't "ruff-clean after a cleanup
pass" — it's **PEP 8 as you type**, with the gate confirming rather than discovering. Two habits
make that real:

- **Run `make lint-backend` at every phase boundary**, next to the tests, not once at the end.
  Ten findings caught inside the phase that created them are a two-minute fix; two hundred at the
  end is a diff that touches every file you wrote and buries the one that mattered.
- **`--fix` is fine on code you wrote.** The tests-are-the-oracle rule below exists for the
  *lifted engine*, where a "safe" fix can delete a side-effect import you've never read. In
  `src/<app>_api/**` you know what every line is for, so `uv run ruff check src tests --fix` is an
  ordinary edit. It is still not a plan: `--fix` cannot rename a function (N802), cannot invent
  the import you forgot (F821), and cannot rewrap a 120-character comment (E501).

What the selected set (`E`, `W`, `F`, `N`, `preview = true`) actually asks of you, in the order
you'd trip it:

| Write it this way | Or ruff says |
|---|---|
| 4-space indent, spaces never tabs | E101, W191 |
| ≤ 100 columns — **comments and docstrings count**, and no autofix exists | E501 |
| Two blank lines between top-level `def`/`class`, one between methods | E301, E302, E303, E305 |
| One space around binary operators and after commas; none inside brackets or before `:`/`,` | E225, E226, E231, E201, E202, E203, E221 |
| No trailing whitespace; file ends with exactly one newline | W291, W293, W292, W391 |
| All imports at the top, one module per `import`, no `from x import *` | E401, E402, F403, F405 |
| No unused imports or locals; no undefined names | F401, F841, F821 |
| `is None`, `isinstance(x, T)`, `if flag:` — not `== None`, `type(x) ==`, `== True` | E711, E721, E712 |
| `except Exception:` over bare `except:`; `def f():` over `f = lambda:` | E722, E731 |
| Names that aren't `l`, `O`, `I`; no f-string without a placeholder | E741, F541 |
| `r"\d+"` for regex literals — a stray `"\d"` is an invalid escape | W605 |
| `snake_case` functions/args/locals, `PascalCase` classes, `UPPER_SNAKE` constants, `self`/`cls` first | N801–N806, N815 |

Three of these bite specifically in a FastAPI layer, and they're worth knowing before you write
the file rather than after:

- **camelCase on the wire is not camelCase in Python.** If the frontend contract wants
  `{"maxTokens": 100}`, do *not* name the Pydantic field `maxTokens` — that's N815 (mixedCase in
  class scope), and it makes the Python side read like the JSON instead of like Python. Keep the
  attribute `max_tokens` and put the camelCase in an alias (`Field(alias="maxTokens")`, or an
  `alias_generator` on the model config, with `populate_by_name` so both forms parse). The wire
  format is a serialization concern; PEP 8 governs the identifier.
- **Route handlers are functions, so they're `snake_case`** (N802) — `async def get_status()`, not
  `getStatus()`, even when the endpoint it serves is `/getStatus` and the `api.ts` wrapper that
  calls it is `getStatus`. Two languages, two conventions, one alias between them.
- **`Depends()` in a default argument is correct here**, and stays correct only because `B` isn't
  in `select`. flake8-bugbear's B008 flags every function call in an argument default — which is
  the entire FastAPI dependency-injection idiom. If you ever adopt `B` (its own branch, per the
  snippet), B008 is the one code you'll have to declare, and that's a config decision, not a
  reason to stop using `Depends`.

Long signatures are where the 100-column limit actually bites in this layer. Break them the way
the templates do — one parameter per line with a trailing comma — rather than reaching for a
`# noqa: E501`, which in code you just wrote is the anti-pattern this skill names outright.

## The rule that decides everything: the engine's tests are the oracle

The tempting rule is "autofix the mechanical findings, ignore the semantic ones." **Don't use
it.** It sorts by the *shape of the diff* rather than the *behavior of the code*, and the shape
lies. All three of these are ruff's **safe** `--fix`, no `--unsafe-fixes`:

```python
import readline                              # deleted -> input() loses history silently
from models import User  # registers User    # deleted, comment and all -> create_all() makes
                                             #   ZERO tables
return sum(c / (1+rate)**i ...)              # rewritten to (1 + rate) — E226, inside your
                                             #   algorithm, because preview is on
```

An import line **is** logic when the import has side effects, and preview's whitespace fixes
reach inside expressions. "It only touched imports and blank lines" is not a safety argument.

So use the oracle this skill already mandates — *verify by observing real behavior*:

> Run `ruff check --fix` on the engine, then **run the engine's tests**. Green → keep the fix.
> Red → revert it and put the code on the ledger. **If the engine has no tests, `--fix` is
> unverifiable — don't run it on the engine at all;** declare the codes and move on. A refactor
> is not where you acquire coverage. Never `--unsafe-fixes` on engine code.

It's binary, it's executable at 3am, and it catches all three cases above without you classifying
anything. It also degrades safely when the oracle is missing — where the taxonomy degrades to
confident deletion.

## The three findings no tool can fix for you

- **`src/<engine>/__init__.py` → F401.** The modal case: the engine re-exports (`from .engine
  import Pipeline`), Phase 1 promised `from <engine> import X` keeps working, and ruff's own
  message suggests **"removing"** first — the one action that breaks that promise. Do not hand-fix
  it. With `preview = true`, `--fix` rewrites it to `Pipeline as Pipeline`, preserving the
  export; that's the fix you want. Without preview there is *no* fix at all, only the suggestion.
  `__all__` is tidier. If neither fits: `per-file-ignores` on that one file.
- **Side-effect imports.** Ruff has a named, narrow mechanism for exactly this —
  `lint.pyflakes.allowed-unused-imports`. Prefer it over a scattered `# noqa`: it's declared in
  config, greppable, and reviewable in one glance.
- **E501 from a looser legacy line length.** Not autofixable at any safety level (Phase 0 should
  have caught this). Rewrapping the engine to satisfy it is rewriting the engine. Ledger it.

## The ledger, and why it isn't "silencing a warning"

SKILL.md's anti-pattern is *blanket-muting a warning instead of fixing it — or, in code you've
promised not to rewrite, declaring it narrowly and by name*. That second clause is not a loophole
invented for ruff; it's the skill's existing policy for inherited code, already written five
lines above `[tool.ruff]` in the snippet: *narrow, message-pinned `ignore:` lines ONLY for
deprecations that live entirely in a third-party package — never a blanket mute.* For the
duration of this refactor the engine has exactly that status: code you have promised not to
author. An N802 there is evidence of nothing except that the engine predates the refactor.

The hatch is honest only when all four hold:

1. **Narrow** — `per-file-ignores` scoped to `src/<engine>/**`. Never `src/<app>_api/**`, where a
   warning *is* evidence of a mistake you just made.
2. **Named** — specific codes. Never a family, never `ALL`, never a bare `# noqa`.
3. **Reasoned** — a comment saying why the fix would change behavior.
4. **Earned** — start empty; add only what the engine actually trips and the tests actually
   rejected. An ignore for a rule nothing hits is cargo cult.

That's a **ledger of inherited debt** — visible in `pyproject.toml`, countable, reviewable. A
mute button hides the count; a ledger publishes it. Tell the user what's on it.

**Watch the glob.** `make test` lints `src` *and* `tests`. Lifted engine tests named after the
engine's camelCase API (`def test_getDocuments`) trip N802 and are **not** covered by
`src/<engine>/**` — extend the ledger to them. Separately: `filterwarnings = ["error"]` now
applies to those lifted tests too, so a deprecation they used to print is now a failure. Same
Phase 1 move, different tool; the snippet's narrow-`ignore:` policy is the answer there.

## `ruff check` yes, `ruff format` no

Different tools, different problems. **Do not run `ruff format` over the lifted engine as part of
this refactor.** The consistency argument is real and worth almost nothing here — nobody else is
editing this engine mid-refactor. The cost is total: this skill commits per phase and the *user*
reviews the branch, so a whole-file reflow stops `git diff` from answering the only question the
reviewer has. A reformat is exactly the commit a real behavior change hides inside. On this
skill's own `host.py` the formatter would join a deliberately-wrapped multi-line `return` into a
single 100-character line — legal, uglier, and not its call to make.

The formatter is also not a superset of the gate: it can't split long comments or string
literals, so E501 survives it.

## The two-commit protocol

1. **`refactor(engine): lift <engine> out of <old app> verbatim`** — file moves only, zero
   content edits. `git diff -M` reports pure renames; the reviewer verifies the lift by reading
   nothing.
2. **`style(engine): ruff --fix on the lifted engine (no behavior change)`** — the output of
   `--fix`, plus the ledger, plus a green test run. Anything you typed by hand doesn't belong.

The point is that commit 2 is **regenerable**: a reviewer can check out commit 1, run the same
command, and see the same result. That's not a proof of behavior — the tests are what argue
that — but it's what separates "I moved these files" from "I moved these files and also…".
Squash the two and the reviewer is back to eyeballing a 40-file diff and trusting you. Any
genuinely semantic change you and the user decide is worth making gets a **third** commit, its
own message, and its own test.
