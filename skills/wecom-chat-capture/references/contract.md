# Slinx chat ZIP v1

Canonical version: `slinx-chat-zip-v1`. The Slinx importer owns this format. The pinned
[manifest schema](slinx-chat-zip-v1.manifest.schema.json) and
[message schema](slinx-chat-zip-v1.message.schema.json) were copied from its generated
`docs/contracts/` schemas on 2026-10-19, including required `original_name` and the optional
typed voice/static-preview extension (canonical stage `bf339d0`). Old v1 ZIPs remain valid:
omitted role defaults to original, omitted voice/derived_from/provenance defaults to null.
Extended ZIPs need the updated importer; older strict parsers can reject the new fields.
The version and three-part root layout remain unchanged. Synthetic fixtures were accepted
by the canonical parser. Future changes
must be coordinated with the importer and revalidated; these are snapshots, not a competing
format. Extra fields are forbidden at every schema object level.

## ZIP layout

One conversation and batch per ZIP, with only `manifest.json`, `messages.jsonl`, `media/`
and inventoried local media files. UTF-8 JSON; one JSON object per ASCII LF-delimited line
in messages. Original Unicode, line breaks and repeated identical occurrences remain intact.
No media base64 in JSON. The producer emits deterministic ZIP_DEFLATED members with fixed
1980 timestamps and private file modes; JSON keys sort for deterministic serialization.
Media payload bytes never change. JSON serialization may change without changing strings.

Safe media paths: ASCII POSIX relative paths beginning `media/`, at most 240 characters,
only letters, digits, `_`, `-`, `.`, `/`; no empty, `.` or `..` segments, backslashes,
absolute paths, symlinks, special files, duplicate names or casefold collisions. Original
display names (including Unicode or path-like text) are metadata only. The staging helper
uses `<sha256>-<occurrence>.bin`; MIME type and original display name are independent of suffix.

The local helper limits individual files and ZIP uploads to 32 MiB, total expanded bytes
to 64 MiB, JSONL records to 1 MiB, and ZIP entries to 2003. Canonical counts allow
1–50000 messages and 0–2000 inventory entries.
It validates the central directory before decompressing, never extracts a ZIP, and refuses
to overwrite output. Large captures must use smaller explicitly related batches. These
limits align with the current canonical archive parser; a deployed importer may add policy limits.

## Manifest fields

| Field | Meaning |
|---|---|
| `version` | Exactly `slinx-chat-zip-v1` |
| `conversation_id`, `title` | Stable local conversation identity and observed title; if generated, record that fact in provenance notes |
| `batch_id`, `base_batch_id` | Unique batch identity; baseline base is null, delta names its immediate prior batch |
| `capture` | `started_at`, `ended_at` nullable offset ISO timestamps for authorized message range; `captured_at` offset ISO capture time; IANA `timezone` |
| `counts` | `messages` = JSONL record count, `attachments` = inventory entry count (including prior references and missing entries) |
| `attachments` | Inventory described below |
| `completeness` | `history`: complete/partial/unknown; `attachments`: complete/partial/none; `notes`: explicit gaps, uncertain originals, bounds and limitations |
| `provenance` | `source`, `capture_method`; optional nullable `locator`, `notes` |
| `overlap_anchors` | Reviewed mappings `{message_id, base_message_id}` to the immediate base; never a content hash deduplication instruction |

Every inventory item requires `path`, `original_name` (string or null), `sha256` (lowercase
64 hex or null), `size_bytes` (integer or null), `content_type`, `completeness`
(complete/missing), `source_batch_id` (prior batch ID or null).
Optional fields are `role` (`original` or `screenshot_preview`, default original),
`derived_from` (safe media path or null, default null) and `provenance` (the same provenance
object or null). Original entries require null `derived_from`.

- Complete local item: hash and size required; bytes must exist at the declared path and match.
- Missing original: no bytes and no prior batch reference. Preserve the visible message,
  display filename and gap reason; unknown hash/size remain null. Uncertain originals,
  thumbnail-only captures and blocked downloads stay missing until original bytes are verified.
- Prior reference: complete inventory entry, no duplicated local bytes. Supply the declared
  ancestor batch and its dependency chain explicitly to validation. Resolve by conversation,
  batch, path, SHA256 and size; a matching hash alone grants no reuse. A deleted or unavailable
  prior package blocks resolution. Materialize original bytes into a new self-contained batch
  if needed; never silently change an existing batch's identity.
- Same bytes can be referenced by multiple messages; different display-name occurrences may
  use distinct safe paths. SHA256 identifies bytes, never message identity. No content-based
  message merging or media transcoding.
- Screenshot preview: complete `image/png`, role `screenshot_preview`, explicit provenance
  and `derived_from` pointing to a missing original inventory entry. Both original and
  preview must be referenced by the same message. Keep original missing and attachment
  completeness partial. Preview hashes never establish original identity. Authorized
  visual message capture includes this representation unless the user excludes screenshots.
  This capture policy does not change the pinned schema or turn the crop into original media.

Static screenshot previews must be true static PNGs, never APNG (even one frame). Corrupt,
truncated or trailing-data PNGs fail. Canonical validation verifies and decodes with Pillow;
local previews together may contain at most 16,777,216 decoded pixels, with each dimension
at most 16,384. The dependency-free producer deliberately accepts a narrower PNG subset:
noninterlaced 8-bit RGB/RGBA without a palette, with CRC, framing, bounded zlib scanline and
filter checks. Use lossless screenshot crops in that mode. Other original media bytes,
including original animations, remain unchanged and are not subject to preview conversion.

Manifest attachment hashes protect original media. The preview separately reports all local
file hashes, including manifest/messages, and `pack` reports the resulting ZIP hash. File-hash
reports remain outside the ZIP because v1 does not permit an extra root hash field.

## Message fields

| Field | Meaning |
|---|---|
| `id`, `id_kind`, `source_id` | Occurrence ID; source/generated; only exposed source identity may fill source_id, otherwise null |
| `sender` | `{id:null|string, name:null|string, is_self:boolean}`; never infer an account ID from display name |
| `sent_at`, `original_time` | Nullable offset ISO time and exact visible original label; unknown absolute time remains null |
| `order` | Unique increasing nonnegative observation order within this batch; do not infer times to sort |
| `type`, `text` | Visible message kind and nullable original text; preserve punctuation, emojis, whitespace and repeated content |
| `reply_to` | Null or `{message_id,batch_id}` resolvable in this batch or its ancestors |
| `media` | References `{path,sha256,source_batch_id,role?}` matching inventory exactly; role defaults original |
| `provenance` | Same provenance shape as manifest; locator can identify viewport/position; notes describe uncertainty or visible unresolved quote |
| `voice` | Optional null or typed voice metadata, only for type voice; described below |

Voice metadata is `{original_duration:null|string, duration_ms:null|integer, transcripts:[]}`.
Preserve the exact visible duration label (maximum 240 characters); duration_ms must be
evidenced, 0–2147483647, and stay null when unknown. Each transcript is
`{text,source:"wecom_ui",provenance}`: 1–200000 characters and at most 20 displayed results.
It is derived UI transcription, never original typed message text. The producer requires
null text for voice-only records. Voice metadata needs at least one original `audio/*`
inventory reference, complete or missing (`audio/unknown` for unknown unavailable audio).
The default capture workflow skips audio export and retains a missing inventory entry with
an explicit intentional-omission reason and no payload file. This does not assert that
WeCom disallows export. Original attachment completeness remains partial. Capture displayed
UI transcripts by default; if no readable transcript is available, retain duration, sender,
time label, order, the missing-audio entry and an explicit transcript gap. Do not infer text.

Generated IDs are persistent local occurrence identifiers, not source IDs. Normalization may
fill null IDs for records already labeled generated, using batch identity plus explicit order;
assign and persist IDs before resolving replies/anchors. It never invents sender, text, time,
range, source IDs or reply targets. Existing IDs remain unchanged.

## Overlap and derived records

Only explicitly reviewed occurrence mappings go into `overlap_anchors`. The pack command
requires a separate exact review file with evidence for all declared mappings, including
repeated-text ambiguity. A candidate match is never proof. The preview reports candidate
counts and ambiguity without mutating records; large reports cap displayed candidates at
500 observations and 20 base IDs per observation and flag truncation. Candidates without
review remain separate observations with no declared mapping. Slinx performs its own review
and identity validation; this helper cannot approve an importer operation.

Prior media and replies must resolve through the explicitly supplied base ancestry. Local
validation checks those files and links; it does not inspect a receiving system's state or
promise ingestion. This skill stops after delivering the verified ZIP.

Fingerprints exclude screenshot preview hashes and all voice transcripts/provenance;
they include observed voice duration only when nonnull. Original-only fingerprints retain
their meaning. Missing originals remain incomplete evidence even when the visual crop is
readable. A candidate match never grants permission to merge occurrences.

Pending candidates, authorization evidence, local UI cursor/checkpoints and other
screenshots/OCR/transcription remain outside the ZIP. Only the typed derived representations
above belong in the canonical package. External derived records should identify original batch,
message and attachment hash, method/model, result and uncertainty. They cannot replace
original text, resurrect unavailable messages or assert an original media file exists.
