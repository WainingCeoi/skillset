# Phase 4 — Redesigning the frontend (not porting it)

The React UI is a **redesign**. The old app tells you *what must exist*; it does not tell you
*where anything goes*. Refer to it as much as you like — just don't reproduce it. This file is
the translation layer. Visual direction is the `frontend-design` skill's job, not this one's.

## Why the old layout carries no information

Streamlit/Gradio layouts are artifacts of an execution model: the script reruns top-to-bottom on
every interaction, so widget order *is* DOM order, and every escape hatch (`sidebar`, `columns`,
`expander`, `tabs`) exists to buy back a little of what that model took away. Nobody sat down and
decided the sidebar. Copy it into React and you reproduce a constraint that no longer applies.

So the failure mode isn't ugliness — it's fidelity. A React tree that maps 1:1 onto the old
widget stack is the bug, even if it looks fine.

**The exception, and it matters: the theme is a real decision.** `.streamlit/config.toml`
`[theme]`, the `page_title`/`page_icon`, the logo — a human chose those. They are the one part of
the old UI that isn't framework residue. Carry them into the React app; ask before changing them.
"Redesign" is not a license to ship the Vite default palette under the title *Vite + React*.

## The translation table

| Old idiom | What it was compensating for | What React should do |
|---|---|---|
| one top-to-bottom column | the script reruns in order; there is no other layout | grid or flex, chosen from the primary action. If your component order matches the old widget order, you transliterated. |
| `st.sidebar` | the only second region the model offers | a sidebar *if* the information architecture earns one — not by default |
| `st.columns` | a crude escape from the single column | grid/flex. `st.columns` was a 50/50 escape hatch; the React version rarely wants 50/50. |
| `st.expander` | rationing vertical space on one long page | a route, a drawer, a panel — or just show it |
| `st.tabs` | fake pages inside one script | real routes, deep-linkable |
| `st.session_state` | module globals die on every rerun | component state / context / a query cache |
| full-page rerun on any change | the execution model itself | **nothing** — the problem is gone; don't simulate it with a global refetch |
| `st.spinner` | one global "the page is busy" | independent loading state per region |
| `st.cache_data` / `st.cache_resource` | recompute-on-rerun | gone client-side; the server-side singleton lives on `app.state` (Phase 2) |
| `st.write_stream` | the one streaming primitive | append tokens to state from the `api.js` SSE reader |
| `st.rerun()` | force the page to redraw | a state update |
| `st.file_uploader` | — | a controlled input posting `FormData` through `api.js` |
| `.streamlit/config.toml` `[theme]` | **nothing — this one is a real choice** | your CSS variables. Carry the colors and font over. |
| `st.set_page_config(page_title=, page_icon=)` | **also a real choice** | `index.html` `<title>` + favicon. Not "Vite + React". |
| Gradio `Blocks`/`Row`/`Column` | the same column model, same reasons | same as above |
| Flask + Jinja POST → redirect → render | no client state; the page *is* the state | `fetch` + local state; no navigation |

Reading rule: before porting a widget, find its row and ask what it was *for*. If the answer is
"a framework limitation", the React version is usually smaller — or absent.

## The two checks

**The delta list — this is the redesign check, and a port fails it.** Name **three things the
React UI does that the Streamlit execution model structurally could not**, and point at the code:

- state that survives an interaction without a rerun
- a region that loads, refreshes, or fails independently of the rest
- a view that deep-links (selection or job id in the URL)
- tokens appended to the DOM without redrawing the page
- a keyboard path to the primary action

Fewer than three and you didn't redesign it — you ported it.

**The parity inventory — this is the *other* check, and it catches the opposite failure.** A
transliteration passes it trivially (a 1:1 port has perfect parity by construction), so it is not
evidence of a redesign. What it catches is "redesign" as a euphemism for dropping what you didn't
feel like rebuilding. Phase 0's capability list is the contract; say where each item now lives:

```
upload a PDF            → Sources drawer, drag-drop zone
see ingest progress     → inline progress bar on the source row (was st.progress)
ask a question          → composer, centre column
watch tokens arrive     → streamed into the transcript (was st.write_stream)
see retrieved chunks    → right rail, collapsible (was st.expander)
change top-k            → Settings drawer (was a sidebar slider)
```

Merging three old widgets into one better control is a redesign; dropping the third is a
regression. If a capability genuinely shouldn't survive, say so and let the user decide — don't
let it vanish into a layout change.

## One visual system

Streamlit's execution model cost you a lot, but it bought one real thing: **every widget looked
the same, for free.** You are now hand-drawing every pixel, so that uniformity is gone unless you
rebuild it deliberately — and it is the first thing to go when components get styled one at a
time. Each screen looks fine alone; the app looks like four people built it.

Do this **before** the first component, not after. Retrofitting uniformity means editing every
file you already wrote, so the cost of skipping it is paid at the worst possible moment.

**1. Tokens — one file, one source of truth.** Every color, space, radius, font size, and shadow
is a CSS custom property. The old app's brand (Phase 0: `[theme]` primaryColor/background/font)
lands *here* and nowhere else, which is what makes "carry the brand forward" a concrete action
instead of a wish.

```css
:root {
  --color-bg: #ffffff;      --color-fg: #1a1a1a;
  --color-primary: #ff4b4b;   /* <- the old app's theme.primaryColor, not a new invention */
  --color-danger: #d93025;    --color-muted: #6b7280;
  --space-1: 4px; --space-2: 8px; --space-3: 16px; --space-4: 24px;
  --radius: 6px;            --font-sans: system-ui, sans-serif;
}
```

Pick a scale and stay on it. Spacing that goes 4/8/16/24 is a system; spacing that goes
7/13/22 because each looked right in isolation is the patchwork with extra steps.

**2. Primitives — one component per interactive element.** Exactly one `Button`, one `Input`, one
`Card`. Variants are props, not new components:

```jsx
<Button variant="primary">Ask</Button>
<Button variant="secondary">Cancel</Button>
<Button variant="danger" disabled>Delete</Button>
```

The primitive owns **every state**: hover, focus-visible, active, disabled, loading. That's the
real payoff — states are where hand-rolled buttons diverge invisibly. Ten bespoke buttons means
ten chances to forget a focus ring, and a missing focus ring is a keyboard user hitting a dead
end (your delta list probably promised a keyboard path).

**3. One library, or none.** Both are fine. A library's dialog next to a hand-rolled one that
almost matches is not — "almost" is the whole problem, and it's worse than either choice made
cleanly. If you adopt one, it is the *only* source of primitives.

### The check

Both halves are greppable, which is the point — "looks consistent" is an opinion, these are not.
Run both over the whole of `src/`, excluding only the token file (the one place literals are
*supposed* to live). Scoping the first one to `src/components/` is the obvious mistake: it leaves
every literal in `src/features/` invisible, and a gate with a blind spot reads exactly like a
clean run.

```bash
# 1. No literal colors, sizes, or radii outside the token file.
grep -rnE '#[0-9a-fA-F]{3,6}|[0-9]+px' src/ \
  --include='*.jsx' --include='*.js' --include='*.css' | grep -v 'styles/tokens.css'

# 2. Every button is the primitive.
grep -rn '<button' src/ | grep -v 'components/ui/Button'
```

Both must print nothing. A hit means a component is styling itself instead of consuming the
system: fix the token or the primitive, never the component. If a component genuinely needs a
value the tokens don't have, that's a missing token — not a licence for a literal.

Sanity-check the gates the same way you check the lint gate (Phase 7): drop a `#ff0000` into a
component and confirm check 1 fires. Silence you haven't falsified is not evidence.

## Common shapes

Phase 0 named the primary action; that picks the layout. State your pick in one line, build it,
show it running — a working UI is a far better prompt for feedback than a hypothetical, and CSS
is cheap to redo.

- **Chat / agent** — the transcript owns the viewport, composer pinned, sources in a collapsible
  rail. Not a form above a log.
- **Dashboard / monitor** — a grid of cards that load, refresh, and fail independently. The point
  is that one slow panel no longer freezes the page.
- **Pipeline / job runner** — the job *is* the page: input → live progress → result, deep-linkable
  by job id.
- **Browse / CRUD** — list + detail, selection in the URL.

Ask only about what the code can't tell you: an existing design system or component library
you're meant to match. The brand is in the repo — read it, don't ask.

## The phone is a first-class target

`make host` (Phase 6) exists so the app opens on a phone on the Wi-Fi. Check at **390px** before
claiming done: nothing scrolls horizontally, the primary action is reachable without zooming, a
rail collapses to a drawer rather than squeezing, tap targets ≥ 44px, the composer stays above
the keyboard. Fixed pixel widths and hover-only affordances are the usual culprits. (The Vite
scaffold ships the right viewport meta — don't hand-write `index.html` and lose it.)
