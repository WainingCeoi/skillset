# Skillset

A collection of reusable [Agent Skills](https://docs.claude.com/en/docs/claude-code/skills) for
Claude Code / the Claude Agent SDK. Each skill is a self-contained folder with a `SKILL.md`
(the instructions + a triggering `description`) plus its bundled `assets/` (drop-in templates)
and `references/` (deep-dive docs loaded on demand).

## Skills

| Skill | What it does |
|---|---|
| [`skills/wecom-chat-capture/`](skills/wecom-chat-capture/) | Capture an explicitly authorized WeCom conversation/range through its already-open UI; validate and package original messages and unchanged media locally as baseline/incremental ZIP batches, with explicit gaps and overlap review. Includes synthetic fixtures and deterministic offline tooling. |
| [`skills/refactor-to-fastapi-react/`](skills/refactor-to-fastapi-react/) | Refactor a Python app that tangles UI and logic (Streamlit, Gradio, Flask, a CLI/monolith) into a clean **FastAPI + React/TypeScript (Vite) monorepo**, with a one-command `make` entrance, one-command lint for both languages (`make lint` → **ruff** + **prettier**), and an optional one-command **LAN host** (`make host` → `http://<machine>.local:<port>`). Ships battle-tested scaffold templates and a discover→change→verify workflow. |
| [`skills/translate-documents/`](skills/translate-documents/) | Translate any document file (PDF, image, Office, HTML, text) out of any language into **two layout-preserving outputs**: an English-only copy and a bilingual English+Chinese copy. Handles flattened/scanned PDFs with no text layer via an OCR→spec→overlay pipeline (Apple Vision / Windows.Media.Ocr / tesseract + PyMuPDF, auto-selected per OS), with debug-overlay and reviewer verification gates. |

## Layout

```
skillset/
├── README.md
├── LICENSE
├── scripts/
│   └── package_skills.py        # deterministic .skill build + stale-bundle check
├── tests/                    # regression tests for the shipped assets/tooling
└── skills/
    ├── refactor-to-fastapi-react/
    │   ├── SKILL.md          # instructions + triggering description (required)
    │   ├── assets/           # drop-in scaffold templates (Makefile, host.py, app-factory, …)
    │   └── references/       # deep-dives loaded on demand (SSE, architecture, LAN host, discovery)
    └── translate-documents/
        ├── SKILL.md          # the two-file contract + the OCR→spec→overlay pipeline
        ├── assets/           # Vision/Windows OCR, overlay_translate.py, spec-example.json
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

### Packaging bundles

The folders in `skills/` are the source of truth. Build deterministic `.skill` archives before
attaching a release or using the skills UI, then verify that no archive is stale:

```bash
python3 scripts/package_skills.py build
python3 scripts/package_skills.py --check
```

The generated root-level `.skill` files are intentionally ignored by Git. Run `--check` in CI or
immediately before publishing to catch missing files, stale content, or unexpected bundle entries.
The packager excludes standard generated cruft (`__pycache__`, `.DS_Store`, `.pyc`, `.pyo`) and
rejects symlinks rather than following files outside a skill folder.

### Regression tests

Run the repository checks with PyMuPDF available:

```bash
uv run --with pymupdf python -m unittest discover -s tests -v
```

The raw TypeScript transport test also needs Node 22.6+ (for built-in type stripping), and the
process-supervisor test needs `make`. These are test-harness requirements; generated Vite projects
retain the Node version range documented in their own README.

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
