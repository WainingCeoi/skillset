# Skillset

Reusable skills for AI agents to translate documents, refactor Python apps, and capture WeCom chats.

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

### Capture WeCom chats

Save a selected WeCom conversation as a local ZIP with messages and available attachments.
Requires WeCom to be open and signed in, and an agent with computer-use tools.

```bash
npx skills add WainingCeoi/skillset --skill wecom-chat-capture -g
```

**Try:** “Capture today's messages from this WeCom conversation and save them as a ZIP.”

[Skill details](skills/wecom-chat-capture/SKILL.md) · [Usage guide](skills/wecom-chat-capture/references/usage.md)

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
