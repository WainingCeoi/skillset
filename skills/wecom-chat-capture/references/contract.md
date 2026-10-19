# Slinx chat ZIP v1

Canonical version: `slinx-chat-zip-v1`. The Slinx importer owns this format. The pinned
[manifest schema](slinx-chat-zip-v1.manifest.schema.json) and
[message schema](slinx-chat-zip-v1.message.schema.json) were copied from its generated
`docs/contracts/` schemas on 2026-10-19, including required `original_name`.
Both synthetic fixtures were accepted by the canonical Pydantic models. Future changes
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
| `media` | References `{path,sha256,source_batch_id}` matching inventory exactly |
| `provenance` | Same provenance shape as manifest; locator can identify viewport/position; notes describe uncertainty or visible unresolved quote |

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

Pending candidates, authorization evidence, local UI cursor/checkpoints, screenshots and
OCR/transcription remain outside the ZIP. Derived records should identify original batch,
message and attachment hash, method/model, result and uncertainty. They cannot replace
original text, resurrect unavailable messages or assert an original media file exists.
