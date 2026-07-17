# Skillset

A collection of reusable [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) for
Claude Code / the Claude Agent SDK. Each skill is a self-contained folder with a `SKILL.md`
(the instructions + a triggering `description`) plus its bundled `assets/` (drop-in templates)
and `references/` (deep-dive docs loaded on demand).

## Skills

| Skill | What it does |
|---|---|
| [`skills/refactor-to-fastapi-react/`](skills/refactor-to-fastapi-react/) | Refactor a Python app that tangles UI and logic (Streamlit, Gradio, Flask, a CLI/monolith) into a clean **FastAPI + React (Vite) monorepo**, with a one-command `make` entrance and an optional one-command **LAN host** (`make host` → `http://<machine>.local:<port>`). Ships battle-tested scaffold templates and a discover→change→verify workflow. |

## Layout

```
skillset/
├── README.md
├── LICENSE
└── skills/
    └── refactor-to-fastapi-react/
        ├── SKILL.md          # instructions + triggering description (required)
        ├── assets/           # drop-in scaffold templates (Makefile, host.py, app-factory, …)
        └── references/       # deep-dives loaded on demand (SSE, architecture, LAN host, discovery)
```

Skills live under `skills/` (the layout the `skills` CLI discovers). Add more by dropping another
`skills/<skill-name>/` folder, each with its own `SKILL.md`. Keep the folder name lowercase-kebab
and matching the `name:` field in that `SKILL.md`'s frontmatter so it loads cleanly.

## Installing a skill

From GitHub with the [`skills` CLI](https://github.com/vercel-labs/skills) (installs into
`.claude/skills/`; add `-g` for `~/.claude/skills/`):

```bash
npx skills add WainingCeoi/skillset --skill refactor-to-fastapi-react -g
```

…or copy the folder directly:

```bash
cp -R skills/refactor-to-fastapi-react ~/.claude/skills/
```

Or install the packaged `.skill` bundle from the Claude Code / claude.ai skills UI. Once
installed, a skill triggers automatically when a request matches its `description` (e.g. "get
this Streamlit app off Streamlit and give it a real backend + frontend").

## License

Copyright (C) 2026 Waining Ceoi

This project is licensed under the **GNU General Public License v3.0** — see the
[`LICENSE`](LICENSE) file for the full text.

This is free software: you can redistribute it and/or modify it under the terms of the GPL as
published by the Free Software Foundation, either version 3 of the License, or (at your option)
any later version. It is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE.

> Note: the scaffold files under each skill's `assets/` are meant to be **copied into the
> projects you generate**. GPL-3.0 is copyleft, so if you want code scaffolded from these
> templates to be freely licensed by its authors, keep the templates as-is; if you'd rather the
> generated projects carry no license obligation, relicense just the `assets/` under a permissive
> license (e.g. MIT) or add a template exception. Choose deliberately before publishing.
