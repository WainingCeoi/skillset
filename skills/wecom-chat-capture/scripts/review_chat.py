#!/usr/bin/env python3
"""Render a validated local capture as a private, self-contained HTML review.

This is visual QA before ZIP delivery, not an importer. Python standard library only;
no UI, network, media conversion, OCR, or script execution.
"""
from __future__ import annotations

import argparse
import base64
from html import escape
import json
import os
from pathlib import Path
import sys
import tempfile

import chat_package as cp


MAX_HTML_BYTES = 128 * 1024 * 1024
IMAGE_TYPES = {"image/png", "image/gif", "image/jpeg", "image/webp"}
STYLE = """*{box-sizing:border-box}body{margin:0;background:#edf0f2;color:#23313d;
font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
main{max-width:900px;margin:auto;padding:30px 24px 56px}header{margin-bottom:25px}
.eyebrow{font-size:11px;font-weight:700;letter-spacing:.14em;color:#607381}
h1{font-size:26px;line-height:1.25;margin:7px 0 12px;overflow-wrap:anywhere}
.summary{background:#fff;border:1px solid #dbe2e6;border-radius:12px;padding:15px 18px}
.muted,.time,.kind,.locator{color:#657581;font-size:12px}.summary p{margin:4px 0}
.notice{color:#8b590a}.row{display:flex;gap:12px;margin:24px 0;align-items:flex-start}
.row.self{flex-direction:row-reverse}.avatar{display:grid;place-items:center;flex:0 0 34px;
height:34px;border-radius:10px;background:#dde6ec;color:#526b7a;font-weight:650}
.body{min-width:0;max-width:calc(100% - 46px)}.meta{display:flex;gap:10px;align-items:baseline;
flex-wrap:wrap;margin:0 2px 5px}.sender{font-weight:650;overflow-wrap:anywhere}
.bubble{border:1px solid #dbe2e6;border-radius:3px 13px 13px;padding:12px 16px;background:white;
box-shadow:0 1px 1px #23313d06}.self .bubble{background:#dff0df;border-color:#c8dfc7;
border-radius:13px 3px 13px 13px}.text,.transcript{white-space:pre-wrap;overflow-wrap:anywhere}
figure{margin:4px 0 10px}figure:last-child{margin-bottom:0}img{display:block;max-width:100%;
max-height:460px;object-fit:contain}figure.sticker img{max-width:220px;max-height:220px}
figcaption{font-size:11px;color:#657581;margin-top:7px}.file,.gap{font-size:12px;
padding:8px 10px;background:#f4f6f7;border-radius:6px;margin-top:8px;overflow-wrap:anywhere}
.gap{color:#8b590a;background:#fff6e7}.transcript{border-left:2px solid #9faeb8;
padding-left:10px;margin-top:12px}.locator{margin:4px 2px;overflow-wrap:anywhere}
details{margin-top:8px}summary{cursor:pointer}ul{padding-left:20px;margin:8px 0}
footer{font-size:12px;color:#657581;margin-top:35px;border-top:1px solid #dbe2e6;padding-top:15px}
@media(max-width:500px){main{padding:20px 12px}.time{width:100%}.bubble{padding:10px 12px}}
"""


def image_matches(data, content_type):
    """Only embed raster formats; never trust a MIME label for active formats."""
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def media_bytes(package, item, batches):
    """Resolve only the explicitly validated ancestor chain, with no disk discovery."""
    while item["source_batch_id"] is not None:
        package = batches[item["source_batch_id"]]
        item = next(entry for entry in package.manifest["attachments"] if entry["path"] == item["path"])
    return package.entries[item["path"]]


def document_parts(package, batches):
    manifest = package.manifest
    inventory = {item["path"]: item for item in manifest["attachments"]}
    missing = sum(item["completeness"] == "missing" for item in inventory.values())
    previews = sum(cp.media_role(item) == "screenshot_preview" for item in inventory.values())
    yield '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    yield '<meta name="viewport" content="width=device-width,initial-scale=1">'
    yield ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
           'img-src data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">')
    yield f'<title>{escape(manifest["title"])} · Local capture review</title><style>{STYLE}</style></head><body><main>'
    yield f'<header><div class="eyebrow">LOCAL CAPTURE REVIEW</div><h1>{escape(manifest["title"])}</h1>'
    yield ('<div class="summary"><p><strong>' + str(len(package.messages)) + ' observed messages</strong> · '
           + str(previews) + ' static screenshot previews · ' + str(missing) + ' unavailable original files</p>')
    yield (f'<p class="muted">History: {escape(manifest["completeness"]["history"])} · '
           f'Original attachments: {escape(manifest["completeness"]["attachments"])} · '
           f'Timezone: {escape(manifest["capture"]["timezone"])}</p>')
    yield '<p class="muted">Visual review of captured records. Compare against the scoped WeCom UI before delivery.</p>'
    notes = manifest["completeness"]["notes"]
    if notes:
        yield '<details><summary class="notice">Capture limitations</summary><ul>'
        for note in notes:
            yield '<li>' + escape(note) + '</li>'
        yield '</ul></details>'
    yield '</div></header>'
    for message in package.messages:
        sender = message["sender"]["name"]
        time_label = message["original_time"]
        if time_label is None:
            time_label = message["sent_at"] or "Time not visible in source"
        row_class = "row self" if message["sender"]["is_self"] else "row"
        yield f'<article class="{row_class}" data-message-id="{escape(message["id"], quote=True)}">'
        yield f'<div class="avatar">{escape(sender[:1] if sender else "?")}</div><div class="body">'
        yield ('<div class="meta"><span class="sender">' + escape(sender if sender is not None else "Sender not visible in source")
               + '</span><span class="time">' + escape(time_label) + '</span><span class="kind">'
               + escape(message["type"]) + '</span></div><div class="bubble">')
        if message["text"] is not None:
            yield '<div class="text">' + escape(message["text"]) + '</div>'
        if message["reply_to"] is not None:
            yield '<div class="muted">Reply reference: ' + escape(message["reply_to"]["message_id"]) + '</div>'
        items = [inventory[ref["path"]] for ref in message["media"]]
        shown = False
        for item in items:
            if item["completeness"] != "complete":
                continue
            data = media_bytes(package, item, batches)
            mime = item["content_type"]
            is_preview = cp.media_role(item) == "screenshot_preview"
            if mime in IMAGE_TYPES and image_matches(data, mime):
                label = "Static screenshot fallback · original unavailable" if is_preview else "Original image · unchanged bytes"
                image_class = "sticker" if message["type"] == "sticker" else "image"
                uri = 'data:' + mime + ';base64,' + base64.b64encode(data).decode("ascii")
                yield (f'<figure class="{image_class}"><img src="{uri}" alt="'
                       + escape(item["original_name"] or label, quote=True) + '"><figcaption>'
                       + label + '</figcaption></figure>')
                shown = True
            else:
                yield ('<div class="file">Original file retained: ' + escape(item["original_name"] or item["path"])
                       + ' <span class="muted">(' + escape(mime) + '; no visual renderer for these bytes)</span></div>')
        voice = message.get("voice")
        if voice is not None:
            duration = voice.get("original_duration")
            if duration is not None:
                yield '<div class="muted">Visible voice duration: ' + escape(duration) + '</div>'
            for transcript in voice["transcripts"]:
                yield ('<div class="transcript"><div class="muted">WeCom UI transcription · derived</div>'
                       + escape(transcript["text"]) + '</div>')
        for item in items:
            if item["completeness"] == "missing":
                yield '<div class="gap">Original unavailable: ' + escape(item["original_name"] or item["path"]) + '</div>'
        if message["type"] == "sticker" and not shown:
            yield '<div class="gap">No renderable sticker visual captured. Review this occurrence before delivery.</div>'
        yield '</div><div class="locator">' + escape(message["id"]) + ' · order ' + str(message["order"]) + '</div></div></article>'
    yield ('<footer>Private offline review · batch ' + escape(package.batch_id)
           + '<br>Static fallbacks preserve one observed state. Missing originals and unknown times stay unresolved.</footer></main></body></html>')


def render(source, output, prior_paths=()):
    """Validate first, then atomically create private HTML outside all package trees."""
    source = cp.no_links(source)
    prior_paths = [cp.no_links(path) for path in prior_paths]
    output = cp.no_links(output)
    cp.require(not output.exists(), "review output exists; refusing to overwrite")
    for path in [source, *prior_paths]:
        cp.require(not path.is_dir() or path not in output.parents,
                   "review HTML must stay outside the canonical package tree")
    package, batches = cp.load_bundle(source, prior_paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".chat-review-", dir=output.parent)
    temporary = Path(temporary_name)
    total = 0
    try:
        with os.fdopen(fd, "wb") as stream:
            for part in document_parts(package, batches):
                data = part.encode("utf-8")
                total += len(data)
                cp.require(total <= MAX_HTML_BYTES, "HTML review exceeds 128 MiB; split the capture into smaller batches")
                stream.write(data)
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {"review": str(output), "messages": len(package.messages), "size_bytes": total,
            "notice": "Private visual QA only; compare against the scoped WeCom UI. ZIP layout is unchanged."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="validated canonical batch directory or ZIP")
    parser.add_argument("--output", type=Path, required=True, help="new private HTML file outside the package tree")
    parser.add_argument("--prior", type=Path, action="append", default=[], help="explicit prior package; repeat for ancestry")
    args = parser.parse_args()
    try:
        print(json.dumps(render(args.source, args.output, args.prior), ensure_ascii=False))
        return 0
    except (cp.Invalid, OSError, ValueError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
