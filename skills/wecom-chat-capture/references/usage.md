# Offline helper usage

Run from the repository root with Python 3.10+ (standard library only). In an installed
skill, replace the repository prefix below with the actual skill directory. All commands
operate only on explicitly supplied local paths, with no WeCom/network/upload access.

## Reproduce the synthetic baseline and delta

Use a new private scratch directory. The checked-in `assets/synthetic/` files are also
ready-to-validate examples; the generator deterministically reproduces them.

```bash
python3 skills/wecom-chat-capture/scripts/make_synthetic.py /tmp/wecom-synthetic-demo
python3 skills/wecom-chat-capture/scripts/chat_package.py preview /tmp/wecom-synthetic-demo/baseline
python3 skills/wecom-chat-capture/scripts/chat_package.py pack /tmp/wecom-synthetic-demo/baseline --output /tmp/wecom-baseline.zip
python3 skills/wecom-chat-capture/scripts/chat_package.py preview /tmp/wecom-synthetic-demo/delta --prior /tmp/wecom-baseline.zip
python3 skills/wecom-chat-capture/scripts/chat_package.py pack /tmp/wecom-synthetic-demo/delta --prior /tmp/wecom-baseline.zip --review /tmp/wecom-synthetic-demo/delta-review.json --output /tmp/wecom-delta.zip
python3 skills/wecom-chat-capture/scripts/chat_package.py validate /tmp/wecom-delta.zip --prior /tmp/wecom-baseline.zip
```

The baseline contains eight original occurrences, including two identical legitimate
text messages, a PNG, UTF-8 attachment, WAV, reply, unavailable video and unknown absolute
time. The delta contains three observations, two reviewed overlap mappings and one new
message; its image resolves from the baseline without duplicating media bytes. The review
file is explicitly invented for this synthetic example; never use it to approve real overlap.
The preview flags both repeated-text candidates rather than choosing an occurrence.
Its overlap is intentionally repeated/noncontiguous. The local synthetic review file records
invented occurrence decisions only and does not authorize actions in another system.

## Prepare actual authorized observations locally

First follow the scope and UI procedure in [capture-workflow.md](capture-workflow.md).
Use a private directory outside source control with exactly `manifest.json`, `messages.jsonl`
and `media/`. Keep authorization, checkpoints, review decisions and derived sidecars in
an adjacent private working directory; only canonical typed derived fields/media belong
inside the package tree. Set the root directory
permissions to private (for example `chmod 700` on POSIX). Do not copy actual data into
this skill's assets or tests.

Construct manifest/messages using the canonical schemas and synthetic examples. Supply
explicit order, original text/time labels, scope and provenance. Unknown fields stay null
where permitted and limitations go in notes. For originals already saved through the
authorized UI, use:

```bash
python3 skills/wecom-chat-capture/scripts/chat_package.py stage-media /private/output/downloaded-original --media-dir /private/output/batch/media --original-name '可见原始文件名' --content-type application/octet-stream
```

The command copies bytes unchanged and prints one inventory object; insert it into the
manifest and reference path/hash/source_batch_id/role from the message. It never rewrites
or deletes the source. Use the evidenced MIME type, or `application/octet-stream` when
unknown. Display filenames never become filesystem paths.
For a sticker actually saved through `Save As GIF`/`另存为 GIF`, verify that the bytes are
GIF before using `--content-type image/gif`. Keep the original file unchanged; do not
re-encode it or infer full-animation timing from tool screenshots. If an earlier package
marked it missing, create a distinct corrected batch and an external supersedes note.

## Voice and static preview examples

Generate synthetic examples in a new directory; no real chat or audio is accessed:

```bash
python3 skills/wecom-chat-capture/scripts/make_voice_synthetic.py /tmp/wecom-voice-demo
python3 skills/wecom-chat-capture/scripts/chat_package.py preview /tmp/wecom-voice-demo/baseline
python3 skills/wecom-chat-capture/scripts/chat_package.py voice-record /tmp/wecom-voice-demo/voice-original.spec.json --media-dir /tmp/wecom-voice-stage/media --output /tmp/wecom-voice-original.json
python3 skills/wecom-chat-capture/scripts/chat_package.py voice-record /tmp/wecom-voice-demo/voice-transcript-only.spec.json --media-dir /tmp/wecom-voice-stage/media --output /tmp/wecom-voice-transcript.json
python3 skills/wecom-chat-capture/scripts/chat_package.py voice-record /tmp/wecom-voice-demo/voice-missing-both.spec.json --media-dir /tmp/wecom-voice-stage/media --output /tmp/wecom-voice-missing.json
```

The baseline has four occurrences: unchanged invented WAV, missing audio with invented UI
transcription, missing audio and no transcription, and missing animated sticker plus a typed
static PNG preview. These examples do not claim a downloaded original or real UI evidence.
`voice-record` consumes `{message,audio}` as shown in the specs, with empty incoming media.
`audio` contains only `file`, `original_name`, `content_type`, `missing_reason`. Relative file
paths resolve beside the spec. Complete originals need a local file and null missing_reason;
missing originals need null file, an explicit reason and an audio MIME kind. Unknown codec
is `audio/unknown`. Output is an exclusive private JSON file containing message and attachment
objects to insert in the batch; stdout reports only identifiers/counts, not transcript text.
Unknown duration/time stay null. This helper never records, plays or transcribes audio.

Authorized capture includes scoped visible sticker crops unless the user excludes them.
For a manually assembled static crop, stage its verified lossless RGB/RGBA PNG with:

```bash
python3 skills/wecom-chat-capture/scripts/chat_package.py stage-media /private/output/sticker-crop.png --media-dir /private/output/batch/media --original-name screenshot-derived-static.png --content-type image/png --role screenshot_preview --derived-from media/missing-original.gif --provenance-file /private/output/crop-provenance.json
```

The provenance file must contain the canonical `source`/`capture_method` object, with optional
locator/notes describing the observed crop. Retain the missing original inventory and both
refs on the same message. The helper bounds static PNG scanlines, dimensions and aggregate
preview pixels; animation, corrupt/truncated/trailing data and unsupported PNG crop modes
fail. Preview reports derived roles, missing original audio and transcript counts explicitly.
It never includes transcripts in original message text or uses derived data for identity.

## Prepare stickers without dropping visible artwork

Use `sticker-record` to construct the message, inventory and media references together.
It copies saved bytes unchanged; it does not operate WeCom or capture screenshots. Generate
the synthetic voice/sticker directory above, then try its three sticker states:

```bash
python3 skills/wecom-chat-capture/scripts/chat_package.py sticker-record /tmp/wecom-voice-demo/sticker-original.spec.json --media-dir /tmp/wecom-sticker-stage/media --output /tmp/wecom-sticker-original.json
python3 skills/wecom-chat-capture/scripts/chat_package.py sticker-record /tmp/wecom-voice-demo/sticker-preview.spec.json --media-dir /tmp/wecom-sticker-stage/media --output /tmp/wecom-sticker-preview.json
python3 skills/wecom-chat-capture/scripts/chat_package.py sticker-record /tmp/wecom-voice-demo/sticker-missing.spec.json --media-dir /tmp/wecom-sticker-stage/media --output /tmp/wecom-sticker-missing.json
```

If the UI tool saves a full PNG but cannot crop it, use the local lossless crop helper:

```bash
python3 skills/wecom-chat-capture/scripts/crop_preview.py /private/output/work/viewport.png --box 480 220 180 160 --output /private/output/work/sticker-crop.png
```

`--box` is left, top, width, height in **that source PNG's actual pixels**; the values above
are illustrative. Inspect the source image before selecting coordinates. The helper preserves
the decoded RGB/RGBA crop and color metadata without resizing, redrawing or generating art.
It accepts the same bounded, noninterlaced 8-bit RGB/RGBA static PNG subset as the preview
validator. It does not take screenshots or read the UI itself. Record the viewport locator,
capture time, source dimensions and crop box in the private capture ledger and preview
provenance. Inspect the output crop; then remove the temporary full-window image when it is
no longer needed. Do not package that full screenshot or unrelated chat content.

Spec shape (use an observed canonical message with `type:"sticker"`, empty `media`, and
null `text` for an artwork-only sticker):

```json
{"message":{},"sticker":{"file":null,"original_name":null,"missing_reason":"Visible save menu did not expose an original export.","preview":{"file":"sticker-crop.png","provenance":{"source":"wecom_ui","capture_method":"lossless screenshot crop","locator":"viewport-3 / occurrence-8","notes":"One visible display state; original animation unavailable."}}}}
```

`message:{}` above is a shape placeholder; use the complete message in a generated spec as
the template. Keep original visible names, time labels, text and occurrence IDs. Paths resolve
beside the spec. For a saved original, set `file`, use its evidenced `original_name` (null when
unknown), and set `missing_reason` and `preview` to null. The helper recognizes PNG/GIF/WebP
container bytes without reencoding; unrecognized originals remain opaque bytes. This format
check does not prove a downloaded file is the correct source sticker: inspect it too.

When the original is unavailable, set `file` to null and provide a specific `missing_reason`.
Supply the inspected lossless crop in `preview`. Its provenance must identify the UI capture
and observed occurrence. The output contains `message` plus `attachments`; insert both into
the batch and recompute counts. The missing original is retained, the PNG is labeled
`screenshot_preview`, and both refs are on the same occurrence. Overall original attachment
completeness stays partial. No invented original filename, hash, GIF MIME type or text label
fills the gap. If the artwork is also unavailable or screenshots were excluded, set `preview`
to null and report the visual gap. Repeated stickers stay separate messages even if the pixels
are identical. Do not use a screen capture to claim recovered animation or source timing.

## Review the actual images before ZIP delivery

`preview` now reports `sticker_visuals` per occurrence: `original_available`, `static_preview`,
or `visual_missing`. Opaque original bytes alone do not establish visual coverage. Render a
private offline HTML review outside the package directory:

```bash
python3 skills/wecom-chat-capture/scripts/review_chat.py /private/output/batch --output /private/output/work/review.html
python3 skills/wecom-chat-capture/scripts/chat_package.py pack /private/output/batch --require-sticker-visual --output /private/output/capture.zip
python3 skills/wecom-chat-capture/scripts/chat_package.py validate /private/output/capture.zip
python3 skills/wecom-chat-capture/scripts/review_chat.py /private/output/capture.zip --output /private/output/work/zip-review.html
```

Supply repeated `--prior` arguments to each command when the batch depends on earlier ZIPs.
Open the HTML locally in a browser and compare the artwork, text, sender and order against
the authorized UI observations. The review embeds supported raster images, including saved
GIF animations and static previews, so an unlisted or missing file cannot masquerade as an
image. It labels previews and original gaps separately and preserves UI transcripts as
derived text. It never loads remote media or runs message content. HTML stays outside the
canonical ZIP; it is working QA, not a change to the receiving system.
If the available browser tool blocks local files, do not bypass its policy with another
browser surface or URL. Inspect the local media files and validated references directly,
and report that the HTML layout was not rendered in that environment.

`--require-sticker-visual` rejects an occurrence lacking a supported original visual or a
static preview before writing the ZIP. It cannot detect a wrong/blank crop or prove UI
completeness. Inspect the saved image itself. Genuine visual gaps can still be delivered
using ordinary `pack`, with the exact limitation reported. Deliver the final ZIP path and
SHA256, selected scope, original-media gaps, and static-only fallbacks; stop there.

## Validate and package observed records

`normalize SOURCE --output NEW_DIRECTORY [--prior PRIOR ...]` computes counts, fills hashes
and byte sizes for declared complete local files, updates their message refs, assigns IDs
only to null IDs already labeled generated, and canonicalizes JSON serialization. It does
not infer timestamps, sort, deduplicate, rename input paths, alter media or repair unresolved
references. Persist its output and IDs before building reply/overlap links. It recalculates
local hashes intentionally; use `validate` on completed packages to detect corruption.
Both source and normalized output have the canonical package layout, not a separate raw
capture format. Unknown fields, unlisted files, missing original bytes and unsafe paths fail.

`validate SOURCE [--prior PRIOR ...]` checks a directory or ZIP. Supply every prior package
needed by the base chain, media and replies, each explicitly authorized for this dataset.
No auto-discovery from unrelated files or hash stores occurs. Duplicate batch IDs are rejected
even if byte-identical; this is validation of one chain, not an importer idempotency action.

`preview SOURCE [--prior PRIOR ...]` performs the same checks and prints scope, counts,
completeness notes, missing media, unknown times/senders, dependencies, overlap candidates
and file SHA256 values as JSON. Save this output beside the batch if desired. Structural
validity does not establish UI completeness, authenticity or reviewed incremental identity.

`pack SOURCE --output NEW.zip [--prior PRIOR ...] [--review FILE]` validates, requires exact
review evidence for declared anchors, then emits deterministic bytes. Outputs are exclusive;
choose a new path instead of overwriting an earlier package. It never uploads.

Review file (outside ZIP):

```json
{"batch_id":"delta-001","decisions":[{"message_id":"delta-g0","base_message_id":"base-g1","decision":"same","evidence":"User explicitly reviewed this ordered occurrence mapping against the visible anchor."}]}
```

Only create real review decisions from explicit occurrence review, never AI fingerprint
matching. If uncertain, omit that anchor, retain observations, and report the pending candidates.
The helper cannot verify the truth of evidence text. Local validation/review is about the
delivered files; it does not authorize or guarantee import into another system.

## Checkpoint and resume

Save a numbered snapshot after each verified viewport, outside the package directory:

```bash
python3 skills/wecom-chat-capture/scripts/chat_package.py checkpoint /tmp/wecom-synthetic-demo/baseline --checkpoint /tmp/wecom-checkpoint-001.json --cursor 'fixture:viewport-1 / base-g7' --authorization 'Synthetic scope only; no real capture'
python3 skills/wecom-chat-capture/scripts/chat_package.py resume-check /tmp/wecom-synthetic-demo/baseline --checkpoint /tmp/wecom-checkpoint-001.json
```

Checkpoint output contains selected range/timezone, authorization, cursor, message prefix
hashes and the complete preview (including missing/uncertain-original notes). It refuses
to overwrite a prior snapshot. Resume verifies conversation/batch/base, authorized range,
timezone and unchanged verified observation prefix, then reports the cursor to re-find.
It does not move the WeCom UI or prove the cursor still exists. Re-identify the exact
conversation and multi-message anchor before collecting more. Changed prior observations,
including resolved media metadata, require deliberate review and a fresh checkpoint;
do not silently discard the older evidence. For an empty/unvalidated initial capture,
record scope/cursor manually until at least one schema-valid observation exists.

## Tests and skill bundle

```bash
python3 -m unittest discover -s tests -p 'test_wecom*.py' -v
python3 scripts/package_skills.py build
python3 scripts/package_skills.py --check
```

These tests use synthetic data only. No account, credentials, service, UI session, package
installation or paid API is needed. The generated root `.skill` archive is intentionally
Git-ignored, following repository convention.
