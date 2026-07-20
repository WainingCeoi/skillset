#!/usr/bin/env python3
"""Overlay translations onto a PDF, preserving the original layout.

Requires PyMuPDF — the pip/uv package is `pymupdf` (NOT `fitz`, which is an
unrelated broken package).

Reads a spec JSON:
  {"dpi": 200, "labels": [{"id", "page": 0, "bbox": [x,y,w,h] (pixels at `dpi`),
   "he": original, "en": ..., "zh": ..., "style": "white"|"chip", "cell": true}]}

- style "white": source text sits on a plain background (title blocks, technical
  plans). Cover with a white patch, draw replacement in black.
- style "chip":  source text is baked into a photo/render. Cover with a rounded
  chip filled with the sampled surrounding color, draw replacement in white.
- "cell" (default true, white style only): the label lives inside a table cell,
  so its patch never grows horizontally and gains at most 1.5x height in
  bilingual mode — growing further wipes cell borders and collides with
  neighbors. Set "cell": false for a free-standing label on open background:
  it may then widen (up to 1.3x) so EN and ZH render at a comfortable size
  instead of shrinking to fit a compact source string.

Every label renders its lines at ONE shared font size (EN over 中文 at two
different sizes reads as a mistake), and a warning is printed for any line that
still overflows at the minimum size.

All patches are drawn before any text, so an overlapping later patch can never
erase an earlier label's text.

Rotated/vertical source labels are not handled here: measure the box from the
page, then extend with `page.insert_text(origin, text, rotate=90)` — see
references/ocr-pipeline.md ("Vertical and rotated text").

Usage:
  python3 overlay_translate.py SPEC SRC OUT --mode en
  python3 overlay_translate.py SPEC SRC OUT --mode en+zh [--cjk-font PATH]

The CJK font is auto-detected per OS (macOS / Windows / Linux candidates below);
--cjk-font overrides. If nothing loads, PyMuPDF's built-in CJK fallback
(Droid Sans Fallback) is used — always works, just plainer.
"""
import argparse
import json
import os
import statistics
import sys

import fitz

MARGIN = 2.0        # pt breathing room inside each patch
MIN_FS = 4.0        # never shrink text below this

CJK_FONT_CANDIDATES = [
    "/Library/Fonts/Arial Unicode.ttf",                          # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",                   # macOS fallback
    r"C:\Windows\Fonts\msyh.ttc",                                # Windows (Microsoft YaHei)
    r"C:\Windows\Fonts\simsun.ttc",                              # Windows fallback
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",    # Linux (Noto)
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
]


def fit_fontsize(text, width, height, font):
    """Largest fontsize that fits text in width x height (pt) for the given fitz.Font."""
    fs = height * 0.78
    while fs > MIN_FS and font.text_length(text, fontsize=fs) > width - 2 * MARGIN:
        fs -= 0.25
    return max(fs, MIN_FS)


def sample_bg(page, rect, dpi, cache):
    """Median color of the pixels ringing `rect` (pt) in a page render at `dpi`."""
    if page.number not in cache:
        cache[page.number] = page.get_pixmap(dpi=dpi)
    pix = cache[page.number]
    s = dpi / 72.0
    x0, y0 = int(rect.x0 * s), int(rect.y0 * s)
    x1, y1 = int(rect.x1 * s), int(rect.y1 * s)
    ring = 6
    px = []
    for y in range(max(0, y0 - ring), min(pix.height, y1 + ring)):
        for x in range(max(0, x0 - ring), min(pix.width, x1 + ring)):
            if x0 <= x < x1 and y0 <= y < y1:
                continue  # ring only: skip the text region itself
            px.append(pix.pixel(x, y))
    return tuple(statistics.median(c[i] for c in px) / 255.0 for i in range(3))


def layout_label(page, lab, mode, fonts, spec_dpi, bg_cache):
    """Compute this label's patch + text draw ops. Returns (patch_op, [text_ops])."""
    s = 72.0 / spec_dpi
    x, y, w, h = lab["bbox"]
    rect = fitz.Rect(x * s, y * s, (x + w) * s, (y + h) * s)
    chip = lab["style"] == "chip"
    free = chip or not lab.get("cell", True)

    lines = [("en", lab["en"])]
    if mode == "en+zh" and lab.get("zh") and lab["zh"] != lab["en"]:
        lines.append(("zh", lab["zh"]))

    box = fitz.Rect(rect)
    if len(lines) == 2:
        # bilingual needs more height: free labels may double, cell-bound cap at 1.5x
        grow = rect.height * (0.55 if free else 0.25)
        box.y0 -= grow
        box.y1 += grow
    line_h = box.height / len(lines)

    if free:
        # free labels widen toward a comfortable size instead of shrinking to fit
        target = line_h * 0.62
        need = max(fonts[k].text_length(t, fontsize=target) for k, t in lines) + 2 * MARGIN
        cap = box.width * (4.0 if chip else 1.3)  # chips float on artwork; white stays subtle
        if need > box.width:
            grow_x = (min(need, cap) - box.width) / 2
            box.x0 -= grow_x
            box.x1 += grow_x

    # one shared size per label: EN over 中文 at two sizes reads as a mistake
    fs = min(fit_fontsize(t, box.width, line_h, fonts[k]) for k, t in lines)

    ops = []
    for i, (kind, text) in enumerate(lines):
        width = fonts[kind].text_length(text, fontsize=fs)
        if width > box.width - 2 * MARGIN:
            print(f"warning: label {lab.get('id')} line {text!r} overflows its box even at "
                  f"minimum size - widen the bbox or shorten the translation", file=sys.stderr)
        top = box.y0 + i * line_h
        origin = fitz.Point(box.x0 + (box.width - width) / 2, top + line_h / 2 + fs * 0.36)
        ops.append((origin, text, fs, kind, (1, 1, 1) if chip else (0, 0, 0)))

    patch = box + (-MARGIN, -MARGIN, MARGIN, MARGIN)
    fill = sample_bg(page, rect, spec_dpi, bg_cache) if chip else (1, 1, 1)
    return (patch, fill, 0.18 if chip else None), ops


def load_fonts(mode, cjk_path):
    """Font objects for measuring + insert_text kwargs for drawing, per language."""
    fonts = {"en": fitz.Font("helv")}
    kwargs = {"en": {"fontname": "helv"}}
    if mode != "en+zh":
        return fonts, kwargs
    for path in ([cjk_path] if cjk_path else CJK_FONT_CANDIDATES):
        if not os.path.exists(path):
            continue
        try:
            fonts["zh"] = fitz.Font(fontfile=path)
            kwargs["zh"] = {"fontname": "cjk", "fontfile": path}
            return fonts, kwargs
        except Exception as e:
            print(f"warning: could not load CJK font {path} ({e}), trying next", file=sys.stderr)
    # built-in CJK fallback (Droid Sans Fallback) — works with no font file
    fonts["zh"] = fitz.Font("cjk")
    kwargs["zh"] = {"fontname": "china-s"}
    return fonts, kwargs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--mode", choices=["en", "en+zh"], default="en")
    ap.add_argument("--cjk-font", default=None,
                    help="CJK font file override; auto-detected per OS when omitted")
    args = ap.parse_args()

    spec = json.load(open(args.spec))
    doc = fitz.open(args.src)
    fonts, text_kwargs = load_fonts(args.mode, args.cjk_font)
    bg_cache = {}

    per_page = {}
    for lab in spec["labels"]:
        per_page.setdefault(lab.get("page", 0), []).append(lab)

    for pno, labs in per_page.items():
        page = doc[pno]
        drawn = []
        shape = page.new_shape()
        for lab in labs:  # pass 1: all patches
            patch_op, text_ops = layout_label(page, lab, args.mode, fonts, spec["dpi"], bg_cache)
            rect, fill, radius = patch_op
            shape.draw_rect(rect, radius=radius)
            shape.finish(color=None, fill=fill)
            drawn.extend(text_ops)
        shape.commit()
        for origin, text, fs, kind, color in drawn:  # pass 2: all text
            page.insert_text(origin, text, fontsize=fs, color=color, **text_kwargs[kind])

    doc.subset_fonts()  # a full CJK font embeds ~20 MB; subsetting keeps only used glyphs
    doc.save(args.out, garbage=3, deflate=True)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
