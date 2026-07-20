# OCR pipeline: boxes you can trust

The OCR stage exists to produce **bounding boxes**, not text. The agent reading the rendered
page is the authority on content; OCR that garbles a script is still useful if its boxes are
tight. This file covers engine selection, setup traps, clustering, and the coordinate math.

## Engine by platform

Detect the OS (`platform.system()` / `uname`) and pick automatically — never ask:

| Platform | Native engine (zero install) | Fallback |
|---|---|---|
| macOS (`Darwin`) | Apple Vision — `assets/ocr_vision.swift` | tesseract via brew |
| Windows | Windows.Media.Ocr — `assets/ocr_windows.ps1` | tesseract via winget |
| Linux | — | tesseract via apt/dnf |

Use the native engine first (better boxes, no downloads), tesseract whenever the native
engine lacks the script — each engine's language gaps are listed in its section below.

## Rendering for OCR

Render PDF pages at **200 dpi** (`page.get_pixmap(dpi=200)`) — enough resolution for small
labels without exploding OCR time. **Windows exception: render at 150 dpi** — Windows.Media.Ocr
rejects images over ~2600 px (`MaxImageDimension`), and an A3 sheet at 200 dpi is 3309 px
wide. Record the dpi; every box in the spec is in pixels at that
dpi, and the overlay converts with `pt = px * 72/dpi`. For plain image inputs there is no
dpi — treat the image's own pixels as the spec space and set `"dpi"` so that
`px * 72/dpi` gives sensible page points for the output PDF (or overlay directly onto the
image with Pillow and skip the pt conversion).

## Engine 1: Apple Vision (macOS, zero install)

`assets/ocr_vision.swift` wraps `VNRecognizeTextRequest`:

```bash
swift assets/ocr_vision.swift page0_200.png "ja-JP,en-US" > ocr.json
```

- Output: JSON array of `{text, conf, x, y, w, h}`, pixels, **top-left origin** (the script
  already flips Vision's bottom-left normalized coordinates).
- **Check language support before trusting it.** As of macOS 26 the supported list has CJK,
  Korean, Japanese, Arabic, Cyrillic, Thai, Vietnamese and most European languages — but
  **no Hebrew**. Query it with `swift assets/ocr_vision.swift --list-langs`, or in Swift:

  ```swift
  import Vision
  let req = VNRecognizeTextRequest(); req.recognitionLevel = .accurate
  print(try req.supportedRecognitionLanguages())
  ```
- For an unsupported script Vision does not fail — it emits confident-looking Latin/Cyrillic
  garbage (`'THOHORUN'` for `אזור מיטה`) and *silently drops* many regions. Expect an
  incomplete box set: usable, never sufficient on its own.

## Engine 2: Windows.Media.Ocr (Windows, zero install)

`assets/ocr_windows.ps1` wraps the WinRT OCR engine (same JSON shape as the Vision script,
but **word-level** like tesseract — cluster the words):

```powershell
powershell -ExecutionPolicy Bypass -File assets/ocr_windows.ps1 -ListLangs
powershell -ExecutionPolicy Bypass -File assets/ocr_windows.ps1 page0_150.png he
```

- Run with **Windows PowerShell 5.1** (`powershell.exe`), not pwsh 7 — the script uses the
  WinRT projection.
- Language coverage = the machine's installed OCR language packs (Settings → Time & Language)
  — **Hebrew is available here**, unlike Vision. `-ListLangs` shows what's installed; the
  script exits with an error for a missing pack instead of guessing.
- No confidence values (`conf` is always 1.0) and a hard ~2600 px input cap — the script
  refuses oversized images rather than silently downscaling; render at 150 dpi.
- This script is authored to the documented WinRT API but has not been exercised on a real
  Windows box by this skill's tests — treat the first Windows run as its verification, and
  check the JSON against the page before trusting it.

## Engine 3: tesseract (any OS, any language)

macOS:

```bash
brew install tesseract        # ships eng + osd (+ snum) — no other languages
curl -sL -o heb.traineddata \
  https://github.com/tesseract-ocr/tessdata_best/raw/main/heb.traineddata
cp heb.traineddata "$(brew --prefix)/share/tessdata/"
tesseract page0_200.png out -l heb+eng tsv   # -> out.tsv, word-level boxes
```

Windows (`winget install UB-Mannheim.TesseractOCR`, or `choco install tesseract`): the
binary lands at `%ProgramFiles%\Tesseract-OCR\tesseract.exe` and its `tessdata` folder next
to it needs admin rights to write — put downloaded traineddata in a user folder instead and
point `TESSDATA_PREFIX` at it (the `configs/` for `tsv` output must be copied along, same
trap as below). Linux: `apt install tesseract-ocr tesseract-ocr-heb` (language packs are
distro packages — no manual download needed).

**The `--tessdata-dir` trap:** pointing `--tessdata-dir` at a local folder that holds only
traineddata files breaks output configs — `read_params_file: Can't open tsv` — because the
`tsv`/`txt` config files live in the *default* tessdata dir's `configs/` subfolder. Copy the
traineddata into brew's tessdata dir instead (as above); it's user-writable.

`tessdata_best` models are a few MB each and noticeably more accurate than the default; the
language codes are ISO 639-2/3-based (`heb`, `jpn`, `ara`, `rus`) with tesseract-specific
script variants like `chi_sim`/`chi_tra` — and `*_vert` models for vertical text (below).

## Clustering words into labels

Both engines return word-level (tesseract) or fragment-level (Vision) boxes. Merge into one
box per visual label:

- Group by tesseract's `(block_num, par_num, line_num)` **and then split on horizontal gaps
  wider than ~80 px @200 dpi**. Grouping by line alone merges every label that happens to
  share a baseline — on a sheet with a rendering + plan + title block, that produced a single
  2484-px-wide "line" spanning three unrelated labels.
- Union the member word boxes for the cluster box; keep mean confidence for triage.
- On RTL pages, word order within a cluster is unreliable in both engines. Irrelevant if you
  follow the rule: boxes from OCR, content from your own reading.

## Reconciling into the spec

For every item in your visual inventory pick the best box: Vision's if present (tighter),
else tesseract's, else measure manually. Cross-check the two engines — where both agree
within a few px you're done; where they disagree, or only one found it, verify by crop.

## Refining a box by 600 dpi crop

For any suspect box (and any label OCR missed entirely):

```python
page.get_pixmap(clip=fitz.Rect(x0pt, y0pt, x1pt, y1pt), dpi=600).save("crop.png")
```

Read the crop, measure the text's pixel extent inside it, then:

```
pt  = crop_origin_pt + crop_px / (600/72)     # crop pixels -> page points
spec_px = pt * spec_dpi / 72                  # page points -> spec pixels
```

Two iterations (debug overlay → crop-measure → adjust) converge; do not eyeball offsets from
a full-page view — at 150 dpi display scale a "small" misjudgment is 30+ spec pixels, which
was exactly the error that put a work-corner box on a desk chair instead of its caption.

## Vertical and rotated text

Vertical CJK columns (tategaki on Japanese menus, spine titles) and rotated labels (axis
titles, drawing margins) fail *silently* through the default pipeline:

- **Vision returns an empty array for vertical CJK** — exit 0, no error, just nothing. Unlike
  the unsupported-script case there isn't even a garbage box to reuse. Your step-1 visual
  inventory is the only thing that notices the hole: every inventory item must end up with a
  box, so a vertical column shows up as an item no engine found.
- **tesseract needs the vertical models**: `jpn_vert`, `chi_sim_vert`, `chi_tra_vert`,
  `kor_vert` — same download-and-copy dance as any traineddata. Plain `jpn` on a vertical
  column emits noise.
- **Boxes for vertical text are tall and narrow**, and `overlay_translate.py` only draws
  horizontal text — fitting "Today's Specials" into a 30×400 px box yields an unreadable
  minimum-size line (the script at least warns). Two workable renderings:
  1. **Rotate the replacement**: patch the box as usual, then draw with
     `page.insert_text(origin, text, rotate=90)` (origin is the *bottom-left* of the rotated
     text run; 270 runs the other way). Good when the vertical orientation is part of the
     design.
  2. **Re-typeset horizontally** into adjacent open space when the page has room and the
     orientation was just a space-saving device.
- **Rotated spans in text-layer PDFs** (Path B) carry their direction in the line's `dir`
  vector — `(0, 1)`/`(0, -1)` means vertical. Redact them like any span, then render with
  option 1.

## The debug overlay gate

Before generating any output, draw every spec box as a numbered red rectangle on the page,
render at 150 dpi, and inspect. Pass criteria: every rectangle sits on its text with a snug
margin; no rectangle covers geometry it shouldn't. This is cheap (one render) and catches the
two failure classes that ruin final output: off-target boxes and too-short boxes.

## The completeness sweep

After the spec "feels done", hunt for what it misses: sweep the page region by region at
zoom — title block top to bottom, each drawing area, margins and corners. Duplicated labels
are the classic miss (the same zone name printed in two places). Dimension numbers, phone
numbers, and brand logos are excluded by policy, not by forgetfulness — say so in the sweep
instructions so the reviewer doesn't file them.
