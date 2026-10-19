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
Its overlap is intentionally repeated/noncontiguous and needs explicit per-message Slinx
importer review too; the local synthetic review file is not importer approval.

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

For a separately authorized static crop, stage its verified lossless RGB/RGBA PNG with:

```bash
python3 skills/wecom-chat-capture/scripts/chat_package.py stage-media /private/output/sticker-crop.png --media-dir /private/output/batch/media --original-name screenshot-derived-static.png --content-type image/png --role screenshot_preview --derived-from media/missing-original.gif --provenance-file /private/output/crop-provenance.json
```

The provenance file must contain the canonical `source`/`capture_method` object, with optional
locator/notes describing the observed crop. Retain the missing original inventory and both
refs on the same message. The helper bounds static PNG scanlines, dimensions and aggregate
preview pixels; animation, corrupt/truncated/trailing data and unsupported PNG crop modes
fail. Preview reports derived roles, missing original audio and transcript counts explicitly.
It never includes transcripts in original message text or uses derived data for identity.

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
The helper cannot verify the truth of evidence text; Slinx still applies importer review.
Before an eventual authorized import, verify that `base_batch_id` is the conversation's
current active head. The runtime accepts only a linear chain and may require per-message
review for repeated or noncontiguous mappings; see [runtime constraints](contract.md#overlap-and-derived-records).

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
