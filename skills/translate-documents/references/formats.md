# Paths B–D: formats with an accessible text layer

Path A (OCR + overlay, in SKILL.md) is for pixels and curves. Everything else lets you edit
real text — cleaner replacements, real fonts, selectable output. The two-file contract is
identical everywhere: `<base>.en.<ext>` and `<base>.en-zh.<ext>`, layout preserved.

## Path B: PDF with a text layer

Confirm with `page.get_text("dict")` — type-0 blocks containing spans. Then replace text
span-by-span with redaction annotations, which delete the original glyphs *without* touching
underlying artwork:

```python
import fitz
doc = fitz.open("source.pdf")
for page in doc:
    d = page.get_text("dict")
    jobs = []
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if needs_translation(span["text"]):
                    jobs.append((fitz.Rect(span["bbox"]), span))
    for rect, span in jobs:
        page.add_redact_annot(rect)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)   # keep images intact!
    for rect, span in jobs:
        insert_translation(page, rect, span)   # size-to-fit, as in overlay_translate.py
doc.save("out.pdf", garbage=3, deflate=True)
```

- `images=fitz.PDF_REDACT_IMAGE_NONE` matters: default redaction erases image areas under
  the rect.
- Span bboxes of rotated text need the line's `dir` vector (`(0, ±1)` = vertical); handle
  horizontal spans first, then treat rotated ones per
  [ocr-pipeline.md § Vertical and rotated text](ocr-pipeline.md) — redact, then
  `insert_text(..., rotate=90)`.
- **RTL caveat:** extraction order for Hebrew/Arabic spans may be visual, not logical —
  glyphs can come out reversed. You still translate from your own reading of a rendered
  page; the text layer's job is the rectangles and the removal.
- Bilingual mode: same growth discipline as Path A — bounded expansion inside table cells.

## Path C: Office formats (docx / pptx / xlsx)

Native in-place editing preserves styles, tables, and reflow. Set up an ephemeral venv:

```bash
uv venv .venv && uv pip install --python .venv python-docx python-pptx openpyxl
```

- **docx** (`python-docx`): walk `doc.paragraphs` (and `table.rows[].cells[].paragraphs`,
  headers/footers). Replace text at the **run** level to keep bold/size/color; translating
  paragraph-wise loses intra-paragraph formatting, run-wise sometimes splits sentences —
  merge runs that share formatting before translating.
  Bilingual: duplicate the paragraph, translated line first, 中文 line after, same style.
- **pptx** (`python-pptx`): `shape.text_frame.paragraphs[].runs[]`, plus notes slides, plus
  grouped shapes (recurse `shape.shapes`). Bilingual: add a second line in the same text
  frame at ~0.8 em, or a paired text box for tight layouts.
- **xlsx** (`openpyxl`): translate string cells; keep formulas, numbers, dates untouched.
  Bilingual: either a mirrored sheet ("Sheet1 (EN)", "Sheet1 (EN+ZH)") or `EN\n中文` in-cell
  with wrap enabled — mirrored sheets read better for dense tables.

## Path D: txt / md / html

Rewrite the text, byte-preserve the scaffolding:

- **Markdown**: translate prose; leave code fences, URLs, link targets, front-matter keys.
  Bilingual: paragraph pairs (EN paragraph, then 中文 paragraph) — not line-by-line, which
  shreds list formatting.
- **HTML**: translate text nodes and `title`/`alt`/`placeholder` attributes only; never
  markup, ids, classes, or scripts. Parse properly (`from bs4 import BeautifulSoup` via uv,
  or html.parser) — regex over HTML corrupts entities.
- **Plain text**: translate; mirror the original's line-length discipline if it's wrapped.

## Cross-cutting notes

- **Multi-page**: the spec's per-label `page` field covers Path A; Paths B–D iterate pages /
  sheets / slides naturally. Verify *every* page render, not just page 0.
- **Choosing "nearest editable" when the source format can't express the result** (e.g. the
  user wants editable output from a scanned PDF): deliver the translated PDF *plus* offer a
  re-typeset docx; don't silently switch formats.
- **Filename**: translate the meaningful part, keep dates/codes verbatim
  (`העמדת ריהוט אוהל 28.6.26.pdf` → `Furniture Placement - Tent 28.6.26.en.pdf`).
- **Fonts for the bilingual copy**: `overlay_translate.py` auto-detects a CJK system font per
  OS (Arial Unicode on macOS, Microsoft YaHei `msyh.ttc` on Windows, Noto Sans CJK on Linux)
  with PyMuPDF's built-in CJK font as the universal fallback; in docx/pptx set the East Asian
  font on the run's `rPr` if the default renders tofu.
