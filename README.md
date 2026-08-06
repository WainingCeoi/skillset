# Skillset

A collection of reusable [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) for
Claude Code / the Claude Agent SDK. Each skill is a self-contained folder with a `SKILL.md`
(the instructions + a triggering `description`) plus its bundled `assets/` (drop-in templates)
and `references/` (deep-dive docs loaded on demand).

## Skills

| Skill | What it does |
|---|---|
| [`skills/refactor-to-fastapi-react/`](skills/refactor-to-fastapi-react/) | Refactor a Python app that tangles UI and logic (Streamlit, Gradio, Flask, a CLI/monolith) into a clean **FastAPI + React/TypeScript (Vite) monorepo**, with a one-command `make` entrance, one-command lint for both languages (`make lint` → **ruff** + **prettier**), and an optional one-command **LAN host** (`make host` → `http://<machine>.local:<port>`). Ships battle-tested scaffold templates and a discover→change→verify workflow. |
| [`skills/translate-documents/`](skills/translate-documents/) | Translate any document file (PDF, image, Office, HTML, text) out of any language into **two layout-preserving outputs**: an English-only copy and a bilingual English+Chinese copy. Handles flattened/scanned PDFs with no text layer via an OCR→spec→overlay pipeline (Apple Vision / Windows.Media.Ocr / tesseract + PyMuPDF, auto-selected per OS), with debug-overlay and reviewer verification gates. |

## Layout

```
skillset/
├── README.md
├── LICENSE
└── skills/
    ├── refactor-to-fastapi-react/
    │   ├── SKILL.md          # instructions + triggering description (required)
    │   ├── assets/           # drop-in scaffold templates (Makefile, host.py, app-factory, …)
    │   └── references/       # deep-dives loaded on demand (SSE, architecture, LAN host, discovery)
    └── translate-documents/
        ├── SKILL.md          # the two-file contract + the OCR→spec→overlay pipeline
        ├── assets/           # ocr_vision.swift, overlay_translate.py, spec-example.json
        └── references/       # ocr-pipeline.md, formats.md (text-layer PDF / Office / text paths)
```

Skills live under `skills/` (the layout the `skills` CLI discovers). Add more by dropping another
`skills/<skill-name>/` folder, each with its own `SKILL.md`. Keep the folder name lowercase-kebab
and matching the `name:` field in that `SKILL.md`'s frontmatter so it loads cleanly.

## Installing

### Everything, one command

With the [`skills` CLI](https://github.com/vercel-labs/skills) — installs every skill in
this repo, for every detected agent, no prompts (`--all` = `--skill '*' --agent '*' -y`):

```bash
npx skills add WainingCeoi/skillset --all -g
```

`-g` installs user-level into `~/.claude/skills/`; drop it to install into the current
project's `.claude/skills/` instead. From a local clone, the no-tooling equivalent:

```bash
cp -R skills/* ~/.claude/skills/
```

### A single skill

```bash
npx skills add WainingCeoi/skillset --skill refactor-to-fastapi-react -g
```

…or copy one folder directly (`cp -R skills/refactor-to-fastapi-react ~/.claude/skills/`),
or install its packaged `.skill` bundle from the Claude Code / claude.ai skills UI.

Once installed, a skill triggers automatically when a request matches its `description`
(e.g. "get this Streamlit app off Streamlit and give it a real backend + frontend", or
"translate this PDF to English").

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
