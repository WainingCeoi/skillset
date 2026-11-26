# Skillset

Reusable skills for AI agents to translate documents, refactor Python apps, standardize Makefiles, and export WeCom chats.

## Install a skill

You need [Node.js 22.20 or newer](https://nodejs.org/) and an AI agent supported by the
[skills CLI](https://github.com/vercel-labs/skills).

Copy a command below into your terminal, then select your agent when prompted.
The `-g` flag makes the skill available across your projects; omit it to install only in the current project.
After installing, open your agent and try the example request.

### Translate documents

Translate PDFs, images, Office files, and text while preserving their layout.
Get an English copy and a bilingual English–Chinese copy.

```bash
npx skills add WainingCeoi/skillset --skill translate-documents -g
```

**Try:** “Translate this PDF into English and a bilingual English–Chinese copy.”

[Skill details](skills/translate-documents/SKILL.md)

### Refactor to FastAPI + React

Turn an existing Python app, such as Streamlit or Gradio, into a FastAPI backend and React frontend.

```bash
npx skills add WainingCeoi/skillset --skill refactor-to-fastapi-react -g
```

**Try:** “Refactor this Streamlit app into FastAPI and React.”

[Skill details](skills/refactor-to-fastapi-react/SKILL.md)

### Standardize Makefile commands

Consolidate an existing project's Make commands into exactly `make help`, `make dev`,
`make init`, and `make test`. The skill reuses existing implementations, merges partial
behavior, retires superseded targets and migrates their callers. It adapts startup and
isolated tests to the actual dependencies; `init` confirms a local reset before rebuilding.

```bash
npx skills add WainingCeoi/skillset --skill standardize-makefile -g
```

**Try:** “Consolidate this project's existing Make commands into help, dev, init, and test.”

[Skill details](skills/standardize-makefile/SKILL.md)

### Export WeCom chats for Slinx Talk

Export a date range from a WeCom group on macOS. The skill saves a structured `messages.jsonl`,
available attachments, an export report, and a single Slinx-compatible ZIP under `~/Downloads/data/` by default.
Capture requires a signed-in WeCom client and an agent with computer-use tools. ZIP validation
uses a local Slinx Talk checkout with its backend Python environment installed.

```bash
npx skills add WainingCeoi/skillset --skill wecom-export -g
```

**Try:** “Export last month's messages and available attachments from this WeCom group as one Slinx ZIP.”

[Skill details](skills/wecom-export/SKILL.md) · [Archive and validation guide](skills/wecom-export/references/complete-archive.md) · [Forwarded messages and source references](skills/wecom-export/references/forwarded-evidence.md)

## Install all skills

```bash
npx skills add WainingCeoi/skillset --skill '*' -g
```

Select the agent you want to use when prompted.

<details>
<summary>Maintainer commands</summary>

Run from the repository root. The full test suite requires `uv`, Node.js 22.6+, and `make`.

```bash
python3 scripts/package_skills.py build
python3 scripts/package_skills.py --check
uv run --with pymupdf python -m unittest discover -s tests -v
```

Generated `.skill` bundles are ignored by Git; edit the folders under `skills/`.

</details>

## License

[GNU General Public License v3.0](LICENSE).
